from antlr4 import TerminalNode
from CompiscriptParser import CompiscriptParser
from CompiscriptVisitor import CompiscriptVisitor

from tipos import (Tipo, TipoArreglo, TipoFuncion, TipoClase, PRIMITIVOS, ENTERO, FLOTANTE,
                   CADENA, BOOLEANO, NULO, VACIO, ERROR, es_error, es_numerico, compatible,
                   unificar, comparables)
from simbolos import Simbolo, InfoClase, TablaSimbolos
from errores import ColectorErrores


class AnalizadorSemantico(CompiscriptVisitor):
    def __init__(self):
        self.tabla = TablaSimbolos()
        self.errores = ColectorErrores()
        self.funciones = []
        self.clases = []
        self.bucles = 0
        self.rompibles = 0
        self.contador_bloques = 0
        self.simbolo_lhs = None
        self.simbolo_atomo = None

    def error(self, codigo, mensaje, ctx):
        self.errores.agregar(codigo, mensaje, ctx)
        return ERROR

    def analizar(self, arbol):
        self.visit(arbol)
        return self.errores

    # Fase 2: el arbol queda anotado. Cada expresion visitada guarda su tipo en `ctx.tipo`
    # y cada declaracion o uso de identificador guarda su simbolo en `ctx.simbolo`.
    # El generador de codigo intermedio lee estas anotaciones y no repite el analisis.
    def visit(self, tree):
        resultado = tree.accept(self)
        if isinstance(resultado, Tipo):
            tree.tipo = resultado
        return resultado

    def resolver_tipo(self, ctx):
        if ctx is None:
            return None
        base = ctx.baseType().getText()
        if base in PRIMITIVOS:
            tipo = PRIMITIVOS[base]
        elif base in self.tabla.clases:
            tipo = TipoClase(base, self.tabla.clases[base])
        else:
            self.error("E500", "el tipo '{}' no esta declarado".format(base), ctx)
            tipo = ERROR
        for _ in range(ctx.getText().count("[]")):
            tipo = TipoArreglo(tipo)
        return tipo

    def tipo_anotado(self, ctx):
        return self.resolver_tipo(ctx.type_()) if ctx is not None else None

    def declarar(self, simbolo, ctx):
        if not self.tabla.declarar(simbolo):
            self.error("E201", "'{}' ya fue declarado en este ambito".format(simbolo.nombre), ctx)
            return False
        return True

    def firma_funcion(self, ctx):
        parametros = []
        if ctx.parameters() is not None:
            for p in ctx.parameters().parameter():
                tipo = self.resolver_tipo(p.type_()) if p.type_() is not None else ERROR
                parametros.append((p.Identifier().getText(), tipo))
        retorno = self.resolver_tipo(ctx.type_()) if ctx.type_() is not None else VACIO
        simbolo = Simbolo(ctx.Identifier().getText(), "funcion",
                          TipoFuncion([t for _, t in parametros], retorno),
                          ctx.start.line, ctx.start.column)
        simbolo.parametros = parametros
        simbolo.retorno = retorno
        simbolo.inicializado = True
        return simbolo

    def declarar_firmas(self, statements):
        declaraciones = [s.classDeclaration() for s in statements if s.classDeclaration() is not None]
        for c in declaraciones:
            self.registrar_clase(c)
        for c in declaraciones:
            self.completar_clase(c)
        for s in statements:
            f = s.functionDeclaration()
            if f is None:
                continue
            nombre = f.Identifier().getText()
            if self.tabla.buscar_local(nombre) is not None:
                self.error("E303", "la funcion '{}' ya fue declarada".format(nombre), f)
                continue
            self.tabla.declarar(self.firma_funcion(f))

    def registrar_clase(self, ctx):
        nombre = ctx.Identifier(0).getText()
        if nombre in self.tabla.clases:
            self.error("E303", "la clase '{}' ya fue declarada".format(nombre), ctx)
            return
        info = InfoClase(nombre)
        self.tabla.clases[nombre] = info
        simbolo = Simbolo(nombre, "clase", TipoClase(nombre, info), ctx.start.line, ctx.start.column)
        simbolo.clase = info
        simbolo.inicializado = True
        self.declarar(simbolo, ctx)

    def completar_clase(self, ctx):
        nombre = ctx.Identifier(0).getText()
        info = self.tabla.clases.get(nombre)
        if info is None:
            return
        if len(ctx.Identifier()) > 1:
            padre = ctx.Identifier(1).getText()
            if padre not in self.tabla.clases:
                self.error("E505", "la clase padre '{}' no esta declarada".format(padre), ctx)
            elif padre == nombre:
                self.error("E505", "la clase '{}' no puede heredar de si misma".format(nombre), ctx)
            else:
                info.padre = self.tabla.clases[padre]
        for miembro in ctx.classMember():
            if miembro.functionDeclaration() is not None:
                metodo = self.firma_funcion(miembro.functionDeclaration())
                metodo.categoria = "metodo"
                metodo.dueno = info
                if metodo.nombre in info.metodos:
                    self.error("E303", "el metodo '{}' ya fue declarado".format(metodo.nombre), miembro)
                info.metodos[metodo.nombre] = metodo
            elif miembro.variableDeclaration() is not None:
                d = miembro.variableDeclaration()
                tipo = self.tipo_anotado(d.typeAnnotation()) or ERROR
                atributo = Simbolo(d.Identifier().getText(), "atributo", tipo, d.start.line, d.start.column)
                if atributo.nombre in info.atributos:
                    self.error("E201", "el atributo '{}' ya fue declarado".format(atributo.nombre), d)
                info.atributos[atributo.nombre] = atributo
            else:
                d = miembro.constantDeclaration()
                tipo = self.tipo_anotado(d.typeAnnotation()) or ERROR
                atributo = Simbolo(d.Identifier().getText(), "atributo", tipo, d.start.line, d.start.column)
                atributo.es_const = True
                atributo.inicializado = True
                info.atributos[atributo.nombre] = atributo

    def revisar_codigo_muerto(self, statements):
        for i, s in enumerate(statements[:-1]):
            if (s.returnStatement() is not None or s.breakStatement() is not None
                    or s.continueStatement() is not None):
                self.error("E600", "codigo inalcanzable despues de '{}'".format(s.getText().strip()[:12]),
                           statements[i + 1])
                return

    def visitProgram(self, ctx):
        statements = ctx.statement()
        self.declarar_firmas(statements)
        self.revisar_codigo_muerto(statements)
        for s in statements:
            self.visit(s)
        return None

    def visitBlock(self, ctx):
        self.contador_bloques += 1
        self.tabla.abrir_ambito("bloque{}".format(self.contador_bloques), "bloque")
        self.cuerpo(ctx.statement())
        self.tabla.cerrar_ambito()
        return None

    def cuerpo(self, statements):
        self.declarar_firmas(statements)
        self.revisar_codigo_muerto(statements)
        for s in statements:
            self.visit(s)

    def visitVariableDeclaration(self, ctx):
        nombre = ctx.Identifier().getText()
        declarado = self.tipo_anotado(ctx.typeAnnotation())
        valor = None
        if ctx.initializer() is not None:
            valor = self.visit(ctx.initializer().expression())
            if declarado is not None and not compatible(declarado, valor):
                self.error("E104", "no se puede inicializar '{}' de tipo {} con un valor {}".format(
                    nombre, declarado, valor), ctx)
        tipo = declarado if declarado is not None else (valor if valor is not None else ERROR)
        simbolo = Simbolo(nombre, "variable", tipo, ctx.start.line, ctx.start.column)
        simbolo.inicializado = valor is not None
        ctx.simbolo = simbolo
        self.declarar(simbolo, ctx)
        return None

    def visitConstantDeclaration(self, ctx):
        nombre = ctx.Identifier().getText()
        declarado = self.tipo_anotado(ctx.typeAnnotation())
        valor = self.visit(ctx.expression())
        if declarado is not None and not compatible(declarado, valor):
            self.error("E104", "no se puede inicializar la constante '{}' de tipo {} con un valor {}".format(
                nombre, declarado, valor), ctx)
        simbolo = Simbolo(nombre, "constante", declarado if declarado is not None else valor,
                          ctx.start.line, ctx.start.column)
        simbolo.es_const = True
        simbolo.inicializado = True
        ctx.simbolo = simbolo
        self.declarar(simbolo, ctx)
        return None

    def visitAssignment(self, ctx):
        expresiones = ctx.expression()
        if len(expresiones) == 1:
            nombre = ctx.Identifier().getText()
            valor = self.visit(expresiones[0])
            ctx.simbolo = self.tabla.buscar(nombre)
            self.asignar_identificador(nombre, valor, ctx)
        else:
            objeto = self.visit(expresiones[0])
            valor = self.visit(expresiones[1])
            self.asignar_propiedad(objeto, ctx.Identifier().getText(), valor, ctx)
        return None

    def asignar_identificador(self, nombre, valor, ctx):
        simbolo = self.tabla.buscar(nombre)
        if simbolo is None:
            return self.error("E200", "'{}' no esta declarado".format(nombre), ctx)
        if simbolo.es_const:
            return self.error("E202", "no se puede reasignar la constante '{}'".format(nombre), ctx)
        if not compatible(simbolo.tipo, valor):
            return self.error("E103", "no se puede asignar un valor {} a '{}' de tipo {}".format(
                valor, nombre, simbolo.tipo), ctx)
        simbolo.inicializado = True
        return simbolo.tipo

    def asignar_propiedad(self, objeto, nombre, valor, ctx):
        if es_error(objeto):
            return ERROR
        if not isinstance(objeto, TipoClase):
            return self.error("E504", "no se puede acceder a '.{}' sobre un valor {}".format(nombre, objeto), ctx)
        miembro = objeto.info.buscar_miembro(nombre)
        if miembro is None:
            return self.error("E501", "la clase '{}' no tiene el miembro '{}'".format(objeto.nombre, nombre), ctx)
        if miembro.es_const:
            return self.error("E202", "no se puede reasignar la constante '{}'".format(nombre), ctx)
        if not compatible(miembro.tipo, valor):
            return self.error("E103", "no se puede asignar un valor {} a '{}' de tipo {}".format(
                valor, nombre, miembro.tipo), ctx)
        return miembro.tipo

    def visitExpressionStatement(self, ctx):
        self.visit(ctx.expression())
        return None

    def visitPrintStatement(self, ctx):
        self.visit(ctx.expression())
        return None

    def condicion(self, ctx, palabra):
        tipo = self.visit(ctx)
        if not es_error(tipo) and tipo != BOOLEANO:
            self.error("E400", "la condicion de '{}' debe ser boolean, se encontro {}".format(palabra, tipo), ctx)

    def visitIfStatement(self, ctx):
        self.condicion(ctx.expression(), "if")
        for b in ctx.block():
            self.visit(b)
        return None

    def visitWhileStatement(self, ctx):
        self.condicion(ctx.expression(), "while")
        self.entrar_bucle(ctx.block())
        return None

    def visitDoWhileStatement(self, ctx):
        self.entrar_bucle(ctx.block())
        self.condicion(ctx.expression(), "do-while")
        return None

    def entrar_bucle(self, block):
        self.bucles += 1
        self.rompibles += 1
        self.visit(block)
        self.bucles -= 1
        self.rompibles -= 1

    def visitForStatement(self, ctx):
        self.contador_bloques += 1
        self.tabla.abrir_ambito("for{}".format(self.contador_bloques), "bucle")
        seccion = 0
        for hijo in ctx.children:
            if isinstance(hijo, CompiscriptParser.VariableDeclarationContext):
                self.visit(hijo)
                seccion = 1
            elif isinstance(hijo, CompiscriptParser.AssignmentContext):
                self.visit(hijo)
                seccion = 1
            elif isinstance(hijo, CompiscriptParser.ExpressionContext):
                if seccion == 1:
                    self.condicion(hijo, "for")
                else:
                    self.visit(hijo)
            elif isinstance(hijo, TerminalNode) and hijo.getText() == ";":
                seccion += 1
        self.entrar_bucle(ctx.block())
        self.tabla.cerrar_ambito()
        return None

    def visitForeachStatement(self, ctx):
        iterable = self.visit(ctx.expression())
        if isinstance(iterable, TipoArreglo):
            elemento = iterable.elemento
        elif es_error(iterable):
            elemento = ERROR
        else:
            elemento = self.error("E107", "'foreach' requiere un arreglo, se encontro {}".format(iterable), ctx)
        self.contador_bloques += 1
        self.tabla.abrir_ambito("foreach{}".format(self.contador_bloques), "bucle")
        simbolo = Simbolo(ctx.Identifier().getText(), "variable", elemento, ctx.start.line, ctx.start.column)
        simbolo.inicializado = True
        ctx.simbolo = simbolo
        self.declarar(simbolo, ctx)
        self.entrar_bucle(ctx.block())
        self.tabla.cerrar_ambito()
        return None

    def visitBreakStatement(self, ctx):
        if self.rompibles == 0:
            self.error("E401", "'break' solo puede usarse dentro de un bucle o un switch", ctx)
        return None

    def visitContinueStatement(self, ctx):
        if self.bucles == 0:
            self.error("E402", "'continue' solo puede usarse dentro de un bucle", ctx)
        return None

    def visitReturnStatement(self, ctx):
        valor = self.visit(ctx.expression()) if ctx.expression() is not None else VACIO
        if not self.funciones:
            self.error("E403", "'return' solo puede usarse dentro de una funcion", ctx)
            return None
        marco = self.funciones[-1]
        marco["tiene_return"] = True
        esperado = marco["retorno"]
        if esperado == VACIO and valor != VACIO:
            self.error("E302", "la funcion '{}' no declara tipo de retorno".format(marco["nombre"]), ctx)
        elif esperado != VACIO and not compatible(esperado, valor):
            self.error("E302", "la funcion '{}' debe retornar {}, se encontro {}".format(
                marco["nombre"], esperado, valor), ctx)
        return None

    def visitTryCatchStatement(self, ctx):
        self.visit(ctx.block(0))
        self.contador_bloques += 1
        self.tabla.abrir_ambito("catch{}".format(self.contador_bloques), "bloque")
        simbolo = Simbolo(ctx.Identifier().getText(), "variable", CADENA, ctx.start.line, ctx.start.column)
        simbolo.inicializado = True
        ctx.simbolo = simbolo
        self.declarar(simbolo, ctx)
        self.visit(ctx.block(1))
        self.tabla.cerrar_ambito()
        return None

    def visitSwitchStatement(self, ctx):
        control = self.visit(ctx.expression())
        self.rompibles += 1
        for caso in ctx.switchCase():
            etiqueta = self.visit(caso.expression())
            if not comparables(control, etiqueta):
                self.error("E404", "el case de tipo {} no es comparable con el switch de tipo {}".format(
                    etiqueta, control), caso)
            self.ambito_de_caso(caso.statement(), "case")
        if ctx.defaultCase() is not None:
            self.ambito_de_caso(ctx.defaultCase().statement(), "default")
        self.rompibles -= 1
        return None

    def ambito_de_caso(self, statements, nombre):
        self.contador_bloques += 1
        self.tabla.abrir_ambito("{}{}".format(nombre, self.contador_bloques), "bloque")
        self.cuerpo(statements)
        self.tabla.cerrar_ambito()

    def visitFunctionDeclaration(self, ctx):
        nombre = ctx.Identifier().getText()
        simbolo = self.tabla.buscar_local(nombre)
        if simbolo is None or simbolo.categoria not in ("funcion", "metodo"):
            simbolo = self.firma_funcion(ctx)
        entorno = self.tabla.abrir_ambito(nombre, "funcion")
        simbolo.etiqueta = entorno.ruta()[len("global."):]
        simbolo.nivel_funcion = len(self.funciones) + 1
        ctx.simbolo = simbolo
        ctx.entorno = entorno
        ctx.parametros_simbolos = []
        vistos = set()
        for nombre_param, tipo_param in simbolo.parametros:
            if nombre_param in vistos:
                self.error("E602", "el parametro '{}' esta duplicado".format(nombre_param), ctx)
                continue
            vistos.add(nombre_param)
            parametro = Simbolo(nombre_param, "parametro", tipo_param, ctx.start.line, ctx.start.column)
            parametro.inicializado = True
            self.tabla.declarar(parametro)
            ctx.parametros_simbolos.append(parametro)
        self.funciones.append({"nombre": nombre, "retorno": simbolo.retorno,
                               "tiene_return": False, "entorno": entorno, "simbolo": simbolo})
        self.cuerpo(ctx.block().statement())
        marco = self.funciones.pop()
        self.tabla.cerrar_ambito()
        if simbolo.retorno != VACIO and not marco["tiene_return"]:
            self.error("E305", "la funcion '{}' debe retornar un valor {}".format(nombre, simbolo.retorno), ctx)
        return None

    def visitClassDeclaration(self, ctx):
        nombre = ctx.Identifier(0).getText()
        info = self.tabla.clases.get(nombre)
        if info is None:
            return None
        entorno = self.tabla.abrir_ambito(nombre, "clase")
        info.entorno = entorno
        ctx.info = info
        for atributo in info.atributos.values():
            self.tabla.declarar(atributo)
        for metodo in info.metodos.values():
            self.tabla.declarar(metodo)
        self.clases.append(info)
        for miembro in ctx.classMember():
            if miembro.functionDeclaration() is not None:
                self.visit(miembro.functionDeclaration())
            elif miembro.variableDeclaration() is not None:
                d = miembro.variableDeclaration()
                if d.initializer() is not None:
                    valor = self.visit(d.initializer().expression())
                    declarado = info.atributos[d.Identifier().getText()].tipo
                    if not compatible(declarado, valor):
                        self.error("E104", "no se puede inicializar '{}' de tipo {} con un valor {}".format(
                            d.Identifier().getText(), declarado, valor), d)
            else:
                d = miembro.constantDeclaration()
                valor = self.visit(d.expression())
                declarado = info.atributos[d.Identifier().getText()].tipo
                if not compatible(declarado, valor):
                    self.error("E104", "no se puede inicializar la constante '{}' de tipo {} con un valor {}".format(
                        d.Identifier().getText(), declarado, valor), d)
        self.clases.pop()
        self.tabla.cerrar_ambito()
        return None

    def visitExpression(self, ctx):
        return self.visit(ctx.assignmentExpr())

    def visitExprNoAssign(self, ctx):
        return self.visit(ctx.conditionalExpr())

    def visitAssignExpr(self, ctx):
        destino = self.visit(ctx.lhs)
        simbolo = self.simbolo_lhs
        valor = self.visit(ctx.assignmentExpr())
        if simbolo is not None:
            return self.asignar_identificador(simbolo.nombre, valor, ctx)
        if not compatible(destino, valor):
            return self.error("E103", "no se puede asignar un valor {} a un destino de tipo {}".format(
                valor, destino), ctx)
        return destino

    def visitPropertyAssignExpr(self, ctx):
        objeto = self.visit(ctx.lhs)
        valor = self.visit(ctx.assignmentExpr())
        return self.asignar_propiedad(objeto, ctx.Identifier().getText(), valor, ctx)

    def visitTernaryExpr(self, ctx):
        condicion = self.visit(ctx.logicalOrExpr())
        if ctx.expression() is None or len(ctx.expression()) == 0:
            return condicion
        if not es_error(condicion) and condicion != BOOLEANO:
            self.error("E400", "la condicion del operador ternario debe ser boolean, se encontro {}".format(
                condicion), ctx)
        izquierda = self.visit(ctx.expression(0))
        derecha = self.visit(ctx.expression(1))
        resultado = unificar(izquierda, derecha)
        if es_error(resultado) and not es_error(izquierda) and not es_error(derecha):
            return self.error("E102", "las ramas del ternario tienen tipos incompatibles: {} y {}".format(
                izquierda, derecha), ctx)
        return resultado

    def operandos_logicos(self, ctx, subregla):
        partes = getattr(ctx, subregla)()
        tipos = [self.visit(p) for p in partes]
        if len(partes) == 1:
            return tipos[0]
        for tipo, parte in zip(tipos, partes):
            if not es_error(tipo) and tipo != BOOLEANO:
                self.error("E101", "los operadores logicos requieren boolean, se encontro {}".format(tipo), parte)
        return BOOLEANO

    def visitLogicalOrExpr(self, ctx):
        return self.operandos_logicos(ctx, "logicalAndExpr")

    def visitLogicalAndExpr(self, ctx):
        return self.operandos_logicos(ctx, "equalityExpr")

    def visitEqualityExpr(self, ctx):
        partes = ctx.relationalExpr()
        tipos = [self.visit(p) for p in partes]
        if len(partes) == 1:
            return tipos[0]
        for i in range(len(tipos) - 1):
            if not comparables(tipos[i], tipos[i + 1]):
                self.error("E102", "no se pueden comparar valores {} y {}".format(tipos[i], tipos[i + 1]), ctx)
        return BOOLEANO

    def visitRelationalExpr(self, ctx):
        partes = ctx.additiveExpr()
        tipos = [self.visit(p) for p in partes]
        if len(partes) == 1:
            return tipos[0]
        for i in range(len(tipos) - 1):
            a, b = tipos[i], tipos[i + 1]
            if es_error(a) or es_error(b):
                continue
            if (es_numerico(a) and es_numerico(b)) or (a == CADENA and b == CADENA):
                continue
            self.error("E102", "no se pueden ordenar valores {} y {}".format(a, b), ctx)
        return BOOLEANO

    def revisar_operando(self, tipo, operador, ctx):
        if isinstance(tipo, TipoFuncion):
            return self.error("E601", "no se puede usar una funcion como operando de '{}'".format(operador), ctx)
        return tipo

    def visitAdditiveExpr(self, ctx):
        partes = ctx.multiplicativeExpr()
        resultado = self.visit(partes[0])
        for i in range(1, len(partes)):
            operador = ctx.getChild(2 * i - 1).getText()
            derecha = self.visit(partes[i])
            resultado = self.revisar_operando(resultado, operador, ctx)
            derecha = self.revisar_operando(derecha, operador, ctx)
            if es_error(resultado) or es_error(derecha):
                resultado = ERROR
            elif operador == "+" and (resultado == CADENA or derecha == CADENA):
                resultado = CADENA
            elif es_numerico(resultado) and es_numerico(derecha):
                resultado = unificar(resultado, derecha)
            else:
                resultado = self.error("E100", "el operador '{}' requiere valores numericos, se encontro {} y {}".format(
                    operador, resultado, derecha), ctx)
        return resultado

    def visitMultiplicativeExpr(self, ctx):
        partes = ctx.unaryExpr()
        resultado = self.visit(partes[0])
        for i in range(1, len(partes)):
            operador = ctx.getChild(2 * i - 1).getText()
            derecha = self.visit(partes[i])
            resultado = self.revisar_operando(resultado, operador, ctx)
            derecha = self.revisar_operando(derecha, operador, ctx)
            if es_error(resultado) or es_error(derecha):
                resultado = ERROR
            elif operador == "%":
                if resultado == ENTERO and derecha == ENTERO:
                    resultado = ENTERO
                else:
                    resultado = self.error("E109", "el operador '%' requiere integer, se encontro {} y {}".format(
                        resultado, derecha), ctx)
            elif es_numerico(resultado) and es_numerico(derecha):
                resultado = unificar(resultado, derecha)
            else:
                resultado = self.error("E100", "el operador '{}' requiere valores numericos, se encontro {} y {}".format(
                    operador, resultado, derecha), ctx)
        return resultado

    def visitUnaryExpr(self, ctx):
        if ctx.primaryExpr() is not None:
            return self.visit(ctx.primaryExpr())
        operador = ctx.getChild(0).getText()
        tipo = self.visit(ctx.unaryExpr())
        if es_error(tipo):
            return ERROR
        if operador == "-":
            if not es_numerico(tipo):
                return self.error("E108", "el operador '-' requiere un valor numerico, se encontro {}".format(tipo), ctx)
            return tipo
        if tipo != BOOLEANO:
            return self.error("E101", "el operador '!' requiere boolean, se encontro {}".format(tipo), ctx)
        return BOOLEANO

    def visitPrimaryExpr(self, ctx):
        if ctx.literalExpr() is not None:
            return self.visit(ctx.literalExpr())
        if ctx.leftHandSide() is not None:
            return self.visit(ctx.leftHandSide())
        return self.visit(ctx.expression())

    def visitLiteralExpr(self, ctx):
        if ctx.arrayLiteral() is not None:
            return self.visit(ctx.arrayLiteral())
        texto = ctx.getText()
        if texto == "null":
            return NULO
        if texto in ("true", "false"):
            return BOOLEANO
        if texto.startswith('"'):
            return CADENA
        if "." in texto:
            return FLOTANTE
        return ENTERO

    def visitArrayLiteral(self, ctx):
        elementos = ctx.expression()
        if not elementos:
            return TipoArreglo(ERROR)
        tipos = [self.visit(e) for e in elementos]
        comun = tipos[0]
        for tipo in tipos[1:]:
            unido = unificar(comun, tipo)
            if es_error(unido) and not es_error(comun) and not es_error(tipo):
                self.error("E105", "la lista mezcla elementos {} y {}".format(comun, tipo), ctx)
                return TipoArreglo(ERROR)
            comun = unido
        return TipoArreglo(comun)

    def visitLeftHandSide(self, ctx):
        tipo = self.visit(ctx.primaryAtom())
        simbolo = self.simbolo_atomo
        sufijos = ctx.suffixOp()
        if not sufijos:
            self.simbolo_lhs = simbolo
            return tipo
        self.simbolo_lhs = None
        for sufijo in sufijos:
            sufijo.tipo_previo = tipo
            tipo = self.aplicar_sufijo(tipo, sufijo)
            sufijo.tipo = tipo
        return tipo

    def aplicar_sufijo(self, tipo, sufijo):
        if isinstance(sufijo, CompiscriptParser.CallExprContext):
            argumentos = sufijo.arguments().expression() if sufijo.arguments() is not None else []
            tipos = [self.visit(a) for a in argumentos]
            if es_error(tipo):
                return ERROR
            if not isinstance(tipo, TipoFuncion):
                return self.error("E304", "no se puede llamar a un valor de tipo {}".format(tipo), sufijo)
            return self.revisar_argumentos(tipo.parametros, tipos, tipo.retorno, "la funcion", sufijo)
        if isinstance(sufijo, CompiscriptParser.IndexExprContext):
            indice = self.visit(sufijo.expression())
            if not es_error(indice) and indice != ENTERO:
                self.error("E106", "el indice de un arreglo debe ser integer, se encontro {}".format(indice), sufijo)
            if es_error(tipo):
                return ERROR
            if not isinstance(tipo, TipoArreglo):
                return self.error("E107", "no se puede indexar un valor de tipo {}".format(tipo), sufijo)
            return tipo.elemento
        nombre = sufijo.Identifier().getText()
        if es_error(tipo):
            return ERROR
        if not isinstance(tipo, TipoClase):
            return self.error("E504", "no se puede acceder a '.{}' sobre un valor {}".format(nombre, tipo), sufijo)
        miembro = tipo.info.buscar_miembro(nombre)
        if miembro is None:
            return self.error("E501", "la clase '{}' no tiene el miembro '{}'".format(tipo.nombre, nombre), sufijo)
        sufijo.miembro = miembro
        return miembro.tipo

    def revisar_argumentos(self, esperados, recibidos, retorno, descripcion, ctx):
        if len(esperados) != len(recibidos):
            codigo = "E502" if descripcion == "el constructor" else "E300"
            return self.error(codigo, "{} espera {} argumentos y recibio {}".format(
                descripcion, len(esperados), len(recibidos)), ctx)
        for i, (esperado, recibido) in enumerate(zip(esperados, recibidos)):
            if not compatible(esperado, recibido):
                codigo = "E502" if descripcion == "el constructor" else "E301"
                self.error(codigo, "el argumento {} de {} debe ser {}, se encontro {}".format(
                    i + 1, descripcion, esperado, recibido), ctx)
        return retorno

    def visitIdentifierExpr(self, ctx):
        nombre = ctx.Identifier().getText()
        simbolo = self.tabla.buscar(nombre)
        self.simbolo_atomo = simbolo
        ctx.simbolo = simbolo
        if simbolo is None:
            return self.error("E200", "'{}' no esta declarado".format(nombre), ctx)
        self.registrar_captura(nombre, simbolo)
        return simbolo.tipo

    def registrar_captura(self, nombre, simbolo):
        if not self.funciones:
            return
        entorno = self.tabla.entorno_de(nombre)
        marco = self.funciones[-1]
        if entorno is None or entorno.nivel >= marco["entorno"].nivel or entorno.padre is None:
            return
        if nombre not in marco["simbolo"].capturadas:
            marco["simbolo"].capturadas.append(nombre)

    def visitNewExpr(self, ctx):
        self.simbolo_atomo = None
        nombre = ctx.Identifier().getText()
        argumentos = ctx.arguments().expression() if ctx.arguments() is not None else []
        tipos = [self.visit(a) for a in argumentos]
        info = self.tabla.clases.get(nombre)
        ctx.info = info
        if info is None:
            return self.error("E500", "la clase '{}' no esta declarada".format(nombre), ctx)
        constructor = info.constructor()
        esperados = [t for _, t in constructor.parametros] if constructor is not None else []
        self.revisar_argumentos(esperados, tipos, None, "el constructor", ctx)
        return TipoClase(nombre, info)

    def visitThisExpr(self, ctx):
        self.simbolo_atomo = None
        if not self.clases:
            return self.error("E503", "'this' solo puede usarse dentro de una clase", ctx)
        info = self.clases[-1]
        return TipoClase(info.nombre, info)
