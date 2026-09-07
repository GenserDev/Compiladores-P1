class Tipo:
    def __init__(self, nombre, tamano=8):
        self.nombre = nombre
        self.tamano = tamano

    def __eq__(self, otro):
        return isinstance(otro, Tipo) and str(self) == str(otro)

    def __hash__(self):
        return hash(str(self))

    def __str__(self):
        return self.nombre

    def __repr__(self):
        return str(self)


class TipoArreglo(Tipo):
    def __init__(self, elemento):
        Tipo.__init__(self, "arreglo", 8)
        self.elemento = elemento

    def __str__(self):
        return "{}[]".format(self.elemento)


class TipoFuncion(Tipo):
    def __init__(self, parametros, retorno):
        Tipo.__init__(self, "funcion", 8)
        self.parametros = parametros
        self.retorno = retorno

    def __str__(self):
        return "({}) -> {}".format(", ".join(str(p) for p in self.parametros), self.retorno)


class TipoClase(Tipo):
    def __init__(self, nombre, info=None):
        Tipo.__init__(self, nombre, 8)
        self.info = info

    def __str__(self):
        return self.nombre


ENTERO = Tipo("integer", 4)
FLOTANTE = Tipo("float", 8)
CADENA = Tipo("string", 8)
BOOLEANO = Tipo("boolean", 1)
NULO = Tipo("null", 8)
VACIO = Tipo("void", 0)
ERROR = Tipo("error", 0)

PRIMITIVOS = {"integer": ENTERO, "float": FLOTANTE, "string": CADENA, "boolean": BOOLEANO}


def es_error(tipo):
    return tipo is None or tipo == ERROR


def es_numerico(tipo):
    return tipo in (ENTERO, FLOTANTE)


def admite_null(tipo):
    return isinstance(tipo, (TipoArreglo, TipoClase, TipoFuncion)) or tipo in (CADENA, NULO)


def es_subclase(hija, padre):
    if not isinstance(hija, TipoClase) or not isinstance(padre, TipoClase):
        return False
    actual = hija.info
    while actual is not None:
        if actual.nombre == padre.nombre:
            return True
        actual = actual.padre
    return False


def compatible(destino, origen):
    if es_error(destino) or es_error(origen):
        return True
    if destino == origen:
        return True
    if origen == NULO and admite_null(destino):
        return True
    if destino == FLOTANTE and origen == ENTERO:
        return True
    if es_subclase(origen, destino):
        return True
    if isinstance(destino, TipoArreglo) and isinstance(origen, TipoArreglo):
        return compatible(destino.elemento, origen.elemento)
    return False


def unificar(a, b):
    if es_error(a) or es_error(b):
        return ERROR
    if a == b:
        return a
    if es_numerico(a) and es_numerico(b):
        return FLOTANTE
    if compatible(a, b):
        return a
    if compatible(b, a):
        return b
    return ERROR


def comparables(a, b):
    if es_error(a) or es_error(b):
        return True
    if es_numerico(a) and es_numerico(b):
        return True
    if a == b:
        return True
    return (a == NULO and admite_null(b)) or (b == NULO and admite_null(a))
