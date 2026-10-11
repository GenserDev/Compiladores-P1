
ENCABEZADO_OBJETO = 8


def alinear(valor, multiplo):
    if multiplo <= 1:
        return valor
    return (valor + multiplo - 1) // multiplo * multiplo


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
        # --- fase 2: datos para generacion de codigo ---
        self.almacenamiento = "-"     # global | local | parametro | campo | funcion
        self.direccion = "-"          # gp+N, fp+N, obj+N o etiqueta
        self.nombre_tac = nombre      # nombre con el que aparece en el codigo intermedio
        self.etiqueta = None          # etiqueta de entrada (funciones y metodos)
        self.nivel_funcion = 0        # profundidad de anidamiento de la funcion duena
        self.registro = None          # RegistroActivacion (solo funciones y metodos)
        self.dueno = None             # InfoClase que declara el metodo (solo metodos)

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

    # --- fase 2: disposicion del objeto ---
    # [0..8) identificador de clase, luego los atributos del ancestro mas lejano al propio.
    def calcular_disposicion(self):
        if getattr(self, "_offsets", None) is not None:
            return self._fin
        if self.padre is not None:
            actual = self.padre.calcular_disposicion()
        else:
            actual = ENCABEZADO_OBJETO
        self._offsets = {}
        for atributo in self.atributos.values():
            actual = alinear(actual, min(atributo.tamano, 8) or 1)
            self._offsets[atributo.nombre] = actual
            atributo.almacenamiento = "campo"
            atributo.offset = actual
            atributo.direccion = "obj+{}".format(actual)
            actual += atributo.tamano
        self._fin = alinear(actual, 8)
        return self._fin

    def tamano_objeto(self):
        return self.calcular_disposicion()

    def offset_campo(self, nombre):
        self.calcular_disposicion()
        actual = self
        while actual is not None:
            if nombre in actual.atributos:
                return actual._offsets[nombre]
            actual = actual.padre
        return None

    def es_subclase_de(self, otra):
        actual = self.padre
        while actual is not None:
            if actual is otra:
                return True
            actual = actual.padre
        return False

    def tabla_virtual(self):
        """nombre de metodo -> etiqueta de la implementacion que corresponde a esta clase"""
        tabla = self.padre.tabla_virtual() if self.padre is not None else {}
        for metodo in self.metodos.values():
            tabla[metodo.nombre] = metodo.etiqueta
        return tabla

    def tiene_inicializadores(self):
        return bool(getattr(self, "inicializadores", None))

    def clase_con_init(self):
        actual = self
        while actual is not None:
            if actual.tiene_inicializadores():
                return actual
            actual = actual.padre
        return None


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


class RegistroActivacion:
    """Disposicion del registro de activacion de una funcion, metodo o del programa principal.

    Los offsets son relativos a fp y crecen hacia arriba:
        fp+0   enlace de control (fp del llamador)
        fp+8   enlace de acceso (fp de la funcion que contiene a esta, para closures)
        fp+16  direccion de retorno
        fp+24  this (solo metodos), luego parametros, luego variables locales
        ...    area de temporales (8 bytes por temporal, despues de las locales)
    """
    ENCABEZADO = 24

    def __init__(self, etiqueta, nivel, padre=None, es_metodo=False):
        self.etiqueta = etiqueta
        self.nivel = nivel
        self.padre = padre
        self.es_metodo = es_metodo
        self.parametros = []     # (nombre, offset, tamano)
        self.locales = []        # (nombre, offset, tamano)
        self.cursor = self.ENCABEZADO
        self.max_cursor = self.ENCABEZADO
        self.temporales = 0      # maximo de temporales vivos a la vez
        self.total_temporales = 0  # temporales pedidos en total (sin reciclaje serian este numero)

    def _reservar(self, nombre, tamano):
        tamano = max(tamano, 1)
        offset = alinear(self.cursor, min(tamano, 8))
        self.cursor = offset + tamano
        self.max_cursor = max(self.max_cursor, self.cursor)
        return offset

    def reservar_this(self):
        offset = self._reservar("this", 8)
        self.parametros.append(("this", offset, 8))
        return offset

    def reservar_parametro(self, simbolo):
        offset = self._reservar(simbolo.nombre_tac, simbolo.tamano)
        self.parametros.append((simbolo.nombre_tac, offset, simbolo.tamano))
        return offset

    def reservar_local(self, simbolo):
        offset = self._reservar(simbolo.nombre_tac, simbolo.tamano)
        self.locales.append((simbolo.nombre_tac, offset, simbolo.tamano))
        return offset

    def marca(self):
        return self.cursor

    def liberar(self, marca):
        self.cursor = marca

    def tamano_locales(self):
        return alinear(self.max_cursor, 8)

    def offset_temporal(self, numero):
        return self.tamano_locales() + 8 * (numero - 1)

    def tamano_total(self):
        return alinear(self.tamano_locales() + 8 * self.temporales, 8)

    def __str__(self):
        return "{} (nivel {}, frame {} bytes)".format(self.etiqueta, self.nivel, self.tamano_total())


COLUMNAS = ["nombre", "categoria", "tipo", "ambito", "nivel", "const", "init", "offset", "tamano",
            "almacen", "direccion", "linea"]


class TablaSimbolos:
    def __init__(self):
        self.raiz = Entorno("global", "global")
        self.actual = self.raiz
        self.entornos = [self.raiz]
        self.clases = {}
        self.registros = []        # RegistroActivacion de cada funcion (fase 2)
        self.area_global = 0       # bytes del area de datos estaticos (fase 2)

    def reservar_global(self, simbolo):
        offset = alinear(self.area_global, min(max(simbolo.tamano, 1), 8))
        self.area_global = offset + max(simbolo.tamano, 1)
        return offset

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
                    "almacen": simbolo.almacenamiento,
                    "direccion": simbolo.direccion,
                    "linea": simbolo.linea,
                })
        return salida

    def __str__(self):
        columnas = COLUMNAS
        filas = self.filas()
        anchos = [max(len(c), *([len(str(f[c])) for f in filas] or [0])) for c in columnas]
        lineas = [" | ".join(c.ljust(a) for c, a in zip(columnas, anchos))]
        lineas.append("-+-".join("-" * a for a in anchos))
        for f in filas:
            lineas.append(" | ".join(str(f[c]).ljust(a) for c, a in zip(columnas, anchos)))
        return "\n".join(lineas)

    def registros_texto(self):
        lineas = []
        for r in self.registros:
            lineas.append("{}  nivel={}  frame={}  (locales={}, temporales={})".format(
                r.etiqueta, r.nivel, r.tamano_total(), r.tamano_locales() - RegistroActivacion.ENCABEZADO,
                r.temporales))
            lineas.append("  fp+0   enlace de control")
            lineas.append("  fp+8   enlace de acceso")
            lineas.append("  fp+16  direccion de retorno")
            for nombre, offset, tamano in r.parametros:
                lineas.append("  fp+{:<3} parametro {} ({} bytes)".format(offset, nombre, tamano))
            for nombre, offset, tamano in r.locales:
                lineas.append("  fp+{:<3} local {} ({} bytes)".format(offset, nombre, tamano))
            if r.temporales:
                lineas.append("  fp+{:<3} temporales t1..t{} (8 bytes c/u)".format(r.tamano_locales(), r.temporales))
        return "\n".join(lineas)

    def clases_texto(self):
        lineas = []
        for nombre, info in self.clases.items():
            padre = " : {}".format(info.padre.nombre) if info.padre is not None else ""
            lineas.append("class {}{}  tamano={}".format(nombre, padre, info.tamano_objeto()))
            lineas.append("  +0   id de clase")
            for atributo in info.atributos.values():
                lineas.append("  +{:<3} {}: {} ({} bytes)".format(atributo.offset, atributo.nombre,
                                                                   atributo.tipo, atributo.tamano))
            for metodo in info.metodos.values():
                lineas.append("  metodo {} -> {}".format(metodo.nombre, metodo.etiqueta or "?"))
        return "\n".join(lineas)
