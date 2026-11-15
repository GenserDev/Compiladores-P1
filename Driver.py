import sys

from src.compilador import compilar_archivo

USO = ("uso: python3 Driver.py <archivo.cps> [--arbol] [--tabla] [--tac] [--lineas] [--registros] [--dot salida.dot]\n"
       "                                  [--mips salida.asm] [--sin-registros] [--ejecutar]")


def main(argv):
    if len(argv) < 2:
        print(USO)
        return 1
    resultado = compilar_archivo(argv[1])
    if "--arbol" in argv:
        print(resultado.arbol_texto())
    if "--tabla" in argv and resultado.tabla is not None:
        print(resultado.tabla)
    if "--tac" in argv and resultado.tac is not None:
        print(resultado.tac.texto(con_lineas="--lineas" in argv))
    if "--registros" in argv and resultado.tabla is not None and resultado.tac is not None:
        print(resultado.tabla.registros_texto())
        print(resultado.tabla.clases_texto())
    if "--dot" in argv:
        destino = argv[argv.index("--dot") + 1]
        with open(destino, "w") as archivo:
            archivo.write(resultado.arbol_dot())
        print("arbol escrito en {}".format(destino))
    if resultado.exitoso() and ("--mips" in argv or "--ejecutar" in argv):
        modo = "pila" if "--sin-registros" in argv else "registros"
        asm = resultado.mips(modo)
        if "--mips" in argv:
            destino = argv[argv.index("--mips") + 1]
            with open(destino, "w") as archivo:
                archivo.write(asm)
            print("codigo MIPS ({}) escrito en {}".format(modo, destino))
        if "--ejecutar" in argv:
            from src.mips.simulador import ejecutar_asm, ErrorSimulador
            try:
                salida, codigo, errores = ejecutar_asm(asm)
            except ErrorSimulador as e:
                print("error del simulador: {}".format(e))
                return 2
            print("\n".join(salida))
            if errores:
                print(errores, file=sys.stderr)
            return codigo
    if resultado.exitoso():
        print("compilacion exitosa: 0 errores")
        return 0
    print(resultado.errores)
    print("{} error(es)".format(len(resultado.errores)))
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
