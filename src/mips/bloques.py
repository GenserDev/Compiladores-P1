"""Analisis previo a la generacion: bloques basicos, ultimo uso de cada nombre, variables capturadas.

Un bloque basico empieza en la primera instruccion, en cada etiqueta y en la instruccion que sigue a un
salto o a un `return`. Dentro de un bloque el flujo es lineal, asi que "el nombre se vuelve a usar mas
adelante en este bloque" basta para decidir cuando un registro ya no se necesita. Un temporal que se
nombra en mas de un bloque se considera vivo en todo momento (hay que guardarlo al cerrar el bloque).
"""
from temporales import es_temporal
from .operandos import clasificar, leer_escribir

SALTOS = ("goto", "if", "iffalse", "return")


def es_salto(i):
    return i.op in SALTOS or (i.op.startswith("if") and i.op != "if" and i.op != "iffalse")


def nombres_locales(instruccion):
    """Nombres de variables/temporales de nivel local (sin ^) que toca la instruccion."""
    leidos, escrito = leer_escribir(instruccion)
    salida = []
    for op in leidos + ([escrito] if escrito else []):
        c = clasificar(op)
        if c[0] == "var" and c[2] == 0:
            salida.append(c[1])
    return salida


class AnalisisFuncion:
    def __init__(self, funcion):
        self.funcion = funcion
        instrucciones = funcion.instrucciones
        n = len(instrucciones)
        self.bloque = [0] * n
        actual = 0
        lider = True
        for k, i in enumerate(instrucciones):
            if i.op == "label":
                lider = True
            if lider and k > 0:
                actual += 1
            self.bloque[k] = actual
            lider = es_salto(i)
        bloques_de = {}       # nombre -> conjunto de bloques que lo nombran
        self.usos = {}        # nombre -> cantidad de referencias
        self.info = []        # por instruccion: (nombres que lee, nombre que escribe)
        self.usa_try = False
        for k, i in enumerate(instrucciones):
            if i.op == "pushtry":
                self.usa_try = True
            leidos, escrito = leer_escribir(i)
            lee = {c[1] for c in map(clasificar, leidos) if c[0] == "var" and c[2] == 0}
            esc = None
            if escrito is not None:
                c = clasificar(escrito)
                if c[0] == "var" and c[2] == 0:
                    esc = c[1]
            self.info.append((lee, esc))
            for nombre in nombres_locales(i):
                bloques_de.setdefault(nombre, set()).add(self.bloque[k])
                self.usos[nombre] = self.usos.get(nombre, 0) + 1
        self.vivo_global = {nombre for nombre, bs in bloques_de.items() if len(bs) > 1}

    def vivo_desde(self, nombre, j):
        """El valor que tiene `nombre` antes de la instruccion j, se lee despues?

        Se avanza por el bloque: si la primera referencia lee el nombre, esta vivo; si la primera lo
        escribe sin leerlo, el valor actual esta muerto (se sobrescribe). Si el bloque termina sin
        mencionarlo, queda vivo solo cuando otro bloque lo nombra.
        """
        n = len(self.info)
        if j < n:
            b = self.bloque[j]
            while j < n and self.bloque[j] == b:
                lee, esc = self.info[j]
                if nombre in lee:
                    return True
                if esc == nombre:
                    return False
                j += 1
        return nombre in self.vivo_global

    def proximo_uso(self, nombre, k):
        """Indice de la siguiente instruccion del bloque que nombra `nombre` (grande si no hay)."""
        n = len(self.info)
        b = self.bloque[k]
        j = k + 1
        while j < n and self.bloque[j] == b:
            lee, esc = self.info[j]
            if nombre in lee or esc == nombre:
                return j
            j += 1
        return 10 ** 9 if nombre not in self.vivo_global else 10 ** 8


def variables_capturadas(programa):
    """Conjunto de (etiqueta de funcion, nombre) que alguna funcion anidada lee o escribe via x^k."""
    funciones = {f.etiqueta: f for f in programa.funciones}
    capturadas = set()
    for f in programa.funciones:
        for i in f.instrucciones:
            leidos, escrito = leer_escribir(i)
            for op in leidos + ([escrito] if escrito else []):
                c = clasificar(op)
                if c[0] == "var" and c[2] > 0:
                    dueno = f
                    for _ in range(c[2]):
                        dueno = funciones[dueno.registro.padre.etiqueta]
                    capturadas.add((dueno.etiqueta, c[1]))
    return capturadas


def asignar_s(funcion, analisis, capturadas, cantidad=8):
    """Variables de usuario que viviran todo el tiempo en $s0..$s7 (las mas referenciadas)."""
    if analisis.usa_try:
        return {}
    candidatos = []
    for nombre in funcion.tipos_vars:
        if nombre in funcion.parametros or es_temporal(nombre):
            continue
        if (funcion.etiqueta, nombre) in capturadas:
            continue
        usos = analisis.usos.get(nombre, 0)
        if usos >= 2:
            candidatos.append((-usos, nombre))
    candidatos.sort()
    return {nombre: "$s{}".format(k) for k, (_, nombre) in enumerate(candidatos[:cantidad])}
