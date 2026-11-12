"""Marco de pila MIPS de una funcion.

    Convencion de llamada (todas las palabras miden 4 bytes):

    mayor direccion   argumento 0            <- fp + 4*(n-1)
                      ...
                      argumento n-1          <- fp + 0      (el llamador los empuja en orden)
    fp ------------>  ------------------
                      $ra guardado           <- fp - 4
                      $fp del llamador       <- fp - 8
                      enlace de acceso       <- fp - 12     (llega en $v1)
                      variables y temporales <- fp - 16, fp - 20, ...
                      $s guardados, contador de manejadores
    sp ------------>  ------------------
"""
from .bloques import nombres_locales

BASE = 12


def alinear8(n):
    return (n + 7) // 8 * 8


class Marco:
    def __init__(self, funcion, s_asignadas, usa_try):
        self.funcion = funcion
        self.parametros = list(funcion.parametros)
        self.s_asignadas = s_asignadas
        self.usa_try = usa_try
        n = len(self.parametros)
        self.offsets = {nombre: 4 * (n - 1 - k) for k, nombre in enumerate(self.parametros)}
        nombres = []
        vistos = set(self.parametros) | set(s_asignadas)
        for nombre in list(funcion.tipos_vars) + [x for i in funcion.instrucciones for x in nombres_locales(i)]:
            if nombre not in vistos:
                vistos.add(nombre)
                nombres.append(nombre)
        cursor = BASE
        for nombre in nombres:
            cursor += 4
            self.offsets[nombre] = -cursor
        self.s_usadas = sorted(set(s_asignadas.values())) if not usa_try else ["$s{}".format(k) for k in range(8)]
        self.offset_s = {}
        for r in self.s_usadas:
            cursor += 4
            self.offset_s[r] = -cursor
        self.offset_exc = None
        if usa_try:
            cursor += 4
            self.offset_exc = -cursor
        self.tamano = alinear8(cursor)

    def offset(self, nombre):
        return self.offsets[nombre]
