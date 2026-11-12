"""Clasificacion de operandos TAC y deduccion de tipos para el backend MIPS.

El TAC no escribe el tipo de cada operando, asi que el backend lo recupera: las variables traen el tipo
declarado (`FuncionTAC.tipos_vars`, `ProgramaTAC.tipos_globales`), las constantes lo dicen su forma y los
temporales heredan el tipo de la instruccion que los define (se recorre la funcion en orden).
"""
import re
import struct

from temporales import es_temporal
from tac import BINARIAS, RELACIONALES

ENTERO = re.compile(r"^-?[0-9]+$")
FLOTANTE = re.compile(r"^-?[0-9]+\.[0-9]+$")


def bits_float(texto):
    """Palabra de 32 bits (float de precision simple) de un literal flotante."""
    return struct.unpack(">i", struct.pack(">f", float(texto)))[0]


def clasificar(op):
    """('nada',) | ('const', clase, valor) | ('global', nombre) | ('var', nombre, saltos)."""
    if op is None:
        return ("nada",)
    if op == "true":
        return ("const", "bool", 1)
    if op == "false":
        return ("const", "bool", 0)
    if op == "null":
        return ("const", "null", 0)
    if ENTERO.match(op):
        return ("const", "int", int(op))
    if FLOTANTE.match(op):
        return ("const", "float", bits_float(op))
    if op.startswith('"'):
        return ("const", "str", op[1:-1])
    if op.startswith("$"):
        return ("global", op)
    if "^" in op:
        nombre, saltos = op.split("^")
        return ("var", nombre, int(saltos))
    return ("var", op, 0)


def leer_escribir(i):
    """(operandos que lee, operando que escribe) de una instruccion TAC."""
    op, a, b, r = i.op, i.arg1, i.arg2, i.res
    if op in ("label", "goto", "poptry", "pushtry"):
        return [], None
    if op in ("if", "iffalse", "param", "return", "print"):
        return [a], None
    if op.startswith("if"):
        return [a, b], None
    if op in ("copy", "neg", "not", "itof", "tostr", "len"):
        return [a], r
    if op in BINARIAS or op == "concat":
        return [a, b], r
    if op == "call" or op == "callv":
        return [], r
    if op == "callind":
        return [a], r
    if op == "addr" or op == "new" or op == "getexc":
        return [], r
    if op == "newarray":
        return [a], r
    if op == "aload":
        return [a, b], r
    if op == "astore":
        return [a, b, r], None
    if op == "getf":
        return [a], r
    if op == "putf":
        return [a, r], None
    raise ValueError("operacion TAC desconocida: " + op)


def clase_tipo(tipo):
    """Resume el texto de un tipo en: int float str bool null arr fun obj ?"""
    if tipo is None:
        return "?"
    if tipo == "integer":
        return "int"
    if tipo == "float":
        return "float"
    if tipo == "string":
        return "str"
    if tipo == "boolean":
        return "bool"
    if tipo == "null":
        return "null"
    if tipo.endswith("[]"):
        return "arr"
    if tipo.startswith("(") or tipo == "fun":
        return "fun"
    if tipo == "void":
        return "?"
    return "obj"


class Tipador:
    def __init__(self, programa):
        self.programa = programa
        self.funciones = {f.etiqueta: f for f in programa.funciones}

    def subir(self, funcion, saltos):
        for _ in range(saltos):
            funcion = self.funciones[funcion.registro.padre.etiqueta]
        return funcion

    def tipo_variable(self, funcion, nombre, saltos):
        dueno = self.subir(funcion, saltos)
        if nombre == "this":
            return dueno.etiqueta.split(".")[0]
        return dueno.tipos_vars.get(nombre)

    def tipo_de(self, funcion, op, temporales):
        c = clasificar(op)
        if c[0] == "const":
            return {"int": "integer", "float": "float", "str": "string", "bool": "boolean", "null": "null"}[c[1]]
        if c[0] == "global":
            return self.programa.tipos_globales.get(op)
        if c[0] == "var":
            if es_temporal(c[1]) and c[2] == 0:
                return temporales.get(c[1])
            return self.tipo_variable(funcion, c[1], c[2])
        return None

    def tipar(self, funcion):
        """Lista, una entrada por instruccion, con el tipo de (arg1, arg2, res) como texto."""
        temporales = {}
        salida = []
        for i in funcion.instrucciones:
            leidos, escrito = leer_escribir(i)
            ta = self.tipo_de(funcion, i.arg1, temporales) if i.arg1 in leidos else None
            tb = self.tipo_de(funcion, i.arg2, temporales) if i.arg2 in leidos else None
            tr = self.tipo_de(funcion, i.res, temporales) if (i.res in leidos or i.res == escrito) and i.res else None
            op = i.op
            if escrito is not None and es_temporal(escrito):
                if i.tipo and op not in ("copy",):
                    resultado = i.tipo
                elif op == "copy":
                    resultado = ta
                elif op in ("len",):
                    resultado = "integer"
                elif op in ("tostr", "concat", "getexc"):
                    resultado = "string"
                elif op == "addr":
                    resultado = "fun"
                elif op in RELACIONALES or op == "not":
                    resultado = "boolean"
                elif op in BINARIAS:
                    resultado = "float" if "float" in (ta, tb) else (ta or tb)
                elif op == "neg":
                    resultado = ta
                elif op == "itof":
                    resultado = "float"
                else:
                    resultado = i.tipo
                temporales[escrito] = resultado
                tr = resultado
            salida.append((ta, tb, tr))
        return salida
