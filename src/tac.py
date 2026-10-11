"""Lenguaje intermedio de Compiscript: codigo de tres direcciones en forma de cuadruplas.

Cada instruccion es una cuadrupla (op, arg1, arg2, res). El formato textual de cada
operacion esta documentado en docs/LENGUAJE_INTERMEDIO.md.
"""

BINARIAS = ("+", "-", "*", "/", "%", "<", "<=", ">", ">=", "==", "!=")
RELACIONALES = ("<", "<=", ">", ">=", "==", "!=")
SALTOS_RELACIONALES = tuple("if" + r for r in RELACIONALES)

NEGADA = {"<": ">=", "<=": ">", ">": "<=", ">=": "<", "==": "!=", "!=": "=="}


class Instruccion:
    __slots__ = ("op", "arg1", "arg2", "res", "tipo", "linea")

    def __init__(self, op, arg1=None, arg2=None, res=None, tipo=None, linea=0):
        self.op = op
        self.arg1 = arg1
        self.arg2 = arg2
        self.res = res
        self.tipo = tipo
        self.linea = linea

    def como_tupla(self):
        return (self.op, self.arg1, self.arg2, self.res)

    def __str__(self):
        op, a, b, r = self.op, self.arg1, self.arg2, self.res
        if op == "label":
            return "{}:".format(r)
        if op == "goto":
            return "goto {}".format(r)
        if op == "if":
            return "if {} goto {}".format(a, r)
        if op == "iffalse":
            return "ifFalse {} goto {}".format(a, r)
        if op in SALTOS_RELACIONALES:
            return "if {} {} {} goto {}".format(a, op[2:], b, r)
        if op == "copy":
            return "{} = {}".format(r, a)
        if op in BINARIAS:
            return "{} = {} {} {}".format(r, a, op, b)
        if op == "neg":
            return "{} = - {}".format(r, a)
        if op == "not":
            return "{} = ! {}".format(r, a)
        if op in ("itof", "tostr", "len", "addr"):
            if op == "addr":
                return "{} = &{}".format(r, a)
            return "{} = {} {}".format(r, op, a)
        if op == "concat":
            return "{} = concat {}, {}".format(r, a, b)
        if op == "param":
            return "param {}".format(a)
        if op == "call":
            return "{}call {}, {}".format("{} = ".format(r) if r else "", a, b)
        if op == "callind":
            return "{}callind {}, {}".format("{} = ".format(r) if r else "", a, b)
        if op == "callv":
            return "{}callv {}, {}".format("{} = ".format(r) if r else "", a, b)
        if op == "return":
            return "return" if a is None else "return {}".format(a)
        if op == "newarray":
            return "{} = newarray {}, {}".format(r, a, b)
        if op == "aload":
            return "{} = {}[{}]".format(r, a, b)
        if op == "astore":
            return "{}[{}] = {}".format(a, b, r)
        if op == "new":
            return "{} = new {}, {}".format(r, a, b)
        if op == "getf":
            return "{} = {}.{}".format(r, a, b)
        if op == "putf":
            return "{}.{} = {}".format(a, b, r)
        if op == "print":
            return "print {}".format(a)
        if op == "pushtry":
            return "pushtry {}".format(r)
        if op == "poptry":
            return "poptry"
        if op == "getexc":
            return "{} = getexc".format(r)
        return "{} {} {} {}".format(op, a, b, r)

    def __repr__(self):
        return str(self)


class FuncionTAC:
    def __init__(self, etiqueta, registro, parametros, es_main=False):
        self.etiqueta = etiqueta
        self.registro = registro
        self.parametros = parametros
        self.es_main = es_main
        self.instrucciones = []

    def encabezado(self):
        return "FUNC {}({})  (frame={})".format(
            self.etiqueta, ", ".join(self.parametros), self.registro.tamano_total())

    def texto(self, con_lineas=False):
        salida = [self.encabezado()]
        for i in self.instrucciones:
            if i.op == "label":
                salida.append("{}:".format(i.res))
            elif con_lineas and i.linea:
                salida.append("    {:<34} ; linea {}".format(str(i), i.linea))
            else:
                salida.append("    {}".format(i))
        salida.append("ENDFUNC {}".format(self.etiqueta))
        return "\n".join(salida)


class ProgramaTAC:
    def __init__(self, funciones, area_global=0, vtables=None):
        self.funciones = funciones
        self.area_global = area_global
        self.vtables = vtables or {}     # clase -> {metodo: etiqueta}

    def usa_despacho_dinamico(self):
        return any(i.op == "callv" for i in self.instrucciones())

    def vtables_texto(self):
        lineas = []
        for clase, tabla in self.vtables.items():
            lineas.append("VTABLE {} {{ {} }}".format(
                clase, ", ".join("{} -> {}".format(m, e) for m, e in tabla.items())))
        return "\n".join(lineas)

    def instrucciones(self):
        return [i for f in self.funciones for i in f.instrucciones]

    def funcion(self, etiqueta):
        for f in self.funciones:
            if f.etiqueta == etiqueta:
                return f
        return None

    def texto(self, con_lineas=False):
        partes = [f.texto(con_lineas) for f in self.funciones]
        if self.vtables and self.usa_despacho_dinamico():
            partes.append(self.vtables_texto())
        return "\n\n".join(partes)

    def __str__(self):
        return self.texto()
