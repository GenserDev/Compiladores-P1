# Generacion de codigo MIPS (fase 3)

El ultimo paso del compilador traduce el codigo de tres direcciones (TAC) de la fase 2 a ensamblador MIPS32
para el simulador **MARS 4.5**. Este documento describe la convencion de llamada, la asignacion de registros
(`getReg`), la representacion de los datos y la forma de ejecutar y probar el resultado.

```
Compiscript --ANTLR--> arbol --analizador--> arbol anotado --generador--> TAC --src/mips--> archivo .asm --MARS--> salida
```

El backend completo vive en `src/mips/` y se llama con `resultado.mips(modo)` o desde la linea de comandos
con `Driver.py archivo.cps --mips salida.asm`.

## Como ejecutar

```bash
python3 Driver.py programa.cps --mips salida.asm              # genera el ensamblador (modo registros)
python3 Driver.py programa.cps --mips salida.asm --sin-registros   # modo "todo en la pila"
python3 Driver.py programa.cps --ejecutar                     # genera y simula en MARS, imprime la salida
java -jar tools/Mars4_5.jar nc salida.asm                     # simular el .asm a mano
```

MARS necesita Java 8 o mayor. El jar esta en `tools/Mars4_5.jar`; si se quiere usar otro, se indica con la
variable de entorno `MARS_JAR`. En el IDE, el boton **Ejecutar en MARS** hace lo mismo, la lista desplegable
elige el modo de registros, la pestaña **Codigo MIPS** muestra el ensamblador y **Guardar .asm** lo escribe a disco.
El codigo de salida de `Driver.py --ejecutar` es el del programa simulado (1 si termino con una excepcion
sin capturar).

## Convencion de llamada

Todas las palabras miden 4 bytes (enteros, booleanos, punteros y floats de precision simple). Los argumentos
viajan por la pila, el valor de retorno en `$v0` y el enlace de acceso en `$v1`.

```
direcciones altas
                  +----------------------+
                  | argumento 0          |  fp + 4*(n-1)     el llamador los empuja en orden
                  | ...                  |                   (el receptor `this` de un metodo es el 0)
                  | argumento n-1        |  fp + 0
   fp ----------> +----------------------+
                  | $ra del llamador     |  fp - 4
                  | $fp del llamador     |  fp - 8           enlace de control
                  | enlace de acceso     |  fp - 12          llego en $v1
                  | variables y          |  fp - 16, -20 ... una palabra por nombre
                  | temporales           |
                  | $s guardados         |  solo los que la funcion usa
                  | contador de          |  solo si la funcion tiene try
                  | manejadores          |
   sp ----------> +----------------------+
direcciones bajas
```

**Llamador** (`call f, n`): los `param` ya empujaron los argumentos (`addiu $sp,$sp,-4 ; sw r,0($sp)`). Luego
deja en `$v1` el enlace de acceso, hace `jal f` y al volver libera los argumentos con `addiu $sp,$sp,4*n`.
El resultado esta en `$v0`.

**Prologo** (marco de `F` bytes, multiplo de 8):

```
addiu $sp, $sp, -F
sw    $ra, F-4($sp)
sw    $fp, F-8($sp)
sw    $v1, F-12($sp)
addiu $fp, $sp, F          # fp apunta a los argumentos
```

**Epilogo** (etiqueta `f_nombre_ret`, todos los `return` saltan aqui):

```
lw    $ra, -4($fp)
move  $sp, $fp
lw    $fp, -8($fp)
jr    $ra
```

Como `fp` y `sp` se restauran desde el marco, una funcion siempre devuelve la pila exactamente como la
recibio (menos los argumentos, que saca el llamador). Esto es lo que permite saltar a procedimientos y volver
sin perder el estado de la memoria, incluso con recursion de miles de niveles.

**Enlace de acceso (closures).** Cada funcion tiene un nivel (`$main` es 0, una funcion dentro de otra tiene
el nivel de la externa mas uno). Para llamar a una funcion de nivel `k` desde el nivel `c`, el llamador
calcula `c - (k - 1)` y sigue ese numero de enlaces desde su propio `fp` (`lw $v1, -12($v1)` repetido); con 0
saltos el enlace es su propio marco. Una variable `x^k` se lee subiendo `k` enlaces y accediendo a su casilla
en el marco de esa funcion:

```
x^2:   lw $t0, -12($fp)      # marco de la funcion externa
       lw $t0, -12($t0)      # marco de la funcion externa de esa
       lw $t0, off($t0)
```

**Valores funcion.** `x = &f` produce la direccion de un descriptor en `.data` (`fd_f: .word f_f, nivel`).
`callind` lee de ahi la direccion y el nivel del destino y calcula en tiempo de ejecucion cuantos enlaces
subir, asi que una funcion anidada guardada en una variable se llama con el entorno correcto.

**Metodos y despacho dinamico.** Un objeto es `[puntero a vtable][campo 0][campo 1]...`; los campos del padre
van primero, por lo que un campo heredado tiene el mismo desplazamiento en toda la jerarquia. La vtable de
cada clase es `vt_Clase: .word cn_Clase, metodo_0, metodo_1, ...`: la primera palabra apunta al nombre de la
clase (lo usa `print` de un objeto) y las demas son los metodos, con el mismo indice para el mismo nombre en
todas las clases. `callv Clase.m, n` toma el receptor (el primer argumento ya empujado), carga su vtable y
salta con `jalr` a la entrada de `m`.

## Representacion de los datos

| Dato | Representacion |
|---|---|
| integer, boolean | palabra con signo (boolean 0/1) |
| float | precision simple IEEE 754 en una palabra; las operaciones pasan por `$f4`/`$f6` con `mtc1`/`mfc1` |
| string | puntero a bytes terminados en cero (literales en `.data`, resultados de `concat` en el heap) |
| arreglo | `[longitud][elem 0][elem 1]...` reservado con `sbrk` |
| objeto | ver arriba, reservado con `sbrk` |
| null | 0 |
| variable global | `g_nombre: .word 0` |

El heap nunca se libera (no hay recolector de basura). Un float ocupa 4 bytes, no 8 como en el TAC; el
supuesto esta documentado porque `float` en Compiscript no fija la precision.

## Asignacion de registros

El generador ofrece las dos opciones del enunciado; se elige con `--sin-registros` o en el IDE.

### Modo pila (`AsignadorPila`)

Cada operacion carga sus operandos de su casilla del marco en `$t0..$t5`, opera y guarda el resultado en la
casilla de destino. No hay estado entre instrucciones: es el modo mas simple y sirve como referencia.

### Modo registros (`AsignadorRegistros`, la funcion `getReg()`)

Mantiene valores en `$t0..$t7` entre instrucciones. Se apoya en un analisis previo (`src/mips/bloques.py`):

* **Bloques basicos.** Empiezan en la primera instruccion, en cada etiqueta y despues de cada salto o `return`.
* **Vida de un nombre.** Dentro de un bloque se avanza desde la instruccion actual: si la primera referencia
  *lee* el nombre, su valor sigue vivo; si lo *escribe* sin leerlo, el valor actual esta muerto. Si el bloque
  termina sin mencionarlo, sigue vivo solo cuando otro bloque lo nombra.

El asignador lleva tres estructuras:

| Estructura | Contenido |
|---|---|
| descriptor de registro | que nombre contiene cada `$t` |
| descriptor de direccion | en que registro esta cada nombre (ademas de su casilla en la pila) |
| conjunto de sucios | temporales cuyo unico valor correcto esta en el registro |

`getReg()` (`obtener`) sigue este orden:

1. Si hay un registro libre, lo usa.
2. Si no, entre los registros que la instruccion actual no esta usando, expulsa al que contiene el valor cuyo
   **siguiente uso esta mas lejos** dentro del bloque (un valor sin mas usos sale primero).
3. Si el expulsado estaba sucio, lo guarda con `sw` en su casilla antes de reutilizar el registro.

Reglas que mantienen la correccion:

* Un temporal que muere en una instruccion libera su registro **antes** de pedir el del resultado, asi
  `t1 = t1 + t2` puede escribir sobre su propio operando.
* Las variables de usuario se escriben a memoria en cada asignacion (escritura inmediata), porque una funcion
  anidada puede leerlas con `x^k` sin que el compilador lo vea. Un temporal solo se guarda cuando lo expulsan,
  al cerrar el bloque si lo usa otro bloque, o antes de una llamada si todavia se va a leer.
* **Llamadas.** Los `$t` son del llamador: antes de un `jal`/`jalr` se guardan los sucios vivos y se olvidan
  todos los descriptores. Con `return` no se guarda nada, el marco se descarta.
* **Etiquetas y saltos.** Al llegar a una etiqueta y antes de un salto se vacian los registros (los sucios
  vivos van a memoria). Los operandos de un salto condicional se leen antes de vaciar.
* **Constantes.** El cero es `$zero`; el resto se carga con `li`/`la` en un registro que vive una sola
  instruccion. Las comparaciones y la suma/resta con constantes pequenas usan inmediatos.
* **Registros `$s0..$s7`.** Las variables de usuario mas referenciadas de una funcion (minimo dos usos) viven
  todo el tiempo en un `$s` y no pasan por la pila ni por los descriptores. Quedan fuera las que alguna
  funcion anidada toca por `x^k`, los parametros y las funciones con `try`. Como `$s` es callee-save, el
  prologo guarda los que la funcion usa y el epilogo los restaura.
* **Funciones con `try`.** Todos los temporales y variables se escriben a memoria al definirse (un `throw` puede
  saltar al `catch` desde cualquier punto), no usan `$s` para variables, y guardan los ocho `$s` del llamador
  porque una excepcion desarma marcos de funciones que habian modificado `$s` sin restaurarlos.

El resultado se ve en cualquier programa con `Driver.py programa.cps --mips a.asm` y `--mips b.asm --sin-registros`.
`tests/test_mips.py` comprueba que el modo registros hace menos accesos a memoria que el modo pila.

## Traduccion de cada instruccion

| TAC | MIPS |
|---|---|
| `x = y` | `move` / `li` / `la` |
| `x = y + z`, `-`, `*` | `addu`/`addiu`, `subu`, `mul` |
| `x = y / z`, `%` | comprueba cero (`bnez`, si no lanza), `div` y `mflo` / `mfhi` |
| `x = y < z` y demas | pseudo-instrucciones `slt sle sgt sge seq sne` |
| floats | `mtc1` a `$f4`/`$f6`, `add.s sub.s mul.s div.s`, `c.lt.s c.le.s c.eq.s` + `bc1t`, `mfc1` |
| `x = itof y` | `mtc1` + `cvt.s.w` + `mfc1` |
| `if a < b goto L` | `blt`/`ble`/`bgt`/`bge`/`beq`/`bne` (con inmediato si `b` es constante) |
| `if x goto L` / `ifFalse` | `bnez` / `beqz` |
| `concat`, `tostr` | rutinas `__concat`, `__itoa`, `__ftoa`, `__boolstr`, `__objstr`, `__arrstr` |
| `==` entre strings | `__strcmp` (compara contenido, no punteros) |
| `newarray`, `new` | `sbrk` (syscall 9) y escritura de la longitud o del puntero a la vtable |
| `a[i]`, `a[i] = v` | comprueba `0 <= i < longitud` (un solo `bltu`), calcula la direccion y `lw`/`sw` |
| `o.f`, `o.f = v` | `lw`/`sw` con el desplazamiento del campo |
| `print x` | syscall 1 para enteros; el resto se convierte a string y se imprime con `__print_str` |
| `pushtry`, `poptry`, `getexc` | ver excepciones |

## Excepciones

`pushtry L` llama a `__pushtry`, que guarda en una pila de manejadores (`exc_pila`, en `.data`) la direccion de
`L`, el `$sp` y el `$fp` actuales. `__throw` (con el mensaje en `$a0`) saca el manejador mas reciente,
restaura `$sp` y `$fp` y salta a su direccion; `getexc` lee el mensaje. Las operaciones que pueden fallar
(`a[i]` fuera de rango, division entre cero entera o flotante) saltan a `__throw` con el mensaje
correspondiente. Si no hay manejador, `__throw` imprime `Excepcion no capturada: <mensaje>` y termina el
programa con codigo 1 (syscall 17). Una funcion con `try` guarda el contador de manejadores en su prologo y
lo restaura en el epilogo, de modo que un `return` dentro de un `try` no deja manejadores huerfanos.

## Rutinas de apoyo

`src/mips/runtime.py` contiene las rutinas en ensamblador. Solo se emiten las que el programa usa (con sus
dependencias). Reciben argumentos en `$a0`/`$a1`, devuelven en `$v0` y pueden destruir `$t0-$t9`, por eso el
generador vacia los registros antes de llamarlas.

## Tipos de los operandos

El TAC no escribe el tipo de cada operando, pero el backend lo necesita para elegir entre instrucciones
enteras y de punto flotante, comparar strings por contenido o convertir a texto. `src/mips/operandos.py`
lo recupera: las variables traen su tipo declarado (`FuncionTAC.tipos_vars`, `ProgramaTAC.tipos_globales`,
que anota el generador), las constantes lo dicen por su forma y los temporales heredan el tipo de la
instruccion que los define.

## Limitaciones y supuestos

* `float` es de precision simple. `print` y `+` muestran hasta 6 decimales sin ceros finales, asi que valores
  como `2.5` o `0.25` salen igual que en el interprete del TAC y valores como `0.1 + 0.2` pueden diferir
  en el ultimo digito. El convertidor a texto trabaja con la parte entera en 32 bits.
* Los enteros son de 32 bits con aritmetica circular; no se detecta el desbordamiento.
* No hay recoleccion de basura.
* `callind` supone que el destino se llama con el entorno del llamador: es lo correcto para las funciones
  de primer nivel y para funciones anidadas llamadas desde donde se declararon.
* Profundidad de manejadores de excepcion anidados: 40 (`exc_pila`).
* Desreferenciar `null` (`o.campo` con `o == null`) termina la simulacion con un error de MARS, no con
  una excepcion de Compiscript.

## Pruebas

```bash
python3 -m pytest tests -q                  # todo (fases 1, 2 y 3), ~25 s con MARS
python3 -m pytest tests/test_mips.py -q     # solo la fase 3
```

`tests/test_mips.py` tiene seis grupos:

1. **Diferencial**: los 15 programas de `tests/casos_tac/validos` y los 10 de `tests/casos_mips/validos` se
   compilan a MIPS, se simulan en MARS en los dos modos y su salida debe coincidir con el `.out`.
2. **Errores de ejecucion** (`tests/casos_mips/errores_ejecucion`): excepciones sin capturar, con el mensaje
   y el codigo de salida 1.
3. **Casos invalidos**: los de `tests/casos_tac/invalidos` no deben producir TAC ni MIPS.
4. **Forma del codigo**: prologo y epilogo simetricos, secuencia de llamada, enlace de acceso, uso de
   `$s`, vtables, solo las rutinas necesarias.
5. **getReg**: pruebas unitarias con un emisor falso (expulsion del uso mas lejano, guardado de sucios,
   vaciado de bloque).
6. **Comparacion de modos**: el modo registros hace menos `lw`/`sw` que el modo pila.

Los casos `M01`..`M10` cubren presion de registros, excepciones anidadas, cadenas, closures de varios niveles,
flotantes, recursion profunda, polimorfismo, control de flujo y paso de parametros.

## Mapa de archivos

```
src/mips/operandos.py   clasificacion de operandos y deduccion de tipos
src/mips/bloques.py     bloques basicos, vida de nombres, variables capturadas, eleccion de $s
src/mips/marco.py       distribucion del marco de pila
src/mips/registros.py   getReg: AsignadorRegistros y AsignadorPila
src/mips/emisor.py      traduccion instruccion por instruccion y estructura del .asm
src/mips/runtime.py     rutinas en ensamblador (itoa, ftoa, concat, strcmp, throw, ...)
src/mips/simulador.py   envoltorio de MARS
tests/test_mips.py      bateria de la fase 3
tools/Mars4_5.jar       simulador MARS 4.5 (Pete Sanderson y Kenneth Vollmar, licencia MIT)
```
