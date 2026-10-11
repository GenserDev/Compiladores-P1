import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for ruta in (os.path.join(RAIZ, "src"), os.path.join(RAIZ, "program", "generated")):
    if ruta not in sys.path:
        sys.path.insert(0, ruta)

from antlr4 import InputStream, CommonTokenStream
from antlr4.error.ErrorListener import ErrorListener

from CompiscriptLexer import CompiscriptLexer
from CompiscriptParser import CompiscriptParser

import arbol as vista_arbol
from analizador import AnalizadorSemantico
from generador import generar_tac
from errores import ColectorErrores


class RecolectorSintactico(ErrorListener):
    def __init__(self, colector):
        ErrorListener.__init__(self)
        self.colector = colector

    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        self.colector.agregar_sintactico(msg, line, column)


class Resultado:
    def __init__(self, errores, tabla, arbol, parser, tac=None):
        self.errores = errores
        self.tabla = tabla
        self.arbol = arbol
        self.parser = parser
        self.tac = tac

    def exitoso(self):
        return not self.errores.hay_errores()

    def arbol_texto(self):
        return vista_arbol.texto(self.arbol, self.parser)

    def arbol_dot(self):
        return vista_arbol.dot(self.arbol, self.parser)


def compilar(fuente, generar=True):
    colector = ColectorErrores()
    lexer = CompiscriptLexer(InputStream(fuente))
    lexer.removeErrorListeners()
    lexer.addErrorListener(RecolectorSintactico(colector))
    parser = CompiscriptParser(CommonTokenStream(lexer))
    parser.removeErrorListeners()
    parser.addErrorListener(RecolectorSintactico(colector))
    arbol = parser.program()
    if colector.hay_errores():
        return Resultado(colector, None, arbol, parser)
    analizador = AnalizadorSemantico()
    analizador.errores = colector
    analizador.analizar(arbol)
    tac = None
    if generar and not colector.hay_errores():
        tac = generar_tac(arbol, analizador.tabla)
    return Resultado(colector, analizador.tabla, arbol, parser, tac)


def compilar_archivo(ruta, generar=True):
    with open(ruta, "r") as archivo:
        return compilar(archivo.read(), generar)
