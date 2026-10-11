import heapq
import re

PATRON_TEMPORAL = re.compile(r"^t[0-9]+$")


def es_temporal(nombre):
    return isinstance(nombre, str) and PATRON_TEMPORAL.match(nombre) is not None


class PoolTemporales:
    """Asignacion y reciclaje de variables temporales.

    `nueva()` entrega el temporal libre de menor numero, o crea uno si no hay.
    `liberar()` lo devuelve al pool en cuanto su valor ya fue consumido.
    Como siempre se reutiliza el menor numero libre, la cantidad de nombres distintos
    que aparece en una funcion es igual al maximo de temporales vivos a la vez.
    """

    def __init__(self):
        self.libres = []
        self.en_uso = set()
        self.siguiente = 1
        self.pedidos = 0

    def nueva(self):
        self.pedidos += 1
        if self.libres:
            numero = heapq.heappop(self.libres)
        else:
            numero = self.siguiente
            self.siguiente += 1
        nombre = "t{}".format(numero)
        self.en_uso.add(nombre)
        return nombre

    def liberar(self, nombre):
        if es_temporal(nombre) and nombre in self.en_uso:
            self.en_uso.discard(nombre)
            heapq.heappush(self.libres, int(nombre[1:]))

    @property
    def maximo(self):
        return self.siguiente - 1

    def vivos(self):
        return len(self.en_uso)
