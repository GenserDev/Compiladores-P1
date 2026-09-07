import glob
import os

import pytest

from src.compilador import compilar_archivo

CASOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "casos")


def archivos(carpeta):
    return sorted(glob.glob(os.path.join(CASOS, carpeta, "*.cps")))


def nombre(ruta):
    return os.path.basename(ruta)


@pytest.mark.parametrize("ruta", archivos("validos"), ids=nombre)
def test_casos_validos(ruta):
    resultado = compilar_archivo(ruta)
    assert resultado.exitoso(), str(resultado.errores)


@pytest.mark.parametrize("ruta", archivos("invalidos"), ids=nombre)
def test_casos_invalidos(ruta):
    esperado = nombre(ruta).split("_")[0]
    resultado = compilar_archivo(ruta)
    assert resultado.errores.hay_errores(), "se esperaba el error {}".format(esperado)
    assert esperado in resultado.errores.codigos(), "se esperaba {}, se obtuvo {}".format(
        esperado, resultado.errores.codigos())


def test_programa_de_ejemplo():
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    resultado = compilar_archivo(os.path.join(raiz, "program", "ejemplo.cps"))
    assert resultado.exitoso(), str(resultado.errores)


def test_tabla_registra_ambitos():
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    resultado = compilar_archivo(os.path.join(raiz, "program", "ejemplo.cps"))
    ambitos = {fila["ambito"] for fila in resultado.tabla.filas()}
    assert "global" in ambitos
    assert any(a.startswith("global.Animal") for a in ambitos)


def test_closure_registra_captura():
    resultado = compilar_archivo(os.path.join(CASOS, "validos", "V308_closure.cps"))
    assert resultado.exitoso()
    capturas = [s.capturadas for e in resultado.tabla.entornos for s in e.simbolos.values()
                if s.categoria == "funcion"]
    assert ["base"] in capturas
