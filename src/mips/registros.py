"""Asignacion de registros: la funcion getReg() y sus descriptores.

Dos estrategias intercambiables que ofrece el generador:

* `AsignadorPila`: cada operacion carga sus operandos en $t0..$t5, opera y guarda el resultado en su
  casilla del marco. Todo vive en la pila; no hay descriptores.
* `AsignadorRegistros`: mantiene en $t0..$t7 los valores recientes y solo toca la memoria cuando hace falta.
  Sus piezas son:
    - descriptor de registro  (registro -> nombre que contiene)
    - descriptor de direccion (nombre -> registro donde esta, ademas de su casilla en la pila)
    - conjunto de sucios      (temporales cuyo unico valor correcto esta en el registro)
  `obtener()` es getReg(): usa un registro libre; si no hay, expulsa al que se usara mas tarde dentro del
  bloque (siguiente uso mas lejano) y, si estaba sucio, lo guarda con sw antes de reutilizarlo.
  Las variables de usuario se escriben a memoria al asignarlas (porque una funcion anidada puede leerlas
  con x^k); los temporales solo se guardan al expulsarlos o al cerrar el bloque basico.
  Las variables mas usadas de una funcion (si ninguna funcion anidada las toca) viven todo el tiempo en
  $s0..$s7 y no pasan por estos descriptores.
"""
from temporales import es_temporal
from .operandos import clasificar

REGISTROS_T = ["$t{}".format(k) for k in range(8)]


class AsignadorPila:
    ESCRATCH = ["$t0", "$t1", "$t2", "$t3", "$t4", "$t5"]

    def __init__(self, emisor):
        self.e = emisor
        self.n = 0

    def inicio(self, k, res=None):
        self.n = 0

    def _siguiente(self):
        r = self.ESCRATCH[self.n]
        self.n += 1
        return r

    def usar(self, op):
        c = clasificar(op)
        if c[0] == "const" and c[1] != "str" and c[2] == 0:
            return "$zero"
        r = self._siguiente()
        self.e.cargar(r, op)
        return r

    def definir(self, res):
        return self._siguiente()

    def terminar(self, res, reg):
        self.e.guardar(reg, res)

    def liberar_operandos(self, operandos, res):
        pass

    def fin(self):
        pass

    def vaciar(self, fin_de_bloque=True, guardar=True):
        pass


class AsignadorRegistros:
    def __init__(self, emisor, analisis, s_asignadas, escritura_inmediata):
        self.e = emisor
        self.an = analisis
        self.s = s_asignadas
        self.inmediata = escritura_inmediata
        self.libres = list(REGISTROS_T)
        self.por_reg = {}        # descriptor de registro
        self.por_nombre = {}     # descriptor de direccion
        self.sucios = set()
        self.fijos = set()       # registros en uso por la instruccion en curso
        self.efimeros = []       # registros de constantes/direcciones, valen solo una instruccion
        self.k = 0
        self.res_actual = None

    # ------------------------------------------------------------- getReg
    def inicio(self, k, res=None):
        self.k = k
        self.res_actual = res
        self.fijos = set()
        self.efimeros = []

    def obtener(self):
        if self.libres:
            return self.libres.pop(0)
        candidatos = [(self.an.proximo_uso(n, self.k), r) for r, n in self.por_reg.items() if r not in self.fijos]
        if not candidatos:
            raise RuntimeError("sin registros libres")
        _, victima = max(candidatos)
        self._expulsar(victima)
        self.libres.remove(victima)
        return victima

    def _expulsar(self, reg):
        nombre = self.por_reg.pop(reg)
        del self.por_nombre[nombre]
        if nombre in self.sucios:
            self.e.guardar_casilla(reg, nombre)
            self.sucios.discard(nombre)
        self.libres.append(reg)

    def _liberar(self, reg):
        nombre = self.por_reg.pop(reg, None)
        if nombre is not None:
            del self.por_nombre[nombre]
            self.sucios.discard(nombre)
        if reg not in self.libres:
            self.libres.append(reg)
        self.fijos.discard(reg)

    def _ligar(self, reg, nombre):
        self.por_reg[reg] = nombre
        self.por_nombre[nombre] = reg

    # ------------------------------------------------------------- operandos
    def usar(self, op):
        c = clasificar(op)
        if c[0] == "const":
            if c[1] != "str" and c[2] == 0:
                return "$zero"
            r = self.obtener()
            self.fijos.add(r)
            self.efimeros.append(r)
            self.e.cargar(r, op)
            return r
        if c[0] == "var" and c[2] == 0:
            if c[1] in self.s:
                return self.s[c[1]]
            if c[1] in self.por_nombre:
                r = self.por_nombre[c[1]]
                self.fijos.add(r)
                return r
            r = self.obtener()
            self.e.cargar(r, op)
            self._ligar(r, c[1])
            self.fijos.add(r)
            return r
        r = self.obtener()
        self.fijos.add(r)
        self.efimeros.append(r)
        self.e.cargar(r, op)
        return r

    def definir(self, res):
        c = clasificar(res)
        if c[0] == "var" and c[2] == 0:
            if c[1] in self.s:
                return self.s[c[1]]
            if c[1] in self.por_nombre:
                r = self.por_nombre[c[1]]
                self.fijos.add(r)
                return r
            r = self.obtener()
            self._ligar(r, c[1])
            self.fijos.add(r)
            return r
        r = self.obtener()
        self.fijos.add(r)
        self.efimeros.append(r)
        return r

    def terminar(self, res, reg):
        c = clasificar(res)
        if c[0] == "var" and c[2] == 0:
            if c[1] in self.s:
                return
            if es_temporal(c[1]) and not self.inmediata:
                self.sucios.add(c[1])
            else:
                self.e.guardar_casilla(reg, c[1])
                self.sucios.discard(c[1])
            return
        self.e.guardar(reg, res)

    def liberar_operandos(self, operandos, res):
        """Antes de pedir el registro del resultado: suelta constantes y temporales que mueren aqui."""
        for r in self.efimeros:
            if r not in self.por_reg:
                self._liberar(r)
        self.efimeros = []
        res_nombre = clasificar(res)[1] if res and clasificar(res)[0] == "var" and clasificar(res)[2] == 0 else None
        for op in operandos:
            c = clasificar(op)
            if c[0] == "var" and c[2] == 0 and es_temporal(c[1]) and c[1] != res_nombre \
                    and c[1] in self.por_nombre and not self.an.vivo_desde(c[1], self.k + 1):
                self._liberar(self.por_nombre[c[1]])

    def fin(self):
        for r in self.efimeros:
            if r not in self.por_reg:
                self._liberar(r)
        self.efimeros = []
        for nombre in list(self.por_nombre):
            if es_temporal(nombre) and not self.an.vivo_desde(nombre, self.k + 1):
                self._liberar(self.por_nombre[nombre])

    def vaciar(self, fin_de_bloque=True, guardar=True):
        """Fin de bloque o llamada: guarda los sucios que sigan vivos y olvida todo (los $t son del llamador).

        En una llamada a mitad de bloque un sucio sigue vivo solo si se lee antes de reescribirse; al cerrar
        el bloque, solo si otro bloque lo nombra. Con guardar=False (return) no se guarda nada.
        """
        for nombre in sorted(self.sucios):
            if not guardar:
                break
            if fin_de_bloque:
                vivo = nombre in self.an.vivo_global
            else:
                vivo = nombre != self.res_actual and self.an.vivo_desde(nombre, self.k + 1)
            if vivo:
                self.e.guardar_casilla(self.por_nombre[nombre], nombre)
        self.sucios.clear()
        self.por_reg.clear()
        self.por_nombre.clear()
        self.libres = list(REGISTROS_T)
        self.fijos = set()
        self.efimeros = []
