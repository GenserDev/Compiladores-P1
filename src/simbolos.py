
class Simbolo:
    def __init__(self, nombre, categoria, tipo, linea=0, columna=0):
        self.nombre = nombre
        self.categoria = categoria
        self.tipo = tipo
        self.linea = linea
        self.columna = columna
        self.es_const = False
        self.inicializado = False
        self.offset = 0
        self.tamano = getattr(tipo, "tamano", 8)
        self.ambito = ""
        self.parametros = []
        self.retorno = None
        self.capturadas = []
        self.clase = None

    def __str__(self):
        return "{} {}: {}".format(self.categoria, self.nombre, self.tipo)


class InfoClase:
    def __init__(self, nombre, padre=None):
        self.nombre = nombre
        self.padre = padre
        self.atributos = {}
        self.metodos = {}
        self.entorno = None

    def buscar_miembro(self, nombre):
        actual = self
        while actual is not None:
            if nombre in actual.atributos:
                return actual.atributos[nombre]
            if nombre in actual.metodos:
                return actual.metodos[nombre]
            actual = actual.padre
        return None

    def constructor(self):
        return self.buscar_miembro("constructor")

    def tamano(self):
        total = 0
        actual = self
        while actual is not None:
            total += sum(s.tamano for s in actual.atributos.values())
            actual = actual.padre
        return total


class Entorno:
    def __init__(self, nombre, categoria, padre=None):
        self.nombre = nombre
        self.categoria = categoria
        self.padre = padre
        self.simbolos = {}
        self.hijos = []
        self.desplazamiento = 0
        self.nivel = 0 if padre is None else padre.nivel + 1

    def declarar(self, simbolo):
        if simbolo.nombre in self.simbolos:
            return False
        simbolo.ambito = self.nombre
        simbolo.offset = self.desplazamiento
        self.desplazamiento += simbolo.tamano
        self.simbolos[simbolo.nombre] = simbolo
        return True

    def buscar_local(self, nombre):
        return self.simbolos.get(nombre)

    def buscar(self, nombre):
        actual = self
        while actual is not None:
            if nombre in actual.simbolos:
                return actual.simbolos[nombre]
            actual = actual.padre
        return None

    def ruta(self):
        partes = []
        actual = self
        while actual is not None:
            partes.append(actual.nombre)
            actual = actual.padre
        return ".".join(reversed(partes))


class TablaSimbolos:
    def __init__(self):
        self.raiz = Entorno("global", "global")
        self.actual = self.raiz
        self.entornos = [self.raiz]
        self.clases = {}

    def abrir_ambito(self, nombre, categoria):
        entorno = Entorno(nombre, categoria, self.actual)
        self.actual.hijos.append(entorno)
        self.entornos.append(entorno)
        self.actual = entorno
        return entorno

    def cerrar_ambito(self):
        if self.actual.padre is not None:
            self.actual = self.actual.padre

    def declarar(self, simbolo):
        return self.actual.declarar(simbolo)

    def buscar(self, nombre):
        return self.actual.buscar(nombre)

    def buscar_local(self, nombre):
        return self.actual.buscar_local(nombre)

    def entorno_de(self, nombre):
        actual = self.actual
        while actual is not None:
            if nombre in actual.simbolos:
                return actual
            actual = actual.padre
        return None

    def filas(self):
        salida = []
        for entorno in self.entornos:
            for simbolo in entorno.simbolos.values():
                salida.append({
                    "nombre": simbolo.nombre,
                    "categoria": simbolo.categoria,
                    "tipo": str(simbolo.tipo),
                    "ambito": entorno.ruta(),
                    "nivel": entorno.nivel,
                    "const": "si" if simbolo.es_const else "no",
                    "init": "si" if simbolo.inicializado else "no",
                    "offset": simbolo.offset,
                    "tamano": simbolo.tamano,
                    "linea": simbolo.linea,
                })
        return salida

    def __str__(self):
        columnas = ["nombre", "categoria", "tipo", "ambito", "nivel", "const", "init", "offset", "tamano", "linea"]
        filas = self.filas()
        anchos = [max(len(c), *([len(str(f[c])) for f in filas] or [0])) for c in columnas]
        lineas = [" | ".join(c.ljust(a) for c, a in zip(columnas, anchos))]
        lineas.append("-+-".join("-" * a for a in anchos))
        for f in filas:
            lineas.append(" | ".join(str(f[c]).ljust(a) for c, a in zip(columnas, anchos)))
        return "\n".join(lineas)
