"""Traduccion de TAC a ensamblador MIPS32 (sintaxis MARS).

`generar_mips(programa, tabla, modo)` devuelve el texto de un archivo .asm completo.
  modo = "registros": getReg con descriptores (registros.AsignadorRegistros), el modo por omision.
  modo = "pila":      toda operacion pasa por la pila (registros.AsignadorPila).
La secuencia de llamada y retorno esta descrita en marco.py y en docs/GENERACION_MIPS.md.
"""
import re

from tac import RELACIONALES
from temporales import es_temporal
from . import runtime
from .bloques import AnalisisFuncion, variables_capturadas, asignar_s
from .marco import Marco
from .operandos import Tipador, clasificar, clase_tipo, leer_escribir
from .registros import AsignadorPila, AsignadorRegistros

NOMBRE_RAMA = {"<": "blt", "<=": "ble", ">": "bgt", ">=": "bge", "==": "beq", "!=": "bne"}
CLASE_ELEMENTO = {"int": 0, "?": 0, "float": 1, "str": 2, "bool": 3, "obj": 4}


def codigo_elemento(tipo_arreglo):
    """Codigo que entiende __valstr para los elementos de un arreglo: clase base + 8 por nivel de anidacion."""
    t = tipo_arreglo[:-2] if tipo_arreglo else None
    profundidad = 0
    while t and t.endswith("[]"):
        profundidad += 1
        t = t[:-2]
    return 8 * profundidad + CLASE_ELEMENTO.get(clase_tipo(t), 5)


def etiqueta_funcion(etiqueta):
    return "f_" + re.sub(r"[^A-Za-z0-9_]", lambda m: {".": "__", "$": "S_"}.get(m.group(), "_"), etiqueta)


def cabe16(valor):
    return -32768 <= valor <= 32767


class ContextoPrograma:
    """Informacion que comparten todas las funciones: cadenas, clases, tablas virtuales, marcos."""

    def __init__(self, programa, tabla, modo):
        self.programa = programa
        self.tabla = tabla
        self.modo = modo
        self.cadenas = {}
        self.descriptores = set()
        self.rutinas = set()
        self.contador = 0
        self.tipador = Tipador(programa)
        self.funciones = {f.etiqueta: f for f in programa.funciones}
        self.analisis = {f.etiqueta: AnalisisFuncion(f) for f in programa.funciones}
        capturadas = variables_capturadas(programa)
        self.marcos = {}
        for f in programa.funciones:
            an = self.analisis[f.etiqueta]
            s = asignar_s(f, an, capturadas) if modo == "registros" else {}
            self.marcos[f.etiqueta] = Marco(f, s, an.usa_try)
        nombres = sorted({m for t in programa.vtables.values() for m in t})
        self.slot_metodo = {m: k for k, m in enumerate(nombres)}
        self.globales = set(programa.tipos_globales)
        for f in programa.funciones:
            for i in f.instrucciones:
                leidos, escrito = leer_escribir(i)
                for op in leidos + ([escrito] if escrito else []):
                    if clasificar(op)[0] == "global":
                        self.globales.add(op)

    def etiqueta_nueva(self, base="__e"):
        self.contador += 1
        return "{}{}".format(base, self.contador)

    def cadena(self, texto):
        if texto not in self.cadenas:
            self.cadenas[texto] = "str_{}".format(len(self.cadenas))
        return self.cadenas[texto]

    def campos(self, nombre_clase):
        info = self.tabla.clases.get(nombre_clase)
        cadena = []
        while info is not None:
            cadena.append(info)
            info = info.padre
        nombres = []
        for c in reversed(cadena):
            nombres.extend(c.atributos.keys())
        return nombres

    def offset_campo(self, nombre_clase, campo):
        nombres = self.campos(nombre_clase) if nombre_clase in self.tabla.clases else []
        if campo in nombres:
            return 4 + 4 * nombres.index(campo)
        for clase in self.tabla.clases:           # tipo desconocido: busca la clase que lo declara
            nombres = self.campos(clase)
            if campo in nombres:
                return 4 + 4 * nombres.index(campo)
        raise KeyError("campo desconocido " + campo)

    def tamano_objeto(self, nombre_clase):
        return 4 + 4 * len(self.campos(nombre_clase))


class EmisorFuncion:
    def __init__(self, ctx, funcion):
        self.ctx = ctx
        self.f = funcion
        self.marco = ctx.marcos[funcion.etiqueta]
        self.an = ctx.analisis[funcion.etiqueta]
        self.tipos = ctx.tipador.tipar(funcion)
        self.salida = []
        self.k = 0
        if ctx.modo == "pila":
            self.a = AsignadorPila(self)
        else:
            self.a = AsignadorRegistros(self, self.an, self.marco.s_asignadas, self.an.usa_try)
        self.etq_ret = etiqueta_funcion(funcion.etiqueta) + "_ret"

    # ---------------------------------------------------------------- salida de texto
    def e(self, texto):
        self.salida.append("    " + texto)

    def etiqueta(self, nombre):
        self.salida.append(nombre + ":")

    # ---------------------------------------------------------------- acceso a memoria
    def dueno(self, saltos):
        f = self.f
        for _ in range(saltos):
            f = self.ctx.funciones[f.registro.padre.etiqueta]
        return f

    def cargar(self, reg, op):
        """Deja el valor del operando en `reg`."""
        c = clasificar(op)
        if c[0] == "const":
            if c[1] == "str":
                self.e("la   {}, {}".format(reg, self.ctx.cadena(c[2])))
            else:
                self.e("li   {}, {}".format(reg, c[2]))
        elif c[0] == "global":
            self.e("lw   {}, g_{}".format(reg, c[1][1:]))
        elif c[2] == 0:
            nombre = c[1]
            s = self.marco.s_asignadas.get(nombre)
            if s:
                self.e("move {}, {}".format(reg, s))
            else:
                self.e("lw   {}, {}($fp)".format(reg, self.marco.offset(nombre)))
        else:
            self.subir_enlaces(reg, c[2])
            dueno = self.ctx.marcos[self.dueno(c[2]).etiqueta]
            self.e("lw   {}, {}({})".format(reg, dueno.offset(c[1]), reg))

    def subir_enlaces(self, reg, saltos):
        """Deja en `reg` el $fp de la funcion que esta `saltos` enlaces de acceso arriba."""
        self.e("lw   {}, -12($fp)".format(reg))
        for _ in range(saltos - 1):
            self.e("lw   {}, -12({})".format(reg, reg))

    def guardar(self, reg, op):
        """Guarda `reg` en la ubicacion del operando."""
        c = clasificar(op)
        if c[0] == "global":
            self.e("sw   {}, g_{}".format(reg, c[1][1:]))
        elif c[2] == 0:
            nombre = c[1]
            s = self.marco.s_asignadas.get(nombre)
            if s:
                if s != reg:
                    self.e("move {}, {}".format(s, reg))
            else:
                self.e("sw   {}, {}($fp)".format(reg, self.marco.offset(nombre)))
        else:
            self.subir_enlaces("$t8", c[2])
            dueno = self.ctx.marcos[self.dueno(c[2]).etiqueta]
            self.e("sw   {}, {}($t8)".format(reg, dueno.offset(c[1])))

    def guardar_casilla(self, reg, nombre):
        self.e("sw   {}, {}($fp)".format(reg, self.marco.offset(nombre)))

    # ---------------------------------------------------------------- tipos
    def clases(self, k):
        ta, tb, tr = self.tipos[k]
        return clase_tipo(ta), clase_tipo(tb), clase_tipo(tr), ta, tb, tr

    def nombre_local(self, op):
        c = clasificar(op)
        return c[1] if c[0] == "var" and c[2] == 0 else None

    def entero_inmediato(self, op):
        c = clasificar(op)
        if c[0] == "const" and c[1] in ("int", "bool") and cabe16(c[2]):
            return c[2]
        return None

    # ---------------------------------------------------------------- funcion completa
    def generar(self):
        nombre = etiqueta_funcion(self.f.etiqueta)
        m = self.marco
        self.salida.append("")
        self.salida.append("# {}  (marco = {} bytes, {} parametros)".format(self.f.etiqueta, m.tamano, len(m.parametros)))
        self.etiqueta(nombre)
        F = m.tamano
        self.e("addiu $sp, $sp, -{}".format(F))
        self.e("sw   $ra, {}($sp)".format(F - 4))
        self.e("sw   $fp, {}($sp)".format(F - 8))
        self.e("sw   $v1, {}($sp)".format(F - 12))
        self.e("addiu $fp, $sp, {}".format(F))
        for r in m.s_usadas:
            self.e("sw   {}, {}($fp)".format(r, m.offset_s[r]))
        if m.usa_try:
            self.e("lw   $t8, exc_n")
            self.e("sw   $t8, {}($fp)".format(m.offset_exc))
        instrucciones = self.f.instrucciones
        for k, i in enumerate(instrucciones):
            self.k = k
            self.a.inicio(k, self.nombre_local(i.res))
            self.salida.append("    # " + str(i) if i.op != "label" else "")
            self.instruccion(i, k, k == len(instrucciones) - 1)
            self.a.fin()
        self.etiqueta(self.etq_ret)
        if m.usa_try:
            self.e("lw   $t8, {}($fp)".format(m.offset_exc))
            self.e("sw   $t8, exc_n")
        for r in m.s_usadas:
            self.e("lw   {}, {}($fp)".format(r, m.offset_s[r]))
        self.e("lw   $ra, -4($fp)")
        self.e("move $sp, $fp")
        self.e("lw   $fp, -8($fp)")
        self.e("jr   $ra")
        return "\n".join(l for l in self.salida if l is not None)

    # ---------------------------------------------------------------- instrucciones
    def instruccion(self, i, k, ultima):
        op = i.op
        a = self.a
        if op == "label":
            a.vaciar()
            self.etiqueta(i.res)
        elif op == "goto":
            a.vaciar()
            self.e("j    {}".format(i.res))
        elif op in ("if", "iffalse"):
            r = a.usar(i.arg1)
            a.vaciar()
            self.e("{} {}, {}".format("bnez" if op == "if" else "beqz", r, i.res))
        elif op.startswith("if"):
            self.salto_relacional(i, k)
        elif op == "copy":
            self.copiar(i)
        elif op in ("+", "-", "*", "/", "%"):
            self.aritmetica(i, k)
        elif op in RELACIONALES:
            self.comparacion(i, k)
        elif op in ("neg", "not", "itof", "len"):
            self.unaria(i, k)
        elif op == "param":
            r = a.usar(i.arg1)
            self.e("addiu $sp, $sp, -4")
            self.e("sw   {}, 0($sp)".format(r))
        elif op in ("call", "callind", "callv"):
            self.llamada(i, k)
        elif op == "return":
            if i.arg1 is not None:
                r = a.usar(i.arg1)
                if r != "$v0":
                    self.e("move $v0, {}".format(r))
            a.vaciar(guardar=False)
            if not ultima:
                self.e("j    {}".format(self.etq_ret))
        elif op == "addr":
            self.ctx.descriptores.add(i.arg1)
            a.liberar_operandos([], i.res)
            r = a.definir(i.res)
            self.e("la   {}, fd_{}".format(r, etiqueta_funcion(i.arg1)[2:]))
            a.terminar(i.res, r)
        elif op == "newarray":
            self.nuevo_arreglo(i)
        elif op in ("aload", "astore"):
            self.acceso_arreglo(i, k)
        elif op == "new":
            self.nuevo_objeto(i)
        elif op in ("getf", "putf"):
            self.acceso_campo(i, k)
        elif op == "tostr":
            self.convertir_cadena(i, k)
        elif op == "concat":
            ra = a.usar(i.arg1)
            rb = a.usar(i.arg2)
            self.rutina("__concat", [ra, rb], i.res)
        elif op == "print":
            self.imprimir(i, k)
        elif op == "pushtry":
            a.vaciar(fin_de_bloque=False)
            self.e("la   $a0, {}".format(i.res))
            self.ctx.rutinas.add("__pushtry")
            self.e("jal  __pushtry")
        elif op == "poptry":
            self.e("lw   $t8, exc_n")
            self.e("addiu $t8, $t8, -1")
            self.e("sw   $t8, exc_n")
        elif op == "getexc":
            a.liberar_operandos([], i.res)
            r = a.definir(i.res)
            self.e("lw   {}, exc_msg".format(r))
            a.terminar(i.res, r)
        else:
            raise ValueError("operacion sin traduccion a MIPS: " + op)

    def rutina(self, nombre, regs, res=None):
        """Llama a una rutina del runtime con los valores en $a0.. y deja el resultado en `res`."""
        for n, r in enumerate(regs):
            self.e("move $a{}, {}".format(n, r))
        self.a.vaciar(fin_de_bloque=False)
        self.ctx.rutinas.add(nombre)
        self.e("jal  {}".format(nombre))
        if res is not None:
            r = self.a.definir(res)
            self.e("move {}, $v0".format(r))
            self.a.terminar(res, r)

    def lanzar(self, mensaje):
        self.ctx.rutinas.add("__throw")
        self.e("la   $a0, {}".format(mensaje))
        self.e("j    __throw")

    # ---------------------------------------------------------------- copia y aritmetica
    def copiar(self, i):
        a = self.a
        c = clasificar(i.arg1)
        if c[0] == "const":
            a.liberar_operandos([], i.res)
            rd = a.definir(i.res)
            self.cargar(rd, i.arg1)
        else:
            rs = a.usar(i.arg1)
            a.liberar_operandos([i.arg1], i.res)
            rd = a.definir(i.res)
            if rd != rs:
                self.e("move {}, {}".format(rd, rs))
        a.terminar(i.res, rd)

    def aritmetica(self, i, k):
        a = self.a
        op = i.op
        ca, cb, cr, ta, tb, tr = self.clases(k)
        if "float" in (ca, cb):
            return self.aritmetica_float(i, k)
        x, y = i.arg1, i.arg2
        if op in ("+", "*") and self.entero_inmediato(x) is not None and self.entero_inmediato(y) is None:
            x, y = y, x
        imm = self.entero_inmediato(y)
        rx = a.usar(x)
        if op in ("+", "-") and imm is not None and cabe16(imm if op == "+" else -imm):
            a.liberar_operandos([x], i.res)
            rd = a.definir(i.res)
            self.e("addiu {}, {}, {}".format(rd, rx, imm if op == "+" else -imm))
            return a.terminar(i.res, rd)
        ry = a.usar(y)
        if op in ("/", "%"):
            if not (imm is not None and imm != 0):
                ok = self.ctx.etiqueta_nueva()
                self.e("bnez {}, {}".format(ry, ok))
                self.lanzar("msg_div")
                self.etiqueta(ok)
        a.liberar_operandos([x, y], i.res)
        rd = a.definir(i.res)
        if op == "+":
            self.e("addu {}, {}, {}".format(rd, rx, ry))
        elif op == "-":
            self.e("subu {}, {}, {}".format(rd, rx, ry))
        elif op == "*":
            self.e("mul  {}, {}, {}".format(rd, rx, ry))
        else:
            self.e("div  {}, {}".format(rx, ry))
            self.e("{} {}".format("mflo" if op == "/" else "mfhi", rd))
        a.terminar(i.res, rd)

    def a_float(self, reg, f):
        self.e("mtc1 {}, {}".format(reg, f))

    def aritmetica_float(self, i, k):
        a = self.a
        rx = a.usar(i.arg1)
        ry = a.usar(i.arg2)
        self.a_float(rx, "$f4")
        self.a_float(ry, "$f6")
        if i.op == "/":
            ok = self.ctx.etiqueta_nueva()
            self.e("mtc1 $zero, $f8")
            self.e("c.eq.s $f6, $f8")
            self.e("bc1f {}".format(ok))
            self.lanzar("msg_div")
            self.etiqueta(ok)
        mnemonico = {"+": "add.s", "-": "sub.s", "*": "mul.s", "/": "div.s"}[i.op]
        self.e("{} $f8, $f4, $f6".format(mnemonico))
        a.liberar_operandos([i.arg1, i.arg2], i.res)
        rd = a.definir(i.res)
        self.e("mfc1 {}, $f8".format(rd))
        a.terminar(i.res, rd)

    def es_cadena_igualdad(self, ca, cb):
        return "str" in (ca, cb) and "null" not in (ca, cb)

    def comparacion(self, i, k):
        a = self.a
        op = i.op
        ca, cb, cr, ta, tb, tr = self.clases(k)
        rx = a.usar(i.arg1)
        ry = a.usar(i.arg2)
        if op in ("==", "!=") and self.es_cadena_igualdad(ca, cb):
            self.rutina("__strcmp", [rx, ry])
            if op == "!=":
                self.e("xori $v0, $v0, 1")
            rd = a.definir(i.res)
            self.e("move {}, $v0".format(rd))
            return a.terminar(i.res, rd)
        if "float" in (ca, cb):
            self.a_float(rx, "$f4")
            self.a_float(ry, "$f6")
            a.liberar_operandos([i.arg1, i.arg2], i.res)
            rd = a.definir(i.res)
            fin = self.ctx.etiqueta_nueva()
            comp, invertir = self.comparador_float(op)
            valor, otro = (0, 1) if invertir else (1, 0)
            self.e("li   {}, {}".format(rd, valor))
            self.e(comp)
            self.e("bc1t {}".format(fin))
            self.e("li   {}, {}".format(rd, otro))
            self.etiqueta(fin)
            return a.terminar(i.res, rd)
        a.liberar_operandos([i.arg1, i.arg2], i.res)
        rd = a.definir(i.res)
        pseudo = {"<": "slt", "<=": "sle", ">": "sgt", ">=": "sge", "==": "seq", "!=": "sne"}[op]
        self.e("{} {}, {}, {}".format(pseudo, rd, rx, ry))
        a.terminar(i.res, rd)

    def comparador_float(self, op):
        """(instruccion c.xx.s, invertir): despues de ella bc1t salta si la relacion es cierta."""
        if op == "<":
            return "c.lt.s $f4, $f6", False
        if op == "<=":
            return "c.le.s $f4, $f6", False
        if op == ">":
            return "c.lt.s $f6, $f4", False
        if op == ">=":
            return "c.le.s $f6, $f4", False
        if op == "==":
            return "c.eq.s $f4, $f6", False
        return "c.eq.s $f4, $f6", True

    def salto_relacional(self, i, k):
        a = self.a
        op = i.op[2:]
        ca, cb, cr, ta, tb, tr = self.clases(k)
        if op in ("==", "!=") and self.es_cadena_igualdad(ca, cb):
            rx = a.usar(i.arg1)
            ry = a.usar(i.arg2)
            self.rutina("__strcmp", [rx, ry])
            self.e("{} $v0, {}".format("bnez" if op == "==" else "beqz", i.res))
            return
        if "float" in (ca, cb):
            rx = a.usar(i.arg1)
            ry = a.usar(i.arg2)
            self.a_float(rx, "$f4")
            self.a_float(ry, "$f6")
            a.vaciar()
            comp, invertir = self.comparador_float(op)
            self.e(comp)
            self.e("{} {}".format("bc1f" if invertir else "bc1t", i.res))
            return
        rx = a.usar(i.arg1)
        imm = self.entero_inmediato(i.arg2)
        if imm is not None:
            a.vaciar()
            self.e("{} {}, {}, {}".format(NOMBRE_RAMA[op], rx, imm, i.res))
            return
        ry = a.usar(i.arg2)
        a.vaciar()
        self.e("{} {}, {}, {}".format(NOMBRE_RAMA[op], rx, ry, i.res))

    def unaria(self, i, k):
        a = self.a
        op = i.op
        ca, cb, cr, ta, tb, tr = self.clases(k)
        if op == "len":
            rx = a.usar(i.arg1)
            a.liberar_operandos([i.arg1], i.res)
            rd = a.definir(i.res)
            self.e("lw   {}, 0({})".format(rd, rx))
            return a.terminar(i.res, rd)
        rx = a.usar(i.arg1)
        if op == "itof":
            self.a_float(rx, "$f4")
            self.e("cvt.s.w $f4, $f4")
            a.liberar_operandos([i.arg1], i.res)
            rd = a.definir(i.res)
            self.e("mfc1 {}, $f4".format(rd))
        elif op == "neg" and ca == "float":
            self.a_float(rx, "$f4")
            self.e("neg.s $f4, $f4")
            a.liberar_operandos([i.arg1], i.res)
            rd = a.definir(i.res)
            self.e("mfc1 {}, $f4".format(rd))
        else:
            a.liberar_operandos([i.arg1], i.res)
            rd = a.definir(i.res)
            if op == "neg":
                self.e("subu {}, $zero, {}".format(rd, rx))
            else:
                self.e("xori {}, {}, 1".format(rd, rx))
        a.terminar(i.res, rd)

    # ---------------------------------------------------------------- llamadas
    def enlace_directo(self, destino):
        """Deja en $v1 el enlace de acceso para llamar a la funcion `destino`."""
        nivel_destino = destino.registro.nivel
        saltos = self.f.registro.nivel - (nivel_destino - 1)
        self.e("move $v1, $fp")
        for _ in range(max(saltos, 0)):
            self.e("lw   $v1, -12($v1)")

    def llamada(self, i, k):
        a = self.a
        n = int(i.arg2)
        if i.op == "call":
            destino = self.ctx.funciones[i.arg1]
            a.vaciar(fin_de_bloque=False)
            self.enlace_directo(destino)
            self.e("jal  {}".format(etiqueta_funcion(i.arg1)))
        elif i.op == "callv":
            nombre = i.arg1.split(".")[-1]
            slot = self.ctx.slot_metodo[nombre]
            a.vaciar(fin_de_bloque=False)
            self.e("lw   $t8, {}($sp)".format(4 * (n - 1)))
            self.e("lw   $t8, 0($t8)")
            self.e("lw   $t9, {}($t8)".format(4 + 4 * slot))
            clase = i.arg1.split(".")[0]
            destino = self.ctx.funciones.get(i.arg1)
            if destino is None:
                destino = self.f
            self.enlace_directo(destino)
            self.e("jalr $t9")
        else:
            rt = a.usar(i.arg1)
            self.e("move $t8, {}".format(rt))
            a.vaciar(fin_de_bloque=False)
            ok = self.ctx.etiqueta_nueva()
            fin = self.ctx.etiqueta_nueva()
            self.e("lw   $t9, 4($t8)")
            self.e("li   $t7, {}".format(self.f.registro.nivel + 1))
            self.e("subu $t7, $t7, $t9")
            self.e("move $v1, $fp")
            self.etiqueta(ok)
            self.e("blez $t7, {}".format(fin))
            self.e("lw   $v1, -12($v1)")
            self.e("addiu $t7, $t7, -1")
            self.e("j    {}".format(ok))
            self.etiqueta(fin)
            self.e("lw   $t9, 0($t8)")
            self.e("jalr $t9")
        if n:
            self.e("addiu $sp, $sp, {}".format(4 * n))
        if i.res is not None:
            rd = a.definir(i.res)
            self.e("move {}, $v0".format(rd))
            a.terminar(i.res, rd)

    # ---------------------------------------------------------------- memoria dinamica
    def nuevo_arreglo(self, i):
        a = self.a
        c = clasificar(i.arg1)
        if c[0] == "const":
            self.e("li   $a0, {}".format(4 + 4 * c[2]))
            self.e("li   $v0, 9")
            self.e("syscall")
            self.e("li   $t8, {}".format(c[2]))
            self.e("sw   $t8, 0($v0)")
        else:
            rn = a.usar(i.arg1)
            self.e("sll  $a0, {}, 2".format(rn))
            self.e("addiu $a0, $a0, 4")
            self.e("li   $v0, 9")
            self.e("syscall")
            self.e("sw   {}, 0($v0)".format(rn))
        a.liberar_operandos([i.arg1], i.res)
        rd = a.definir(i.res)
        self.e("move {}, $v0".format(rd))
        a.terminar(i.res, rd)

    def nuevo_objeto(self, i):
        a = self.a
        self.e("li   $a0, {}".format(self.ctx.tamano_objeto(i.arg1)))
        self.e("li   $v0, 9")
        self.e("syscall")
        self.e("la   $t8, vt_{}".format(i.arg1))
        self.e("sw   $t8, 0($v0)")
        a.liberar_operandos([], i.res)
        rd = a.definir(i.res)
        self.e("move {}, $v0".format(rd))
        a.terminar(i.res, rd)

    def acceso_arreglo(self, i, k):
        a = self.a
        rarr = a.usar(i.arg1)
        imm = self.entero_inmediato(i.arg2)
        rind = a.usar(i.arg2)
        ok = self.ctx.etiqueta_nueva()
        self.e("lw   $t8, 0({})".format(rarr))
        self.e("bltu {}, $t8, {}".format(rind, ok))
        self.lanzar("msg_indice")
        self.etiqueta(ok)
        self.e("sll  $t9, {}, 2".format(rind))
        self.e("addu $t9, $t9, {}".format(rarr))
        if i.op == "aload":
            a.liberar_operandos([i.arg1, i.arg2], i.res)
            rd = a.definir(i.res)
            self.e("lw   {}, 4($t9)".format(rd))
            a.terminar(i.res, rd)
        else:
            rv = a.usar(i.res)
            self.e("sw   {}, 4($t9)".format(rv))

    def acceso_campo(self, i, k):
        a = self.a
        ca, cb, cr, ta, tb, tr = self.clases(k)
        clase = ta if ca == "obj" else None
        off = self.ctx.offset_campo(clase, i.arg2)
        ro = a.usar(i.arg1)
        if i.op == "getf":
            a.liberar_operandos([i.arg1], i.res)
            rd = a.definir(i.res)
            self.e("lw   {}, {}({})".format(rd, off, ro))
            a.terminar(i.res, rd)
        else:
            rv = a.usar(i.res)
            self.e("sw   {}, {}({})".format(rv, off, ro))

    # ---------------------------------------------------------------- cadenas
    def a_cadena(self, reg, clase, tipo):
        """Deja en $v0 la representacion en texto del valor de `reg`."""
        if clase in ("int", "?"):
            self.rutina("__itoa", [reg])
        elif clase == "float":
            self.rutina("__ftoa", [reg])
        elif clase == "bool":
            self.rutina("__boolstr", [reg])
        elif clase == "obj":
            self.rutina("__objstr", [reg])
        elif clase == "arr":
            self.e("move $a0, {}".format(reg))
            self.e("li   $a1, {}".format(codigo_elemento(tipo)))
            self.a.vaciar(fin_de_bloque=False)
            self.ctx.rutinas.add("__arrstr")
            self.e("jal  __arrstr")
        elif clase == "str":
            self.e("move $v0, {}".format(reg))
            self.a.vaciar(fin_de_bloque=False)
        elif clase == "null":
            self.a.vaciar(fin_de_bloque=False)
            self.e("la   $v0, rt_null")
        else:
            self.a.vaciar(fin_de_bloque=False)
            self.e("la   $v0, rt_fun")

    def convertir_cadena(self, i, k):
        a = self.a
        ca, cb, cr, ta, tb, tr = self.clases(k)
        r = a.usar(i.arg1)
        self.a_cadena(r, ca, ta)
        rd = a.definir(i.res)
        self.e("move {}, $v0".format(rd))
        a.terminar(i.res, rd)

    def imprimir(self, i, k):
        a = self.a
        ca, cb, cr, ta, tb, tr = self.clases(k)
        r = a.usar(i.arg1)
        if ca == "int":
            self.e("move $a0, {}".format(r))
            self.e("li   $v0, 1")
            self.e("syscall")
            self.e("li   $a0, 10")
            self.e("li   $v0, 11")
            self.e("syscall")
            return
        if ca == "str":
            self.rutina("__print_str", [r])
            return
        self.a_cadena(r, ca, ta)
        self.rutina("__print_str", ["$v0"])


def datos_usuario(ctx):
    lineas = []
    for g in sorted(ctx.globales):
        lineas.append("g_{}: .word 0".format(g[1:]))
    for texto, etiqueta in ctx.cadenas.items():
        seguro = texto.replace("\\", "\\\\").replace('"', '\\"')
        lineas.append('{}: .asciiz "{}"'.format(etiqueta, seguro))
    for clase in ctx.tabla.clases:
        lineas.append('cn_{}: .asciiz "{}"'.format(clase, clase))
    for clase in ctx.tabla.clases:
        tabla = ctx.programa.vtables.get(clase, {})
        slots = []
        for nombre in sorted(ctx.slot_metodo, key=ctx.slot_metodo.get):
            etiqueta = tabla.get(nombre)
            slots.append(etiqueta_funcion(etiqueta) if etiqueta else "0")
        lineas.append("vt_{}: .word {}".format(clase, ", ".join(["cn_" + clase] + slots)))
    for destino in sorted(ctx.descriptores):
        funcion = ctx.funciones[destino]
        lineas.append("fd_{}: .word {}, {}".format(etiqueta_funcion(destino)[2:], etiqueta_funcion(destino),
                                                    funcion.registro.nivel))
    return "\n".join(lineas)


def generar_mips(programa, tabla, modo="registros"):
    ctx = ContextoPrograma(programa, tabla, modo)
    cuerpos = []
    for f in programa.funciones:
        cuerpos.append(EmisorFuncion(ctx, f).generar())
    partes = [
        "# Codigo MIPS generado por el compilador de Compiscript (fase 3)",
        "# modo de asignacion de registros: {}".format("getReg con descriptores ($t y $s)" if modo == "registros"
                                                      else "todo en la pila"),
        "",
        "    .data",
        runtime.DATOS.rstrip(),
        datos_usuario(ctx),
        "",
        "    .text",
        "    .globl main",
        "main:",
        "    li   $v1, 0",
        "    jal  {}".format(etiqueta_funcion("$main")),
        "    li   $v0, 10",
        "    syscall",
    ]
    partes.extend(cuerpos)
    if ctx.rutinas:
        partes.append("")
        partes.append("# ---- rutinas de apoyo ----")
        partes.append(runtime.texto(ctx.rutinas))
    return "\n".join(partes) + "\n"
