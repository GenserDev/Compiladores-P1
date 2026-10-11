"""Generador de codigo intermedio (TAC) para Compiscript.

Recorre el arbol que dejo anotado el analizador semantico (`ctx.tipo`, `ctx.simbolo`, ...)
y produce un `ProgramaTAC`. Tambien completa la tabla de simbolos con direcciones,
registros de activacion y disposicion de objetos.
"""
import re

from CompiscriptParser import CompiscriptParser as P
from CompiscriptVisitor import CompiscriptVisitor

from tipos import (TipoArreglo, TipoFuncion, ENTERO, FLOTANTE, CADENA, BOOLEANO, VACIO,
                   es_numerico, unificar)
from simbolos import RegistroActivacion
from tac import Instruccion, FuncionTAC, ProgramaTAC, NEGADA
from temporales import PoolTemporales, es_temporal

ETIQUETA_MAIN = "$main"

# operaciones cuyo resultado puede redirigirse directo a una variable (evita la copia t -> x)
PRODUCTORAS = {"+", "-", "*", "/", "%", "<", "<=", ">", ">=", "==", "!=", "neg", "not", "itof",
               "tostr", "concat", "call", "callind", "newarray", "len", "aload", "new", "getf",
               "copy", "addr", "getexc"}


class ErrorGeneracion(Exception):
    pass


class ContextoFuncion:
    """Estado de generacion de la funcion que se esta traduciendo."""

    def __init__(self, funcion, registro, padre, es_metodo=False, retorno=None):
        self.funcion = funcion
        self.registro = registro
        self.nivel = registro.nivel
        self.padre = padre
        self.es_metodo = es_metodo
        self.retorno = retorno
        self.pool = PoolTemporales()
        self.nombres = {}
        self.lazos = []     # pila de {"break", "continue", "tries"}
        self.tries = 0


def desenvolver(ctx):
    """Baja por las reglas encadenadas de la gramatica hasta el nodo que realmente decide."""
    while True:
        if isinstance(ctx, P.ExpressionContext):
            ctx = ctx.assignmentExpr()
        elif isinstance(ctx, P.ExprNoAssignContext):
            ctx = ctx.conditionalExpr()
        elif isinstance(ctx, P.TernaryExprContext) and not ctx.expression():
            ctx = ctx.logicalOrExpr()
        elif isinstance(ctx, P.LogicalOrExprContext) and len(ctx.logicalAndExpr()) == 1:
            ctx = ctx.logicalAndExpr(0)
        elif isinstance(ctx, P.LogicalAndExprContext) and len(ctx.equalityExpr()) == 1:
            ctx = ctx.equalityExpr(0)
        elif isinstance(ctx, P.EqualityExprContext) and len(ctx.relationalExpr()) == 1:
            ctx = ctx.relationalExpr(0)
        elif isinstance(ctx, P.RelationalExprContext) and len(ctx.additiveExpr()) == 1:
            ctx = ctx.additiveExpr(0)
        elif isinstance(ctx, P.AdditiveExprContext) and len(ctx.multiplicativeExpr()) == 1:
            ctx = ctx.multiplicativeExpr(0)
        elif isinstance(ctx, P.MultiplicativeExprContext) and len(ctx.unaryExpr()) == 1:
            ctx = ctx.unaryExpr(0)
        elif isinstance(ctx, P.UnaryExprContext) and ctx.primaryExpr() is not None:
            ctx = ctx.primaryExpr()
        elif isinstance(ctx, P.PrimaryExprContext) and ctx.expression() is not None:
            ctx = ctx.expression()
        else:
            return ctx


def tipo_de(ctx):
    return getattr(ctx, "tipo", None)


def tamano_elemento(tipo):
    return getattr(tipo, "tamano", 8) or 8


class GeneradorTAC(CompiscriptVisitor):
    def __init__(self, tabla):
        self.tabla = tabla
        self.salida = []
        self.cx = None
        self.etiquetas = 0
        self.linea = 0

    # ------------------------------------------------------------------ utilidades
    def visitChildren(self, ctx):
        raise ErrorGeneracion("construccion sin traduccion: {}".format(type(ctx).__name__))

    def emitir(self, op, arg1=None, arg2=None, res=None, tipo=None):
        instruccion = Instruccion(op, arg1, arg2, res, str(tipo) if tipo is not None else None, self.linea)
        self.cx.funcion.instrucciones.append(instruccion)
        return instruccion

    def nueva_etiqueta(self):
        self.etiquetas += 1
        return "L{}".format(self.etiquetas)

    def poner(self, etiqueta):
        self.emitir("label", res=etiqueta)

    def temp(self):
        return self.cx.pool.nueva()

    def liberar(self, *operandos):
        for operando in operandos:
            self.cx.pool.liberar(operando)

    def en_temporal(self, operando):
        """Copia `operando` a un temporal propio si no lo es (para valores que deben sobrevivir)."""
        if es_temporal(operando):
            return operando
        t = self.temp()
        self.emitir("copy", operando, res=t)
        return t

    # ------------------------------------------------------------------ nombres y direcciones
    def asignar_nombre(self, simbolo):
        base = simbolo.nombre
        if re.match(r"^[tL][0-9]+$", base):
            base += "#"
        veces = self.cx.nombres.get(base, 0)
        self.cx.nombres[base] = veces + 1
        simbolo.nombre_tac = base if veces == 0 else "{}#{}".format(base, veces + 1)

    def declarar_almacenamiento(self, simbolo, es_global):
        if es_global:
            simbolo.almacenamiento = "global"
            simbolo.nombre_tac = "$" + simbolo.nombre
            simbolo.nivel_funcion = 0
            simbolo.offset = self.tabla.reservar_global(simbolo)
            simbolo.direccion = "gp+{}".format(simbolo.offset)
            return
        self.asignar_nombre(simbolo)
        simbolo.nivel_funcion = self.cx.nivel
        if simbolo.categoria == "parametro":
            simbolo.almacenamiento = "parametro"
            simbolo.offset = self.cx.registro.reservar_parametro(simbolo)
        else:
            simbolo.almacenamiento = "local"
            simbolo.offset = self.cx.registro.reservar_local(simbolo)
        simbolo.direccion = "fp+{}".format(simbolo.offset)

    def acceso(self, simbolo):
        if simbolo.almacenamiento == "global":
            return simbolo.nombre_tac
        saltos = self.cx.nivel - simbolo.nivel_funcion
        return simbolo.nombre_tac if saltos == 0 else "{}^{}".format(simbolo.nombre_tac, saltos)

    def acceso_this(self):
        cx = self.cx
        saltos = 0
        while cx is not None and not cx.es_metodo:
            cx = cx.padre
            saltos += 1
        if cx is None:
            raise ErrorGeneracion("'this' fuera de un metodo")
        return "this" if saltos == 0 else "this^{}".format(saltos)

    # ------------------------------------------------------------------ conversiones
    def convertir(self, operando, desde, hasta):
        if operando is None or desde is None or hasta is None:
            return operando
        if hasta == FLOTANTE and desde == ENTERO:
            if re.fullmatch(r"-?[0-9]+", operando):
                return operando + ".0"
            self.liberar(operando)
            t = self.temp()
            self.emitir("itof", operando, res=t, tipo=FLOTANTE)
            return t
        return operando

    def a_cadena(self, operando, tipo):
        if tipo == CADENA:
            return operando
        self.liberar(operando)
        t = self.temp()
        self.emitir("tostr", operando, res=t, tipo=CADENA)
        return t

    def volcar(self, valor, destino):
        """Deja `valor` en `destino`; si el valor es el temporal recien producido, lo redirige."""
        instrucciones = self.cx.funcion.instrucciones
        if (es_temporal(valor) and instrucciones and instrucciones[-1].res == valor
                and instrucciones[-1].op in PRODUCTORAS):
            instrucciones[-1].res = destino
        else:
            self.emitir("copy", valor, res=destino)
        self.liberar(valor)

    # ------------------------------------------------------------------ programa
    def recolectar_clases(self, nodo):
        if isinstance(nodo, P.ClassDeclarationContext):
            info = getattr(nodo, "info", None)
            if info is not None:
                info.calcular_disposicion()
                info.inicializadores = []
                for miembro in nodo.classMember():
                    if miembro.variableDeclaration() is not None:
                        d = miembro.variableDeclaration()
                        if d.initializer() is not None:
                            info.inicializadores.append(
                                (info.atributos[d.Identifier().getText()], d.initializer().expression()))
                    elif miembro.constantDeclaration() is not None:
                        d = miembro.constantDeclaration()
                        info.inicializadores.append(
                            (info.atributos[d.Identifier().getText()], d.expression()))
        for i in range(nodo.getChildCount()):
            hijo = nodo.getChild(i)
            if hasattr(hijo, "getChildCount"):
                self.recolectar_clases(hijo)

    def generar(self, arbol):
        self.recolectar_clases(arbol)
        registro = RegistroActivacion(ETIQUETA_MAIN, 0)
        self.tabla.registros.append(registro)
        funcion = FuncionTAC(ETIQUETA_MAIN, registro, [], es_main=True)
        self.cx = ContextoFuncion(funcion, registro, None)
        for s in arbol.statement():
            self.visit(s)
        self.emitir("return")
        self.cerrar_contexto()
        self.salida.insert(0, funcion)
        vtables = {nombre: info.tabla_virtual() for nombre, info in self.tabla.clases.items()}
        return ProgramaTAC(self.salida, self.tabla.area_global, vtables)

    def cerrar_contexto(self):
        registro = self.cx.registro
        registro.temporales = self.cx.pool.maximo
        registro.total_temporales = self.cx.pool.pedidos

    # ------------------------------------------------------------------ sentencias
    def visitStatement(self, ctx):
        self.linea = ctx.start.line
        return self.visit(ctx.getChild(0))

    def visitBlock(self, ctx):
        marca = self.cx.registro.marca()
        for s in ctx.statement():
            self.visit(s)
        self.cx.registro.liberar(marca)

    def cuerpo(self, statements):
        marca = self.cx.registro.marca()
        for s in statements:
            self.visit(s)
        self.cx.registro.liberar(marca)

    def es_global(self, ctx):
        padre = ctx.parentCtx
        return padre is not None and isinstance(padre.parentCtx, P.ProgramContext)

    def visitVariableDeclaration(self, ctx):
        simbolo = ctx.simbolo
        self.declarar_almacenamiento(simbolo, self.es_global(ctx))
        if ctx.initializer() is not None:
            expr = ctx.initializer().expression()
            valor = self.visit(expr)
            valor = self.convertir(valor, tipo_de(expr), simbolo.tipo)
            self.volcar(valor, self.acceso(simbolo))
        return None

    def visitConstantDeclaration(self, ctx):
        simbolo = ctx.simbolo
        self.declarar_almacenamiento(simbolo, self.es_global(ctx))
        valor = self.visit(ctx.expression())
        valor = self.convertir(valor, tipo_de(ctx.expression()), simbolo.tipo)
        self.volcar(valor, self.acceso(simbolo))
        return None

    def guardar_simbolo(self, simbolo, valor):
        if simbolo.categoria == "atributo":
            self.emitir("putf", self.acceso_this(), simbolo.nombre, valor, tipo=simbolo.tipo)
            return valor
        destino = self.acceso(simbolo)
        self.volcar(valor, destino)
        return destino

    def visitAssignment(self, ctx):
        expresiones = ctx.expression()
        if len(expresiones) == 1:
            simbolo = ctx.simbolo
            valor = self.visit(expresiones[0])
            valor = self.convertir(valor, tipo_de(expresiones[0]), simbolo.tipo)
            self.liberar(self.guardar_simbolo(simbolo, valor))
        else:
            objeto = self.visit(expresiones[0])
            self.guardar_campo(objeto, tipo_de(expresiones[0]), ctx.Identifier().getText(), expresiones[1])
        return None

    def guardar_campo(self, objeto, tipo_objeto, nombre, expr_valor):
        miembro = tipo_objeto.info.buscar_miembro(nombre)
        valor = self.visit(expr_valor)
        valor = self.convertir(valor, tipo_de(expr_valor), miembro.tipo)
        self.emitir("putf", objeto, nombre, valor, tipo=miembro.tipo)
        self.liberar(objeto)
        return valor

    def visitExpressionStatement(self, ctx):
        self.liberar(self.visit(ctx.expression()))
        return None

    def visitPrintStatement(self, ctx):
        valor = self.visit(ctx.expression())
        self.emitir("print", valor)
        self.liberar(valor)
        return None

    def visitIfStatement(self, ctx):
        falso = self.nueva_etiqueta()
        self.saltar_si_falso(ctx.expression(), falso)
        self.visit(ctx.block(0))
        if len(ctx.block()) == 2:
            fin = self.nueva_etiqueta()
            self.emitir("goto", res=fin)
            self.poner(falso)
            self.visit(ctx.block(1))
            self.poner(fin)
        else:
            self.poner(falso)
        return None

    def entrar_lazo(self, rotura, continuacion):
        self.cx.lazos.append({"break": rotura, "continue": continuacion, "tries": self.cx.tries})

    def salir_lazo(self):
        self.cx.lazos.pop()

    def visitWhileStatement(self, ctx):
        condicion, fin = self.nueva_etiqueta(), self.nueva_etiqueta()
        self.poner(condicion)
        self.saltar_si_falso(ctx.expression(), fin)
        self.entrar_lazo(fin, condicion)
        self.visit(ctx.block())
        self.salir_lazo()
        self.emitir("goto", res=condicion)
        self.poner(fin)
        return None

    def visitDoWhileStatement(self, ctx):
        inicio, condicion, fin = self.nueva_etiqueta(), self.nueva_etiqueta(), self.nueva_etiqueta()
        self.poner(inicio)
        self.entrar_lazo(fin, condicion)
        self.visit(ctx.block())
        self.salir_lazo()
        self.poner(condicion)
        self.saltar_si_verdadero(ctx.expression(), inicio)
        self.poner(fin)
        return None

    def visitForStatement(self, ctx):
        marca = self.cx.registro.marca()
        inicializacion = condicion = actualizacion = None
        seccion = 0
        for hijo in ctx.children:
            if isinstance(hijo, (P.VariableDeclarationContext, P.AssignmentContext)):
                inicializacion = hijo
                seccion = 1
            elif isinstance(hijo, P.ExpressionContext):
                if seccion == 1:
                    condicion = hijo
                else:
                    actualizacion = hijo
            elif hasattr(hijo, "symbol") and hijo.getText() == ";":
                seccion += 1
        if inicializacion is not None:
            self.visit(inicializacion)
        l_cond, l_act, fin = self.nueva_etiqueta(), self.nueva_etiqueta(), self.nueva_etiqueta()
        self.poner(l_cond)
        if condicion is not None:
            self.saltar_si_falso(condicion, fin)
        self.entrar_lazo(fin, l_act)
        self.visit(ctx.block())
        self.salir_lazo()
        self.poner(l_act)
        if actualizacion is not None:
            self.liberar(self.visit(actualizacion))
        self.emitir("goto", res=l_cond)
        self.poner(fin)
        self.cx.registro.liberar(marca)
        return None

    def visitForeachStatement(self, ctx):
        marca = self.cx.registro.marca()
        arreglo = self.en_temporal(self.visit(ctx.expression()))
        longitud = self.temp()
        self.emitir("len", arreglo, res=longitud, tipo=ENTERO)
        indice = self.temp()
        self.emitir("copy", "0", res=indice, tipo=ENTERO)
        simbolo = ctx.simbolo
        self.declarar_almacenamiento(simbolo, False)
        l_cond, l_act, fin = self.nueva_etiqueta(), self.nueva_etiqueta(), self.nueva_etiqueta()
        self.poner(l_cond)
        self.emitir("if>=", indice, longitud, fin)
        self.emitir("aload", arreglo, indice, self.acceso(simbolo), tipo=simbolo.tipo)
        self.entrar_lazo(fin, l_act)
        self.visit(ctx.block())
        self.salir_lazo()
        self.poner(l_act)
        self.emitir("+", indice, "1", indice, tipo=ENTERO)
        self.emitir("goto", res=l_cond)
        self.poner(fin)
        self.liberar(arreglo, longitud, indice)
        self.cx.registro.liberar(marca)
        return None

    def cerrar_trys(self, hasta):
        for _ in range(self.cx.tries - hasta):
            self.emitir("poptry")

    def visitBreakStatement(self, ctx):
        lazo = self.cx.lazos[-1]
        self.cerrar_trys(lazo["tries"])
        self.emitir("goto", res=lazo["break"])
        return None

    def visitContinueStatement(self, ctx):
        for lazo in reversed(self.cx.lazos):
            if lazo["continue"] is not None:
                self.cerrar_trys(lazo["tries"])
                self.emitir("goto", res=lazo["continue"])
                return None
        raise ErrorGeneracion("'continue' fuera de un bucle")

    def visitReturnStatement(self, ctx):
        valor = None
        if ctx.expression() is not None:
            valor = self.visit(ctx.expression())
            valor = self.convertir(valor, tipo_de(ctx.expression()), self.cx.retorno)
        self.cerrar_trys(0)
        self.emitir("return", valor)
        self.liberar(valor)
        return None

    def visitTryCatchStatement(self, ctx):
        captura, fin = self.nueva_etiqueta(), self.nueva_etiqueta()
        self.emitir("pushtry", res=captura)
        self.cx.tries += 1
        self.visit(ctx.block(0))
        self.cx.tries -= 1
        self.emitir("poptry")
        self.emitir("goto", res=fin)
        self.poner(captura)
        marca = self.cx.registro.marca()
        simbolo = ctx.simbolo
        self.declarar_almacenamiento(simbolo, False)
        self.emitir("getexc", res=self.acceso(simbolo), tipo=CADENA)
        self.visit(ctx.block(1))
        self.cx.registro.liberar(marca)
        self.poner(fin)
        return None

    def visitSwitchStatement(self, ctx):
        control = self.en_temporal(self.visit(ctx.expression()))
        tipo_control = tipo_de(ctx.expression())
        casos = ctx.switchCase()
        por_defecto = ctx.defaultCase()
        etiquetas = [self.nueva_etiqueta() for _ in casos]
        l_defecto = self.nueva_etiqueta() if por_defecto is not None else None
        fin = self.nueva_etiqueta()
        for caso, etiqueta in zip(casos, etiquetas):
            valor = self.visit(caso.expression())
            a, b = self.igualar_tipos(control, tipo_control, valor, tipo_de(caso.expression()))
            self.emitir("if==", a, b, etiqueta)
            self.liberar(b)
        self.emitir("goto", res=l_defecto if l_defecto is not None else fin)
        self.entrar_lazo(fin, None)
        for caso, etiqueta in zip(casos, etiquetas):
            self.poner(etiqueta)
            self.cuerpo(caso.statement())
        if por_defecto is not None:
            self.poner(l_defecto)
            self.cuerpo(por_defecto.statement())
        self.salir_lazo()
        self.poner(fin)
        self.liberar(control)
        return None

    # ------------------------------------------------------------------ funciones y clases
    def visitFunctionDeclaration(self, ctx):
        self.generar_funcion(ctx)
        return None

    def generar_funcion(self, ctx):
        simbolo = ctx.simbolo
        es_metodo = simbolo.categoria == "metodo"
        padre = self.cx
        registro = RegistroActivacion(simbolo.etiqueta, padre.nivel + 1, padre.registro, es_metodo)
        self.tabla.registros.append(registro)
        simbolo.registro = registro
        simbolo.nivel_funcion = registro.nivel
        simbolo.almacenamiento = "funcion"
        simbolo.direccion = simbolo.etiqueta
        funcion = FuncionTAC(simbolo.etiqueta, registro, [])
        self.cx = ContextoFuncion(funcion, registro, padre, es_metodo, simbolo.retorno)
        nombres = []
        if es_metodo:
            registro.reservar_this()
            nombres.append("this")
        for parametro in ctx.parametros_simbolos:
            self.declarar_almacenamiento(parametro, False)
            nombres.append(parametro.nombre_tac)
        funcion.parametros = nombres
        for s in ctx.block().statement():
            self.visit(s)
        self.retorno_implicito()
        self.cerrar_contexto()
        self.cx = padre
        self.salida.append(funcion)

    def retorno_implicito(self):
        instrucciones = self.cx.funcion.instrucciones
        if not instrucciones or instrucciones[-1].op != "return":
            self.emitir("return")

    def visitClassDeclaration(self, ctx):
        info = ctx.info
        for metodo in info.metodos.values():
            metodo.almacenamiento = "funcion"
        for miembro in ctx.classMember():
            if miembro.functionDeclaration() is not None:
                self.generar_funcion(miembro.functionDeclaration())
        if info.tiene_inicializadores():
            self.generar_init(info)
        return None

    def generar_init(self, info):
        etiqueta = "{}.$init".format(info.nombre)
        padre = self.cx
        registro = RegistroActivacion(etiqueta, padre.nivel + 1, padre.registro, True)
        self.tabla.registros.append(registro)
        funcion = FuncionTAC(etiqueta, registro, ["this"])
        self.cx = ContextoFuncion(funcion, registro, padre, True, VACIO)
        registro.reservar_this()
        anterior = info.padre.clase_con_init() if info.padre is not None else None
        if anterior is not None:
            self.emitir("param", "this")
            self.emitir("call", "{}.$init".format(anterior.nombre), 1)
        for atributo, expr in info.inicializadores:
            valor = self.visit(expr)
            valor = self.convertir(valor, tipo_de(expr), atributo.tipo)
            self.emitir("putf", "this", atributo.nombre, valor, tipo=atributo.tipo)
            self.liberar(valor)
        self.emitir("return")
        self.cerrar_contexto()
        self.cx = padre
        self.salida.append(funcion)

    # ------------------------------------------------------------------ saltos condicionales
    def igualar_tipos(self, a, ta, b, tb):
        if ta is not None and tb is not None and es_numerico(ta) and es_numerico(tb):
            comun = unificar(ta, tb)
            a = self.convertir(a, ta, comun)
            b = self.convertir(b, tb, comun)
        return a, b

    def saltar_si_falso(self, ctx, destino):
        n = desenvolver(ctx)
        if isinstance(n, P.LogicalOrExprContext):
            partes = n.logicalAndExpr()
            verdadero = self.nueva_etiqueta()
            for parte in partes[:-1]:
                self.saltar_si_verdadero(parte, verdadero)
            self.saltar_si_falso(partes[-1], destino)
            self.poner(verdadero)
            return
        if isinstance(n, P.LogicalAndExprContext):
            for parte in n.equalityExpr():
                self.saltar_si_falso(parte, destino)
            return
        if self.es_negacion(n):
            self.saltar_si_verdadero(n.unaryExpr(), destino)
            return
        relacion = self.relacion_simple(n)
        if relacion is not None:
            op, a, b = relacion
            self.emitir("if" + NEGADA[op], a, b, destino)
            self.liberar(a, b)
            return
        texto = n.getText()
        if texto == "true":
            return
        if texto == "false":
            self.emitir("goto", res=destino)
            return
        valor = self.visit(n)
        self.emitir("iffalse", valor, res=destino)
        self.liberar(valor)

    def saltar_si_verdadero(self, ctx, destino):
        n = desenvolver(ctx)
        if isinstance(n, P.LogicalOrExprContext):
            for parte in n.logicalAndExpr():
                self.saltar_si_verdadero(parte, destino)
            return
        if isinstance(n, P.LogicalAndExprContext):
            partes = n.equalityExpr()
            falso = self.nueva_etiqueta()
            for parte in partes[:-1]:
                self.saltar_si_falso(parte, falso)
            self.saltar_si_verdadero(partes[-1], destino)
            self.poner(falso)
            return
        if self.es_negacion(n):
            self.saltar_si_falso(n.unaryExpr(), destino)
            return
        relacion = self.relacion_simple(n)
        if relacion is not None:
            op, a, b = relacion
            self.emitir("if" + op, a, b, destino)
            self.liberar(a, b)
            return
        texto = n.getText()
        if texto == "false":
            return
        if texto == "true":
            self.emitir("goto", res=destino)
            return
        valor = self.visit(n)
        self.emitir("if", valor, res=destino)
        self.liberar(valor)

    def es_negacion(self, n):
        return (isinstance(n, P.UnaryExprContext) and n.primaryExpr() is None
                and n.getChild(0).getText() == "!")

    def relacion_simple(self, n):
        """Si `n` es `a op b` (una sola comparacion) devuelve (op, a, b) ya evaluados."""
        if isinstance(n, P.RelationalExprContext):
            partes = n.additiveExpr()
        elif isinstance(n, P.EqualityExprContext):
            partes = n.relationalExpr()
        else:
            return None
        if len(partes) != 2:
            return None
        op = n.getChild(1).getText()
        a = self.visit(partes[0])
        b = self.visit(partes[1])
        a, b = self.igualar_tipos(a, tipo_de(partes[0]), b, tipo_de(partes[1]))
        return op, a, b

    def valor_logico(self, ctx):
        resultado = self.temp()
        falso, fin = self.nueva_etiqueta(), self.nueva_etiqueta()
        self.saltar_si_falso(ctx, falso)
        self.emitir("copy", "true", res=resultado, tipo=BOOLEANO)
        self.emitir("goto", res=fin)
        self.poner(falso)
        self.emitir("copy", "false", res=resultado, tipo=BOOLEANO)
        self.poner(fin)
        return resultado

    # ------------------------------------------------------------------ expresiones
    def visitExpression(self, ctx):
        return self.visit(ctx.assignmentExpr())

    def visitExprNoAssign(self, ctx):
        return self.visit(ctx.conditionalExpr())

    def visitTernaryExpr(self, ctx):
        if not ctx.expression():
            return self.visit(ctx.logicalOrExpr())
        resultado = self.temp()
        falso, fin = self.nueva_etiqueta(), self.nueva_etiqueta()
        tipo = tipo_de(ctx)
        self.saltar_si_falso(ctx.logicalOrExpr(), falso)
        for i, etiqueta in ((0, None), (1, falso)):
            if etiqueta is not None:
                self.poner(etiqueta)
            rama = ctx.expression(i)
            valor = self.convertir(self.visit(rama), tipo_de(rama), tipo)
            self.emitir("copy", valor, res=resultado, tipo=tipo)
            self.liberar(valor)
            if i == 0:
                self.emitir("goto", res=fin)
        self.poner(fin)
        return resultado

    def visitLogicalOrExpr(self, ctx):
        if len(ctx.logicalAndExpr()) == 1:
            return self.visit(ctx.logicalAndExpr(0))
        return self.valor_logico(ctx)

    def visitLogicalAndExpr(self, ctx):
        if len(ctx.equalityExpr()) == 1:
            return self.visit(ctx.equalityExpr(0))
        return self.valor_logico(ctx)

    def comparacion(self, ctx, partes):
        acumulado = self.visit(partes[0])
        tipo_acumulado = tipo_de(partes[0])
        for i in range(1, len(partes)):
            op = ctx.getChild(2 * i - 1).getText()
            derecha = self.visit(partes[i])
            a, b = self.igualar_tipos(acumulado, tipo_acumulado, derecha, tipo_de(partes[i]))
            self.liberar(a, b)
            acumulado = self.temp()
            tipo_acumulado = BOOLEANO
            self.emitir(op, a, b, acumulado, tipo=BOOLEANO)
        return acumulado

    def visitEqualityExpr(self, ctx):
        return self.comparacion(ctx, ctx.relationalExpr())

    def visitRelationalExpr(self, ctx):
        return self.comparacion(ctx, ctx.additiveExpr())

    def aritmetica(self, op, a, ta, b, tb):
        if op == "+" and (ta == CADENA or tb == CADENA):
            a = self.a_cadena(a, ta)
            b = self.a_cadena(b, tb)
            self.liberar(a, b)
            r = self.temp()
            self.emitir("concat", a, b, r, tipo=CADENA)
            return r, CADENA
        comun = unificar(ta, tb)
        a = self.convertir(a, ta, comun)
        b = self.convertir(b, tb, comun)
        self.liberar(a, b)
        r = self.temp()
        self.emitir(op, a, b, r, tipo=comun)
        return r, comun

    def cadena_aritmetica(self, ctx, partes):
        acumulado = self.visit(partes[0])
        tipo_acumulado = tipo_de(partes[0])
        for i in range(1, len(partes)):
            op = ctx.getChild(2 * i - 1).getText()
            derecha = self.visit(partes[i])
            acumulado, tipo_acumulado = self.aritmetica(op, acumulado, tipo_acumulado, derecha, tipo_de(partes[i]))
        return acumulado

    def visitAdditiveExpr(self, ctx):
        return self.cadena_aritmetica(ctx, ctx.multiplicativeExpr())

    def visitMultiplicativeExpr(self, ctx):
        return self.cadena_aritmetica(ctx, ctx.unaryExpr())

    def visitUnaryExpr(self, ctx):
        if ctx.primaryExpr() is not None:
            return self.visit(ctx.primaryExpr())
        operador = ctx.getChild(0).getText()
        interno = ctx.unaryExpr()
        if operador == "-":
            if re.fullmatch(r"[0-9]+(\.[0-9]+)?", interno.getText()):
                return "-" + interno.getText()
            valor = self.visit(interno)
            self.liberar(valor)
            t = self.temp()
            self.emitir("neg", valor, res=t, tipo=tipo_de(ctx))
            return t
        valor = self.visit(interno)
        self.liberar(valor)
        t = self.temp()
        self.emitir("not", valor, res=t, tipo=BOOLEANO)
        return t

    def visitPrimaryExpr(self, ctx):
        if ctx.literalExpr() is not None:
            return self.visit(ctx.literalExpr())
        if ctx.leftHandSide() is not None:
            return self.visit(ctx.leftHandSide())
        return self.visit(ctx.expression())

    def visitLiteralExpr(self, ctx):
        if ctx.arrayLiteral() is not None:
            return self.visit(ctx.arrayLiteral())
        return ctx.getText()

    def visitArrayLiteral(self, ctx):
        elementos = ctx.expression()
        tipo = tipo_de(ctx)
        elemento = tipo.elemento if isinstance(tipo, TipoArreglo) else None
        arreglo = self.temp()
        self.emitir("newarray", str(len(elementos)), str(tamano_elemento(elemento)), arreglo, tipo=tipo)
        for i, e in enumerate(elementos):
            valor = self.convertir(self.visit(e), tipo_de(e), elemento)
            self.emitir("astore", arreglo, str(i), valor)
            self.liberar(valor)
        return arreglo

    def visitNewExpr(self, ctx):
        info = ctx.info
        objeto = self.temp()
        self.emitir("new", info.nombre, str(info.tamano_objeto()), objeto, tipo=tipo_de(ctx))
        con_init = info.clase_con_init()
        if con_init is not None:
            self.emitir("param", objeto)
            self.emitir("call", "{}.$init".format(con_init.nombre), 1)
        constructor = info.constructor()
        if constructor is not None:
            operandos = self.argumentos(ctx.arguments(), [t for _, t in constructor.parametros])
            self.emitir("param", objeto)
            for o in operandos:
                self.emitir("param", o)
            self.emitir("call", constructor.etiqueta, len(operandos) + 1)
            self.liberar(*operandos)
        return objeto

    # ------------------------------------------------------------------ asignacion como expresion
    def visitAssignExpr(self, ctx):
        lhs = ctx.lhs
        sufijos = lhs.suffixOp()
        rhs = ctx.assignmentExpr()
        if not sufijos:
            atomo = lhs.primaryAtom()
            if not isinstance(atomo, P.IdentifierExprContext):
                raise ErrorGeneracion("destino de asignacion no valido")
            simbolo = atomo.simbolo
            valor = self.convertir(self.visit(rhs), tipo_de(rhs), simbolo.tipo)
            return self.guardar_simbolo(simbolo, valor)
        base = self.materializar(self.estado_de(lhs, len(sufijos) - 1))
        ultimo = sufijos[-1]
        if isinstance(ultimo, P.IndexExprContext):
            indice = self.visit(ultimo.expression())
            valor = self.convertir(self.visit(rhs), tipo_de(rhs), tipo_de(ultimo))
            self.emitir("astore", base, indice, valor)
            self.liberar(base, indice)
            return valor
        if isinstance(ultimo, P.PropertyAccessExprContext):
            nombre = ultimo.Identifier().getText()
            valor = self.convertir(self.visit(rhs), tipo_de(rhs), tipo_de(ultimo))
            self.emitir("putf", base, nombre, valor, tipo=tipo_de(ultimo))
            self.liberar(base)
            return valor
        raise ErrorGeneracion("destino de asignacion no valido")

    def visitPropertyAssignExpr(self, ctx):
        objeto = self.visit(ctx.lhs)
        return self.guardar_campo(objeto, tipo_de(ctx.lhs), ctx.Identifier().getText(), ctx.assignmentExpr())

    # ------------------------------------------------------------------ accesos encadenados
    # Un "estado" es ("val", operando, tipo) o ("fun", simbolo, receptor): una funcion o metodo
    # que todavia no se llamo.
    def estado_de(self, lhs, cantidad):
        estado = self.atomo(lhs.primaryAtom())
        for sufijo in lhs.suffixOp()[:cantidad]:
            estado = self.sufijo(estado, sufijo)
        return estado

    def visitLeftHandSide(self, ctx):
        return self.materializar(self.estado_de(ctx, len(ctx.suffixOp())))

    def materializar(self, estado):
        if estado[0] == "val":
            return estado[1]
        simbolo = estado[1]
        t = self.temp()
        self.emitir("addr", simbolo.etiqueta, res=t)
        return t

    def atomo(self, ctx):
        if isinstance(ctx, P.IdentifierExprContext):
            simbolo = ctx.simbolo
            if simbolo.categoria in ("funcion", "metodo"):
                receptor = self.acceso_this() if simbolo.categoria == "metodo" else None
                return ("fun", simbolo, receptor)
            if simbolo.categoria == "atributo":
                t = self.temp()
                self.emitir("getf", self.acceso_this(), simbolo.nombre, t, tipo=simbolo.tipo)
                return ("val", t, simbolo.tipo)
            return ("val", self.acceso(simbolo), simbolo.tipo)
        if isinstance(ctx, P.NewExprContext):
            return ("val", self.visit(ctx), tipo_de(ctx))
        if isinstance(ctx, P.ThisExprContext):
            return ("val", self.acceso_this(), tipo_de(ctx))
        raise ErrorGeneracion("atomo no soportado")

    def sufijo(self, estado, sufijo):
        if isinstance(sufijo, P.CallExprContext):
            return self.llamada(estado, sufijo)
        base = self.materializar(estado) if isinstance(sufijo, P.IndexExprContext) else None
        if isinstance(sufijo, P.IndexExprContext):
            indice = self.visit(sufijo.expression())
            self.liberar(base, indice)
            t = self.temp()
            self.emitir("aload", base, indice, t, tipo=tipo_de(sufijo))
            return ("val", t, tipo_de(sufijo))
        nombre = sufijo.Identifier().getText()
        objeto = self.materializar(estado)
        miembro = sufijo.miembro
        if miembro.categoria == "metodo":
            return ("fun", miembro, objeto)
        self.liberar(objeto)
        t = self.temp()
        self.emitir("getf", objeto, nombre, t, tipo=tipo_de(sufijo))
        return ("val", t, tipo_de(sufijo))

    def argumentos(self, ctx_args, tipos_parametros):
        expresiones = ctx_args.expression() if ctx_args is not None else []
        operandos = []
        for i, e in enumerate(expresiones):
            valor = self.visit(e)
            destino = tipos_parametros[i] if i < len(tipos_parametros) else None
            operandos.append(self.convertir(valor, tipo_de(e), destino))
        return operandos

    def llamada(self, estado, sufijo):
        if estado[0] == "fun":
            simbolo, receptor = estado[1], estado[2]
            operandos = self.argumentos(sufijo.arguments(), [t for _, t in simbolo.parametros])
            r = self.emitir_llamada(simbolo.etiqueta, receptor, operandos, simbolo.retorno, False,
                                    self.es_virtual(simbolo, receptor))
            return ("val", r, simbolo.retorno)
        callee, tipo = estado[1], estado[2]
        operandos = self.argumentos(sufijo.arguments(), tipo.parametros if isinstance(tipo, TipoFuncion) else [])
        retorno = tipo.retorno if isinstance(tipo, TipoFuncion) else None
        r = self.emitir_llamada(callee, None, operandos, retorno, True)
        return ("val", r, retorno)

    def es_virtual(self, simbolo, receptor):
        """Un metodo se despacha dinamicamente solo si alguna subclase lo sobrescribe."""
        if receptor is None or simbolo.categoria != "metodo" or simbolo.dueno is None:
            return False
        for info in self.tabla.clases.values():
            if info.es_subclase_de(simbolo.dueno) and simbolo.nombre in info.metodos:
                return True
        return False

    def emitir_llamada(self, destino, receptor, operandos, retorno, indirecta, virtual=False):
        total = len(operandos) + (1 if receptor is not None else 0)
        if receptor is not None:
            self.emitir("param", receptor)
        for o in operandos:
            self.emitir("param", o)
        self.liberar(receptor, *operandos)
        if indirecta:
            self.liberar(destino)
        op = "callind" if indirecta else ("callv" if virtual else "call")
        if retorno is None or retorno == VACIO:
            self.emitir(op, destino, total)
            return "null"
        r = self.temp()
        self.emitir(op, destino, total, r, tipo=retorno)
        return r


def generar_tac(arbol, tabla):
    return GeneradorTAC(tabla).generar(arbol)
