"""Interprete del codigo intermedio.

No forma parte del enunciado: existe para comprobar que el TAC generado hace lo que dice el
programa original. La bateria de pruebas ejecuta programas Compiscript compilados a TAC y compara
lo que imprimen contra el resultado esperado. Tambien lo usa el IDE en el boton "Ejecutar".
"""
import re


class ExcepcionCompiscript(Exception):
    def __init__(self, mensaje):
        Exception.__init__(self, mensaje)
        self.mensaje = mensaje


class ErrorEjecucion(Exception):
    pass


class Objeto:
    def __init__(self, clase):
        self.clase = clase
        self.campos = {}


class Marco:
    def __init__(self, funcion, enlace):
        self.funcion = funcion
        self.nivel = funcion.registro.nivel
        self.enlace = enlace
        self.vars = {}


ENTERO = re.compile(r"^-?[0-9]+$")
FLOTANTE = re.compile(r"^-?[0-9]+\.[0-9]+$")


def a_texto(valor):
    if valor is True:
        return "true"
    if valor is False:
        return "false"
    if valor is None:
        return "null"
    if isinstance(valor, list):
        return "[" + ", ".join(a_texto(v) for v in valor) + "]"
    if isinstance(valor, Objeto):
        return "<{}>".format(valor.clase)
    if isinstance(valor, tuple):
        return "<funcion {}>".format(valor[1])
    return str(valor)


class Interprete:
    def __init__(self, programa, limite_pasos=2000000):
        self.programa = programa
        self.funciones = {f.etiqueta: f for f in programa.funciones}
        self.etiquetas = {}
        for f in programa.funciones:
            self.etiquetas[f.etiqueta] = {i.res: n for n, i in enumerate(f.instrucciones) if i.op == "label"}
        self.globales = {}
        self.salida = []
        self.pendientes = []
        self.pasos = 0
        self.limite = limite_pasos
        self.excepcion = None

    def ejecutar(self):
        self.llamar("$main", [], None, None)
        return self.salida

    # ---------------------------------------------------------------- operandos
    def marco_de(self, marco, saltos):
        for _ in range(saltos):
            marco = marco.enlace
        return marco

    def leer(self, operando, marco):
        if operando is None:
            return None
        if operando == "true":
            return True
        if operando == "false":
            return False
        if operando == "null":
            return None
        if ENTERO.match(operando):
            return int(operando)
        if FLOTANTE.match(operando):
            return float(operando)
        if operando.startswith('"'):
            return operando[1:-1]
        if operando.startswith("$"):
            return self.globales.get(operando)
        if "^" in operando:
            nombre, saltos = operando.split("^")
            return self.marco_de(marco, int(saltos)).vars.get(nombre)
        return marco.vars.get(operando)

    def escribir(self, operando, valor, marco):
        if operando.startswith("$"):
            self.globales[operando] = valor
        elif "^" in operando:
            nombre, saltos = operando.split("^")
            self.marco_de(marco, int(saltos)).vars[nombre] = valor
        else:
            marco.vars[operando] = valor

    # ---------------------------------------------------------------- llamadas
    def llamar(self, etiqueta, argumentos, marco_llamador, indirecto):
        funcion = self.funciones[etiqueta]
        nivel = funcion.registro.nivel
        if marco_llamador is None:
            enlace = None
        else:
            enlace = self.marco_de(marco_llamador, marco_llamador.nivel - (nivel - 1))
        marco = Marco(funcion, enlace)
        for nombre, valor in zip(funcion.parametros, argumentos):
            marco.vars[nombre] = valor
        return self.correr(funcion, marco)

    def correr(self, funcion, marco):
        instrucciones = funcion.instrucciones
        etiquetas = self.etiquetas[funcion.etiqueta]
        manejadores = []
        pc = 0
        while True:
            try:
                while pc < len(instrucciones):
                    self.pasos += 1
                    if self.pasos > self.limite:
                        raise ErrorEjecucion("limite de pasos excedido")
                    i = instrucciones[pc]
                    pc += 1
                    op = i.op
                    if op == "label":
                        continue
                    if op == "goto":
                        pc = etiquetas[i.res]
                    elif op == "if":
                        if self.leer(i.arg1, marco):
                            pc = etiquetas[i.res]
                    elif op == "iffalse":
                        if not self.leer(i.arg1, marco):
                            pc = etiquetas[i.res]
                    elif op.startswith("if") and op[2:] in ("<", "<=", ">", ">=", "==", "!="):
                        if self.comparar(op[2:], self.leer(i.arg1, marco), self.leer(i.arg2, marco)):
                            pc = etiquetas[i.res]
                    elif op == "copy":
                        self.escribir(i.res, self.leer(i.arg1, marco), marco)
                    elif op in ("<", "<=", ">", ">=", "==", "!="):
                        self.escribir(i.res, self.comparar(op, self.leer(i.arg1, marco), self.leer(i.arg2, marco)), marco)
                    elif op in ("+", "-", "*", "/", "%"):
                        self.escribir(i.res, self.aritmetica(op, self.leer(i.arg1, marco), self.leer(i.arg2, marco)), marco)
                    elif op == "neg":
                        self.escribir(i.res, -self.leer(i.arg1, marco), marco)
                    elif op == "not":
                        self.escribir(i.res, not self.leer(i.arg1, marco), marco)
                    elif op == "itof":
                        self.escribir(i.res, float(self.leer(i.arg1, marco)), marco)
                    elif op == "tostr":
                        self.escribir(i.res, a_texto(self.leer(i.arg1, marco)), marco)
                    elif op == "concat":
                        self.escribir(i.res, self.leer(i.arg1, marco) + self.leer(i.arg2, marco), marco)
                    elif op == "param":
                        self.pendientes.append(self.leer(i.arg1, marco))
                    elif op in ("call", "callind", "callv"):
                        n = int(i.arg2)
                        argumentos = self.pendientes[len(self.pendientes) - n:] if n else []
                        del self.pendientes[len(self.pendientes) - n:]
                        if op == "call":
                            destino = i.arg1
                        elif op == "callind":
                            destino = self.leer(i.arg1, marco)[1]
                        else:
                            destino = self.programa.vtables[argumentos[0].clase][i.arg1.split(".")[-1]]
                        resultado = self.llamar(destino, argumentos, marco, op == "callind")
                        if i.res is not None:
                            self.escribir(i.res, resultado, marco)
                    elif op == "return":
                        return self.leer(i.arg1, marco)
                    elif op == "newarray":
                        self.escribir(i.res, [0] * int(i.arg1), marco)
                    elif op == "len":
                        self.escribir(i.res, len(self.leer(i.arg1, marco)), marco)
                    elif op == "aload":
                        self.escribir(i.res, self.indexar(self.leer(i.arg1, marco), self.leer(i.arg2, marco)), marco)
                    elif op == "astore":
                        arreglo = self.leer(i.arg1, marco)
                        self.indexar(arreglo, self.leer(i.arg2, marco))
                        arreglo[self.leer(i.arg2, marco)] = self.leer(i.res, marco)
                    elif op == "new":
                        self.escribir(i.res, Objeto(i.arg1), marco)
                    elif op == "getf":
                        self.escribir(i.res, self.leer(i.arg1, marco).campos.get(i.arg2), marco)
                    elif op == "putf":
                        self.leer(i.arg1, marco).campos[i.arg2] = self.leer(i.res, marco)
                    elif op == "addr":
                        self.escribir(i.res, ("fn", i.arg1), marco)
                    elif op == "print":
                        self.salida.append(a_texto(self.leer(i.arg1, marco)))
                    elif op == "pushtry":
                        manejadores.append(i.res)
                    elif op == "poptry":
                        manejadores.pop()
                    elif op == "getexc":
                        self.escribir(i.res, self.excepcion, marco)
                    else:
                        raise ErrorEjecucion("operacion desconocida {}".format(op))
                return None
            except ExcepcionCompiscript as e:
                if not manejadores:
                    raise
                self.excepcion = e.mensaje
                pc = etiquetas[manejadores.pop()]

    def indexar(self, arreglo, indice):
        if not isinstance(indice, int) or indice < 0 or indice >= len(arreglo):
            raise ExcepcionCompiscript("indice fuera de rango")
        return arreglo[indice]

    def comparar(self, op, a, b):
        if op in ("==", "!="):
            if isinstance(a, (list, Objeto)) or isinstance(b, (list, Objeto)):
                igual = a is b
            else:
                igual = a == b and type(a) == type(b) or (isinstance(a, (int, float)) and isinstance(b, (int, float))
                                                          and not isinstance(a, bool) and not isinstance(b, bool) and a == b)
            return igual if op == "==" else not igual
        return {"<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b}[op]

    def aritmetica(self, op, a, b):
        if op == "+":
            return a + b
        if op == "-":
            return a - b
        if op == "*":
            return a * b
        if op == "/":
            if b == 0:
                raise ExcepcionCompiscript("division entre cero")
            if isinstance(a, int) and isinstance(b, int):
                cociente = abs(a) // abs(b)
                return cociente if (a >= 0) == (b >= 0) else -cociente
            return a / b
        if b == 0:
            raise ExcepcionCompiscript("division entre cero")
        resto = abs(a) % abs(b)
        return resto if a >= 0 else -resto


def ejecutar(programa, limite_pasos=2000000):
    return Interprete(programa, limite_pasos).ejecutar()
