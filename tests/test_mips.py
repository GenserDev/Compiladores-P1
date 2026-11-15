"""Bateria de pruebas de la fase 3: generacion de codigo MIPS.

Grupos:
  1. Diferencial: cada programa valido se compila a MIPS (en los dos modos de asignacion de registros),
     se simula en MARS y lo que imprime debe coincidir con el archivo .out (que sale del interprete TAC
     o, en M10, de calcularlo a mano).
  2. Errores de ejecucion: excepciones sin capturar; el programa termina con codigo 1 y el mensaje esperado.
  3. Casos invalidos: con errores de compilacion no se genera TAC ni MIPS.
  4. Forma del codigo: secuencia de llamada y retorno, marco de pila, uso de $t/$s, rutinas del runtime.
  5. getReg: pruebas unitarias del asignador (expulsion del registro de uso mas lejano, spills).
  6. Comparacion de los dos modos: el modo registros hace menos accesos a memoria.
"""
import glob
import os
import re

import pytest

from src.compilador import compilar, compilar_archivo
from src.mips.bloques import AnalisisFuncion
from src.mips.registros import AsignadorRegistros, REGISTROS_T
from src.mips.simulador import ejecutar_asm, mars_disponible

AQUI = os.path.dirname(os.path.abspath(__file__))
MODOS = ["registros", "pila"]
requiere_mars = pytest.mark.skipif(not mars_disponible(), reason="falta Java o tools/Mars4_5.jar")


def archivos(*partes):
    return sorted(glob.glob(os.path.join(AQUI, *partes, "*.cps")))


def nombre(ruta):
    return os.path.basename(ruta)


def asm_de(fuente, modo="registros"):
    resultado = compilar(fuente)
    assert resultado.exitoso(), str(resultado.errores)
    return resultado.mips(modo)


def funcion_asm(asm, etiqueta):
    """Texto de una funcion dentro del .asm (desde su etiqueta hasta la siguiente funcion)."""
    m = re.search(r"^{}:\n(.*?)(?=^f_(?!\w*_ret:)\w+:|^# ---- rutinas|\Z)".format(re.escape(etiqueta)), asm, re.S | re.M)
    assert m, "no se encontro {} en el ensamblador".format(etiqueta)
    return m.group(1)


def instrucciones(texto):
    """Instrucciones sin comentarios ni etiquetas."""
    salida = []
    for linea in texto.splitlines():
        linea = linea.split("#")[0].strip()
        if linea and not linea.endswith(":"):
            salida.append(linea)
    return salida


# ---------------------------------------------------------------------------- 1. diferencial
CASOS_VALIDOS = archivos("casos_tac", "validos") + archivos("casos_mips", "validos")


@requiere_mars
@pytest.mark.parametrize("modo", MODOS)
@pytest.mark.parametrize("ruta", CASOS_VALIDOS, ids=nombre)
def test_mips_coincide_con_la_salida_esperada(ruta, modo):
    resultado = compilar_archivo(ruta)
    assert resultado.exitoso(), str(resultado.errores)
    esperado = open(ruta[:-4] + ".out").read().splitlines()
    salida, codigo, errores = ejecutar_asm(resultado.mips(modo))
    assert errores == "", errores
    assert codigo == 0
    assert salida == esperado


# ---------------------------------------------------------------------------- 2. errores de ejecucion
@requiere_mars
@pytest.mark.parametrize("modo", MODOS)
@pytest.mark.parametrize("ruta", archivos("casos_mips", "errores_ejecucion"), ids=nombre)
def test_excepcion_sin_capturar_termina_con_error(ruta, modo):
    resultado = compilar_archivo(ruta)
    assert resultado.exitoso()
    esperado = open(ruta[:-4] + ".out").read().splitlines()
    salida, codigo, _ = ejecutar_asm(resultado.mips(modo))
    assert salida == esperado
    assert codigo == 1


# ---------------------------------------------------------------------------- 3. invalidos
@pytest.mark.parametrize("ruta", archivos("casos_tac", "invalidos"), ids=nombre)
def test_con_errores_no_se_genera_codigo(ruta):
    resultado = compilar_archivo(ruta)
    assert resultado.errores.hay_errores()
    assert resultado.tac is None


def test_driver_no_escribe_asm_si_hay_errores(tmp_path):
    import Driver
    destino = tmp_path / "salida.asm"
    ruta = os.path.join(AQUI, "casos_tac", "invalidos", "E100_suma_booleano.cps")
    assert Driver.main(["Driver.py", ruta, "--mips", str(destino)]) == 1
    assert not destino.exists()


@requiere_mars
def test_driver_genera_y_ejecuta(tmp_path, capsys):
    import Driver
    destino = tmp_path / "salida.asm"
    ruta = os.path.join(AQUI, "casos_mips", "validos", "M06_recursion.cps")
    assert Driver.main(["Driver.py", ruta, "--mips", str(destino), "--ejecutar"]) == 0
    assert destino.exists() and ".globl main" in destino.read_text()
    assert "6765" in capsys.readouterr().out


# ---------------------------------------------------------------------------- 4. forma del codigo
FACT = "function fact(n: integer): integer { if (n <= 1) { return 1; } return n * fact(n - 1); }\nprint(fact(5));\n"


@pytest.mark.parametrize("modo", MODOS)
def test_prologo_y_epilogo_simetricos(modo):
    asm = asm_de(FACT, modo)
    cuerpo = instrucciones(funcion_asm(asm, "f_fact"))
    marco = int(re.match(r"addiu \$sp, \$sp, -(\d+)", cuerpo[0]).group(1))
    assert marco % 8 == 0
    assert cuerpo[1:5] == ["sw   $ra, {}($sp)".format(marco - 4), "sw   $fp, {}($sp)".format(marco - 8),
                           "sw   $v1, {}($sp)".format(marco - 12), "addiu $fp, $sp, {}".format(marco)]
    assert cuerpo[-4:] == ["lw   $ra, -4($fp)", "move $sp, $fp", "lw   $fp, -8($fp)", "jr   $ra"]


@pytest.mark.parametrize("modo", MODOS)
def test_secuencia_de_llamada(modo):
    cuerpo = instrucciones(funcion_asm(asm_de(FACT, modo), "f_fact"))
    i = cuerpo.index("jal  f_fact")
    # el argumento se empuja justo antes, y el llamador lo saca justo despues
    assert cuerpo[i - 2] == "lw   $v1, -12($v1)" or cuerpo[i - 2] == "move $v1, $fp"
    assert any(c == "addiu $sp, $sp, -4" for c in cuerpo[:i])
    assert cuerpo[i + 1] == "addiu $sp, $sp, 4"
    # el valor de retorno llega en $v0
    assert cuerpo[i + 2].endswith(", $v0")


def test_main_llama_al_programa_y_termina():
    asm = asm_de("print(1);")
    assert re.search(r"main:\n    li   \$v1, 0\n    jal  f_S_main\n    li   \$v0, 10\n    syscall", asm)


def test_enlace_de_acceso_sube_tantos_niveles_como_hace_falta():
    fuente = ("function a(): integer { let x: integer = 5;\n"
              "  function b(): integer { function c(): integer { return x; } return c(); }\n"
              "  return b(); }\nprint(a());\n")
    asm = asm_de(fuente, "pila")
    c = instrucciones(funcion_asm(asm, "f_a__b__c"))
    # x esta dos niveles arriba: dos lw sobre -12 antes de leerlo
    assert c[5:8] == ["lw   $t0, -12($fp)", "lw   $t0, -12($t0)", "lw   $t0, -16($t0)"]


def test_solo_se_emiten_las_rutinas_usadas():
    simple = asm_de("print(1 + 2);")
    assert "__concat:" not in simple and "__itoa:" not in simple and "__throw:" not in simple
    con_texto = asm_de('let n: integer = 3; print("n=" + n);')
    assert "__concat:" in con_texto and "__itoa:" in con_texto
    con_division = asm_de("let a: integer = 6; let b: integer = 0; print(a / b);")
    assert "__throw:" in con_division


def test_modo_pila_solo_usa_t0_a_t5_y_nunca_s():
    asm = asm_de(open(os.path.join(AQUI, "casos_mips", "validos", "M01_presion_registros.cps")).read(), "pila")
    cuerpo = "\n".join(instrucciones(funcion_asm(asm, "f_f")))
    assert not re.search(r"\$s[0-7]", cuerpo)
    assert not re.search(r"\$t[67]", cuerpo)


def test_modo_registros_usa_s_para_las_variables_mas_usadas():
    asm = asm_de(open(os.path.join(AQUI, "casos_mips", "validos", "M01_presion_registros.cps")).read(), "registros")
    cuerpo = funcion_asm(asm, "f_f")
    assert re.search(r"sw   \$s0, -\d+\(\$fp\)", cuerpo)          # prologo: guarda $s0 del llamador
    assert re.search(r"lw   \$s0, -\d+\(\$fp\)", cuerpo)          # epilogo: lo restaura


def test_variable_capturada_no_va_a_un_registro_s():
    fuente = ("function f(): integer { let c: integer = 0; let d: integer = 0;\n"
              "  function g(): integer { c = c + 1; return c; }\n"
              "  d = d + 1; d = d + 2; g(); g(); return c + d; }\nprint(f());\n")
    cuerpo = funcion_asm(asm_de(fuente), "f_f")
    # d (no capturada, 3 usos) si pasa a $s; c (la usa g con c^1) se queda en memoria
    assert "$s0" in cuerpo and "$s1" not in cuerpo


def test_funcion_con_try_guarda_todos_los_s_y_el_contador_de_manejadores():
    fuente = "function f(): integer { try { return 1 / 0; } catch (e) { return 2; } }\nprint(f());\n"
    cuerpo = funcion_asm(asm_de(fuente), "f_f")
    for k in range(8):
        assert "sw   $s{}, ".format(k) in cuerpo
    assert "lw   $t8, exc_n" in cuerpo and "sw   $t8, exc_n" in cuerpo


def test_vtable_y_despacho_virtual():
    fuente = ("class A { function f(): integer { return 1; } }\n"
              "class B : A { function f(): integer { return 2; } }\n"
              "let a: A = new B(); print(a.f());\n")
    asm = asm_de(fuente)
    assert re.search(r"vt_A: \.word cn_A, f_A__f", asm) and re.search(r"vt_B: \.word cn_B, f_B__f", asm)
    cuerpo = funcion_asm(asm, "f_S_main")
    assert "jalr $t9" in cuerpo


# ---------------------------------------------------------------------------- 5. getReg
class EmisorFalso:
    def __init__(self):
        self.guardados = []
        self.cargados = []

    def guardar_casilla(self, reg, nombre):
        self.guardados.append((reg, nombre))

    def cargar(self, reg, op):
        self.cargados.append((reg, op))

    def guardar(self, reg, op):
        self.guardados.append((reg, op))


def asignador_para(fuente_tac_ops):
    """Un AsignadorRegistros sobre una funcion TAC minima construida a mano."""
    from tac import Instruccion, FuncionTAC

    class Reg:
        nivel = 0
        padre = None
        etiqueta = "$main"

    funcion = FuncionTAC("$main", Reg(), [], True)
    funcion.instrucciones = [Instruccion(*op) for op in fuente_tac_ops]
    analisis = AnalisisFuncion(funcion)
    emisor = EmisorFalso()
    return AsignadorRegistros(emisor, analisis, {}, False), emisor


def test_getreg_entrega_registros_distintos_mientras_haya_libres():
    a, _ = asignador_para([("copy", "1", None, "t1")] * 3)
    a.inicio(0)
    regs = [a.obtener() for _ in range(len(REGISTROS_T))]
    assert len(set(regs)) == len(REGISTROS_T)


def test_getreg_expulsa_el_de_uso_mas_lejano_y_guarda_si_esta_sucio():
    ops = [("copy", "1", None, "t{}".format(k)) for k in range(1, 9)]          # t1..t8 definidos
    ops += [("+", "t8", "t7", "t9"), ("+", "t6", "t5", "t10"), ("+", "t4", "t3", "t11"),
            ("+", "t2", "t2", "t12"), ("copy", "t1", None, "t13")]            # t1 se usa al final de todo
    a, emisor = asignador_para(ops)
    for k in range(8):
        a.inicio(k)
        r = a.definir("t{}".format(k + 1))
        a.terminar("t{}".format(k + 1), r)
    assert not a.libres
    a.inicio(8)                      # t9 = t8 + t7: t8 y t7 estan en uso y no pueden expulsarse
    a.usar("t8")
    a.usar("t7")
    r_nuevo = a.definir("t9")
    # la victima es t1 (su siguiente uso es el mas lejano) y, como estaba sucio, se guardo en su casilla
    assert "t1" not in a.por_nombre and a.por_nombre["t9"] == r_nuevo
    assert emisor.guardados == [(r_nuevo, "t1")]


def test_getreg_no_guarda_lo_que_esta_limpio():
    ops = [("copy", "1", None, "x")] + [("copy", "1", None, "t{}".format(k)) for k in range(1, 9)] + \
          [("copy", "x", None, "t9")]
    a, emisor = asignador_para(ops)
    a.inicio(0)
    r = a.usar("x")                      # variable de usuario: limpia, esta tambien en memoria
    a.fijos = set()
    for k in range(1, 8):
        a.inicio(k)
        reg = a.definir("t{}".format(k))
        a.terminar("t{}".format(k), reg)
        a.fijos = set()
    a.inicio(9)
    a.obtener()                          # presion: expulsa algo
    assert all(nombre != "x" for _, nombre in emisor.guardados)


def test_vaciar_guarda_los_sucios_vivos_y_olvida_todo():
    ops = [("copy", "1", None, "t1"), ("goto", None, None, "L1"), ("label", None, None, "L1"),
           ("copy", "t1", None, "t2")]
    a, emisor = asignador_para(ops)
    a.inicio(0)
    r = a.definir("t1")
    a.terminar("t1", r)
    a.vaciar()
    assert emisor.guardados == [(r, "t1")]         # t1 se usa en otro bloque, hay que guardarlo
    assert not a.por_nombre and len(a.libres) == len(REGISTROS_T)


# ---------------------------------------------------------------------------- 6. comparacion de modos
def accesos_a_memoria(asm):
    return sum(1 for l in instrucciones(asm) if re.match(r"(lw|sw)\s", l))


@pytest.mark.parametrize("caso", ["M01_presion_registros", "M06_recursion", "M08_flujo_control"])
def test_modo_registros_hace_menos_accesos_a_memoria(caso):
    fuente = open(os.path.join(AQUI, "casos_mips", "validos", caso + ".cps")).read()
    assert accesos_a_memoria(asm_de(fuente, "registros")) < accesos_a_memoria(asm_de(fuente, "pila"))
