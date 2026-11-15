"""Ejecuta un archivo .asm en MARS (https://dpetersanderson.github.io/) y devuelve lo que imprimio."""
import os
import subprocess
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUTA_MARS = os.environ.get("MARS_JAR", os.path.join(RAIZ, "tools", "Mars4_5.jar"))


class ErrorSimulador(Exception):
    pass


def mars_disponible():
    return os.path.exists(RUTA_MARS) and subprocess.call(
        ["java", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0


def ejecutar_asm(texto_asm, limite_segundos=60, entrada=None):
    """Ensambla y simula. Devuelve (lineas_de_salida, codigo_de_salida, texto_de_errores)."""
    if not os.path.exists(RUTA_MARS):
        raise ErrorSimulador("no se encontro MARS en {} (variable MARS_JAR)".format(RUTA_MARS))
    with tempfile.NamedTemporaryFile("w", suffix=".asm", delete=False) as archivo:
        archivo.write(texto_asm)
        ruta = archivo.name
    try:
        proceso = subprocess.run(["java", "-jar", RUTA_MARS, "nc", "me", ruta], input=entrada, capture_output=True,
                                 text=True, timeout=limite_segundos)
    except subprocess.TimeoutExpired:
        raise ErrorSimulador("la simulacion excedio {} s".format(limite_segundos))
    finally:
        os.unlink(ruta)
    salida = proceso.stdout.splitlines()
    errores = "\n".join(l for l in proceso.stderr.splitlines()
                        if "Picked up" not in l and "prefs" not in l.lower() and not l.startswith("INFO"))
    return salida, proceso.returncode, errores
