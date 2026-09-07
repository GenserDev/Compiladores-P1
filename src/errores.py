class ErrorSemantico:
    def __init__(self, codigo, mensaje, linea, columna):
        self.codigo = codigo
        self.mensaje = mensaje
        self.linea = linea
        self.columna = columna

    def __str__(self):
        return "[{}] linea {}:{} {}".format(self.codigo, self.linea, self.columna, self.mensaje)


class ErrorSintactico(ErrorSemantico):
    pass


class ColectorErrores:
    def __init__(self):
        self.errores = []

    def agregar(self, codigo, mensaje, ctx):
        linea, columna = ubicacion(ctx)
        self.errores.append(ErrorSemantico(codigo, mensaje, linea, columna))

    def agregar_sintactico(self, mensaje, linea, columna):
        self.errores.append(ErrorSintactico("E000", mensaje, linea, columna))

    def hay_errores(self):
        return len(self.errores) > 0

    def codigos(self):
        return [e.codigo for e in self.errores]

    def ordenados(self):
        return sorted(self.errores, key=lambda e: (e.linea, e.columna))

    def __len__(self):
        return len(self.errores)

    def __iter__(self):
        return iter(self.ordenados())

    def __str__(self):
        return "\n".join(str(e) for e in self.ordenados())


def ubicacion(ctx):
    if ctx is None:
        return 0, 0
    if hasattr(ctx, "start"):
        return ctx.start.line, ctx.start.column
    if hasattr(ctx, "symbol"):
        return ctx.symbol.line, ctx.symbol.column
    return 0, 0
