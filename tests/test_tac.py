"""Bateria de pruebas de la fase 2: generacion de codigo intermedio.

Cuatro grupos:
  1. Casos validos: se compilan a TAC, se verifica la estructura del TAC y se ejecuta en el
     interprete; lo que imprimen debe coincidir con el archivo .out.
  2. Casos invalidos: tienen errores semanticos o sintacticos, no debe generarse TAC.
  3. Pruebas de forma del TAC (golden): textos exactos para construcciones concretas.
  4. Pruebas de las estructuras auxiliares: temporales, registros de activacion, tabla de simbolos.
"""
import glob
import os
import re

import pytest

from src.compilador import compilar, compilar_archivo
from src.interprete_tac import ejecutar
from src.temporales import PoolTemporales, es_temporal

CASOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "casos_tac")
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def archivos(carpeta):
    return sorted(glob.glob(os.path.join(CASOS, carpeta, "*.cps")))


def nombre(ruta):
    return os.path.basename(ruta)


def lineas_tac(fuente, funcion="$main"):
    resultado = compilar(fuente)
    assert resultado.exitoso(), str(resultado.errores)
    return [str(i) for i in resultado.tac.funcion(funcion).instrucciones]


# ---------------------------------------------------------------------------- estructura
def verificar_estructura(tac):
    """Invariantes que debe cumplir cualquier TAC bien formado."""
    for f in tac.funciones:
        definidas = [i.res for i in f.instrucciones if i.op == "label"]
        assert len(definidas) == len(set(definidas)), "etiqueta repetida en {}".format(f.etiqueta)
        for i in f.instrucciones:
            if i.op in ("goto", "if", "iffalse", "pushtry") or i.op.startswith("if"):
                assert i.res in definidas, "salto a etiqueta inexistente {} en {}".format(i.res, f.etiqueta)
        # cada call recibe exactamente tantos param como indica, sin param huerfanos
        pendientes = 0
        for i in f.instrucciones:
            if i.op == "param":
                pendientes += 1
            elif i.op in ("call", "callind", "callv"):
                assert pendientes >= int(i.arg2), "call con menos param de los declarados en {}".format(f.etiqueta)
                pendientes -= int(i.arg2)
        assert pendientes == 0, "param sin call en {}".format(f.etiqueta)
        # los temporales usados no superan los reservados en el registro de activacion
        usados = set()
        for i in f.instrucciones:
            for operando in (i.arg1, i.arg2, i.res):
                if es_temporal(operando):
                    usados.add(operando)
        assert len(usados) <= f.registro.temporales
        assert f.instrucciones[-1].op == "return"
    etiquetas = {f.etiqueta for f in tac.funciones}
    for i in tac.instrucciones():
        if i.op == "call":
            assert i.arg1 in etiquetas, "llamada a funcion sin codigo: {}".format(i.arg1)


@pytest.mark.parametrize("ruta", archivos("validos"), ids=nombre)
def test_casos_validos_ejecutan(ruta):
    resultado = compilar_archivo(ruta)
    assert resultado.exitoso(), str(resultado.errores)
    assert resultado.tac is not None
    verificar_estructura(resultado.tac)
    esperado = open(ruta[:-4] + ".out").read().splitlines()
    assert ejecutar(resultado.tac) == esperado


@pytest.mark.parametrize("ruta", archivos("invalidos"), ids=nombre)
def test_casos_invalidos_no_generan_tac(ruta):
    esperado = nombre(ruta).split("_")[0]
    resultado = compilar_archivo(ruta)
    assert esperado in resultado.errores.codigos(), "se esperaba {}, se obtuvo {}".format(
        esperado, resultado.errores.codigos())
    assert resultado.tac is None


CASOS_FASE1 = os.path.join(RAIZ, "tests", "casos", "validos")


@pytest.mark.skipif(not os.path.isdir(CASOS_FASE1), reason="no estan los casos de la fase 1")
@pytest.mark.parametrize("ruta", sorted(glob.glob(os.path.join(CASOS_FASE1, "*.cps"))), ids=nombre)
def test_casos_validos_de_la_fase1_generan_tac_bien_formado(ruta):
    resultado = compilar_archivo(ruta)
    assert resultado.exitoso(), str(resultado.errores)
    verificar_estructura(resultado.tac)


def test_programa_del_curso_genera_tac():
    resultado = compilar_archivo(os.path.join(RAIZ, "program", "ejemplo.cps"))
    assert resultado.tac is not None
    etiquetas = [f.etiqueta for f in resultado.tac.funciones]
    assert etiquetas[0] == "$main"
    for esperada in ("makeAdder", "Animal.constructor", "Animal.speak", "Dog.speak", "getMultiples", "factorial"):
        assert esperada in etiquetas


# ---------------------------------------------------------------------------- forma del TAC
def test_precedencia_y_un_temporal():
    codigo = lineas_tac("let a: integer = 1; let b: integer = 2; let c: integer = 3;\n"
                        "let r: integer = a + b * c;")
    assert codigo[3:5] == ["t1 = $b * $c", "$r = $a + t1"]


def test_cortocircuito_en_condicion():
    codigo = lineas_tac("let a = 1; let b = 2; let c = 3; let d = 4;\n"
                        "if (a < b && c < d) { print(1); }")
    assert codigo[4:6] == ["if $a >= $b goto L1", "if $c >= $d goto L1"]
    assert "print 1" in codigo


def test_or_en_condicion_salta_al_cuerpo():
    codigo = lineas_tac("let a = 1; let b = 2; let c = 3; let d = 4;\n"
                        "if (a < b || c < d) { print(1); }")
    assert codigo[4] == "if $a < $b goto L2"
    assert codigo[5] == "if $c >= $d goto L1"
    assert codigo[6] == "L2:"


def test_while_forma_clasica():
    codigo = lineas_tac("let i: integer = 0; while (i < 3) { i = i + 1; }")
    assert codigo[1:6] == ["L1:", "if $i >= 3 goto L2", "$i = $i + 1", "goto L1", "L2:"]


def test_conversion_entero_a_flotante():
    codigo = lineas_tac("let i: integer = 2; let f: float = i; let g: float = f * i; let h: float = 3;")
    assert "$f = itof $i" in codigo
    assert "t1 = itof $i" in codigo and "$g = $f * t1" in codigo
    assert "$h = 3.0" in codigo


def test_concatenacion_convierte_a_cadena():
    codigo = lineas_tac('let n: integer = 5; print("n=" + n);')
    assert codigo[1:4] == ["t1 = tostr $n", 't1 = concat "n=", t1', "print t1"]


def test_llamada_evalua_argumentos_antes_de_los_param():
    codigo = lineas_tac("function f(a: integer, b: integer): integer { return a + b; }\n"
                        "function g(x: integer): integer { return x; }\n"
                        "let r: integer = f(g(1), g(2));")
    assert codigo[:6] == ["param 1", "t1 = call g, 1", "param 2", "t2 = call g, 1", "param t1", "param t2"]
    assert codigo[6] == "$r = call f, 2"


def test_acceso_a_variable_de_funcion_externa_usa_enlace_de_acceso():
    resultado = compilar("function externa(): integer {\n  let x: integer = 1;\n"
                         "  function interna(): integer { x = x + 1; return x; }\n  return interna();\n}\n")
    interna = [str(i) for i in resultado.tac.funcion("externa.interna").instrucciones]
    assert interna[0] == "x^1 = x^1 + 1"
    assert resultado.tac.funcion("externa.interna").registro.nivel == 2


def test_llamada_virtual_solo_si_hay_sobrescritura():
    sin = compilar("class A { function f(): integer { return 1; } }\nlet a: A = new A();\nprint(a.f());")
    assert "callv" not in sin.tac.texto()
    con = compilar("class A { function f(): integer { return 1; } }\n"
                   "class B : A { function f(): integer { return 2; } }\n"
                   "let a: A = new B();\nprint(a.f());")
    assert "callv A.f, 1" in con.tac.texto()
    assert "VTABLE B" in con.tac.texto()


def test_inicializadores_de_atributos_en_init():
    resultado = compilar("class A { let n: integer = 7; function constructor() { } }\nlet a: A = new A();")
    init = [str(i) for i in resultado.tac.funcion("A.$init").instrucciones]
    assert init[0] == "this.n = 7"
    principal = [str(i) for i in resultado.tac.funcion("$main").instrucciones]
    assert principal[:2] == ["t1 = new A, 16", "param t1"]
    assert "call A.$init, 1" in principal


def test_try_catch_forma():
    codigo = lineas_tac("try { print(1); } catch (e) { print(e); }")
    assert codigo[:3] == ["pushtry L1", "print 1", "poptry"]
    assert "e = getexc" in codigo


def test_break_dentro_de_try_cierra_el_manejador():
    codigo = lineas_tac("while (true) { try { break; } catch (e) { print(e); } }")
    indice = codigo.index("pushtry L3")
    assert codigo[indice + 1:indice + 3] == ["poptry", "goto L2"]


def test_foreach_usa_len_e_indice():
    codigo = lineas_tac("let a: integer[] = [1,2]; foreach (x in a) { print(x); }")
    assert "t2 = len t1" in codigo
    assert "if t3 >= t2 goto L3" in codigo
    assert "x = t1[t3]" in codigo


# ---------------------------------------------------------------------------- temporales
def test_pool_reutiliza_el_menor_numero_libre():
    pool = PoolTemporales()
    t1, t2, t3 = pool.nueva(), pool.nueva(), pool.nueva()
    assert (t1, t2, t3) == ("t1", "t2", "t3")
    pool.liberar(t2)
    pool.liberar(t1)
    assert pool.nueva() == "t1"
    assert pool.nueva() == "t2"
    assert pool.maximo == 3 and pool.pedidos == 5


def test_pool_ignora_nombres_que_no_son_temporales():
    pool = PoolTemporales()
    pool.liberar("x")
    pool.liberar("t9")
    assert pool.nueva() == "t1"


def test_cadena_de_sumas_usa_un_solo_temporal():
    resultado = compilar("let a=1; let b=2; let c=3; let d=4; let e=5;\nlet r: integer = a + b + c + d + e;")
    registro = resultado.tac.funcion("$main").registro
    assert registro.temporales == 1
    assert registro.total_temporales >= 3


def test_expresion_balanceada_necesita_log_temporales():
    resultado = compilar("let a=1; let b=2; let c=3; let d=4; let e=5; let f=6; let g=7; let h=8;\n"
                         "let r: integer = (a + b) * (c + d) - (e + f) * (g - h);")
    registro = resultado.tac.funcion("$main").registro
    assert registro.temporales == 3
    assert registro.total_temporales > registro.temporales


def test_un_temporal_liberado_no_se_reutiliza_mientras_esta_vivo():
    codigo = lineas_tac("let a=1; let b=2; let c=3; let d=4;\nlet r: integer = (a + b) * (c + d);")
    assert codigo[4:7] == ["t1 = $a + $b", "t2 = $c + $d", "$r = t1 * t2"]


# ---------------------------------------------------------------------------- registros de activacion
def test_registro_de_activacion_layout():
    resultado = compilar("function f(a: integer, b: boolean, c: string): integer {\n"
                         "  let x: integer = a + 1;\n  return x;\n}\n")
    registro = resultado.tac.funcion("f").registro
    assert registro.parametros == [("a", 24, 4), ("b", 28, 1), ("c", 32, 8)]
    assert registro.locales == [("x", 40, 4)]
    assert registro.temporales == 1
    assert registro.tamano_total() == 56      # 44 de locales alineado a 48, mas un temporal de 8


def test_locales_de_bloques_hermanos_comparten_espacio():
    resultado = compilar("function f(): integer {\n  { let a: integer = 1; let b: integer = 2; }\n"
                         "  { let c: integer = 3; }\n  return 0;\n}\n")
    registro = resultado.tac.funcion("f").registro
    offsets = {n: o for n, o, _ in registro.locales}
    assert offsets["a"] == 24 and offsets["b"] == 28 and offsets["c"] == 24
    assert registro.tamano_locales() == 32


def test_metodo_reserva_this_primero():
    resultado = compilar("class A { let n: integer; function f(x: integer): integer { return x; } }")
    registro = resultado.tac.funcion("A.f").registro
    assert registro.parametros[0] == ("this", 24, 8)
    assert registro.parametros[1][0] == "x"


def test_disposicion_de_objetos_con_herencia():
    resultado = compilar("class A { let a: integer; let s: string; }\nclass B : A { let b: boolean; }\n")
    a, b = resultado.tabla.clases["A"], resultado.tabla.clases["B"]
    assert a.offset_campo("a") == 8 and a.offset_campo("s") == 16 and a.tamano_objeto() == 24
    assert b.offset_campo("a") == 8 and b.offset_campo("s") == 16
    assert b.offset_campo("b") == 24 and b.tamano_objeto() == 32


def test_tabla_de_simbolos_tiene_direcciones():
    resultado = compilar("let g: integer = 1;\nfunction f(p: integer): integer { let l: integer = p; return l; }\n")
    filas = {(f["nombre"], f["categoria"]): f for f in resultado.tabla.filas()}
    assert filas[("g", "variable")]["almacen"] == "global" and filas[("g", "variable")]["direccion"] == "gp+0"
    assert filas[("p", "parametro")]["direccion"] == "fp+24"
    assert filas[("l", "variable")]["direccion"] == "fp+28"
    assert filas[("f", "funcion")]["direccion"] == "f"
    assert resultado.tabla.area_global == 4


def test_variables_con_nombre_de_temporal_no_colisionan():
    resultado = compilar("function f(): integer { let t1: integer = 2; let t2: integer = t1 + 1; return t2; }")
    texto = resultado.tac.texto()
    assert "t1# = 2" in texto


def test_error_semantico_no_genera_tac():
    resultado = compilar("let x: integer = \"a\";")
    assert resultado.tac is None
    assert "E104" in resultado.errores.codigos()


def test_sin_generar_solo_analiza():
    resultado = compilar("let x = 1;", generar=False)
    assert resultado.exitoso() and resultado.tac is None
