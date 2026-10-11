# Lenguaje intermedio de Compiscript (TAC)

El compilador traduce Compiscript a **codigo de tres direcciones en forma de cuadruplas**. Cada instruccion
es una cuadrupla `(op, arg1, arg2, res)` con a lo sumo tres operandos y una operacion. El texto que ve el
usuario (`python3 Driver.py programa.cps --tac`) es solo una forma legible de esas cuadruplas; el objeto
`Instruccion` de `src/tac.py` es la representacion real.

## Estructura de un programa TAC

Un programa es una lista de funciones. La primera es siempre `$main`, que contiene las sentencias del
nivel global. Despues van las funciones, los metodos (`Clase.metodo`) y los inicializadores de clase
(`Clase.$init`) en el orden en que aparecen en el fuente.

```
FUNC f(n)  (frame=40)
    if n > 1 goto L1
    return 1
L1:
    t1 = n - 1
    param t1
    t1 = call f, 1
    t1 = n * t1
    return t1
ENDFUNC f
```

El numero de `frame` es el tamano en bytes del registro de activacion (ver mas abajo). Si el programa
tiene metodos sobrescritos se agrega al final una seccion `VTABLE Clase { metodo -> etiqueta, ... }`.

## Operandos

| Forma | Significado |
|---|---|
| `t1`, `t2`, ... | temporal. Se numeran desde 1 en cada funcion y se reciclan |
| `x`, `x#2` | variable local o parametro. El sufijo `#n` aparece solo si otra variable de la misma funcion ya usa el nombre (bloques con sombra) |
| `$x` | variable global, vive en el area estatica (`gp`) |
| `x^1`, `x^2` | variable de una funcion externa, a 1 o 2 enlaces de acceso de distancia (closures) |
| `this`, `this^1` | receptor de un metodo (`this^k` si se usa desde una funcion anidada) |
| `12`, `3.5`, `"texto"`, `true`, `false`, `null` | constantes |
| `L1`, `Animal.speak` | etiquetas de salto y de funcion |

Los caracteres `$`, `#` y `^` no existen en los identificadores de Compiscript, asi que ningun nombre del
usuario puede chocar con ellos. Una variable del usuario llamada `t1` o `L2` se escribe `t1#`, `L2#`.

## Catalogo de instrucciones

| Texto | Cuadrupla | Descripcion |
|---|---|---|
| `x = y` | `copy y _ x` | copia |
| `x = y op z` | `op y z x` | `op` en `+ - * / % < <= > >= == !=`. El tipo (integer o float) lo fija el tipo del resultado y de los operandos; `/` entre enteros es division entera |
| `x = - y` / `x = ! y` | `neg y _ x` / `not y _ x` | unarios |
| `x = itof y` | `itof` | integer a float. Se inserta donde un entero se usa como float |
| `x = tostr y` | `tostr` | convierte cualquier valor a string |
| `x = concat y, z` | `concat y z x` | concatenacion de strings. `+` con un string se traduce siempre a `tostr` + `concat` |
| `L:` | `label _ _ L` | etiqueta |
| `goto L` | `goto _ _ L` | salto incondicional |
| `if x goto L` / `ifFalse x goto L` | `if` / `iffalse` | salto segun un booleano |
| `if x < y goto L` | `if< x y L` | salto con comparacion fusionada, para `< <= > >= == !=` |
| `param x` | `param x` | empuja un argumento. El receptor de un metodo va primero |
| `x = call f, n` / `call f, n` | `call f n x` | llamada directa con `n` parametros (incluye `this`). Sin `x` si la funcion es `void` |
| `x = callind t, n` | `callind t n x` | llamada a traves de un valor funcion (`t` viene de `addr`) |
| `x = callv Clase.m, n` | `callv` | llamada con despacho dinamico, ver abajo |
| `return` / `return x` | `return x` | retorno |
| `x = &f` | `addr f _ x` | direccion de una funcion, para usarla como valor |
| `x = newarray n, s` | `newarray n s x` | arreglo de `n` elementos de `s` bytes |
| `x = len a` | `len a _ x` | longitud |
| `x = a[i]` / `a[i] = v` | `aload a i x` / `astore a i v` | acceso a elementos. En `astore` el valor va en el campo `res` |
| `x = new C, s` | `new C s x` | objeto de `s` bytes de la clase `C` |
| `x = o.f` / `o.f = v` | `getf o f x` / `putf o f v` | acceso a atributos. En `putf` el valor va en el campo `res` |
| `print x` | `print x` | imprime |
| `pushtry L` / `poptry` | | abre o cierra un manejador de excepciones. Si se lanza una excepcion el control salta a `L` |
| `x = getexc` | `getexc _ _ x` | recupera el mensaje de la excepcion en curso |

## Esquemas de traduccion

**Expresiones aritmeticas.** Se recorren de izquierda a derecha. Cada operador evalua sus operandos, libera
los temporales que ya consumio y pide uno nuevo para el resultado, de modo que puede reutilizar el de un
operando:

```
let r: integer = (a + b) * (c + d) - a;
    t1 = $a + $b
    t2 = $c + $d
    t1 = t1 * t2
    $r = t1 - $a
```

La ultima instruccion escribe directo en `$r`: si el valor que se va a guardar es el temporal recien
producido, se redirige el resultado en lugar de emitir `$r = t1`.

**Condiciones.** Las condiciones de `if`, `while`, `do-while` y `for` no producen un booleano, producen saltos.
`&&`, `||` y `!` usan evaluacion en cortocircuito y las comparaciones se fusionan con el salto, negando el
operador cuando se salta al caso falso:

```
if (a < b && c < d) { print("ok"); } else { print("no"); }
    if $a >= $b goto L1
    if $c >= $d goto L1
    print "ok"
    goto L2
L1:
    print "no"
L2:
```

Cuando un `&&`, `||` o `!` se usa como valor (por ejemplo `let v = a && b;`) se materializa con saltos que
asignan `true` o `false` a un temporal.

**Bucles.** `while` pone la condicion arriba; `do-while` la pone abajo; `for` tiene tres etiquetas (condicion,
actualizacion, fin) y `continue` salta a la de actualizacion. `foreach` guarda el arreglo, su longitud y un
indice en temporales que permanecen reservados mientras dura el bucle. `break` y `continue` usan una pila de
bucles; si salen de un `try` emiten antes los `poptry` necesarios.

**`switch`.** Evalua la expresion una vez, compara con cada `case` (`if x == v goto Lcase`) y salta al
`default` o al final. Los cuerpos se emiten en orden, asi que sin `break` el control cae al siguiente caso,
igual que en el programa de ejemplo del curso.

**Llamadas.** Los argumentos se evaluan completos antes de emitir los `param`, para que una llamada anidada no
intercale `param` ajenos:

```
let r = f(g(1), g(2));
    param 1
    t1 = call g, 1
    param 2
    t2 = call g, 1
    param t1
    param t2
    $r = call f, 2
```

**Clases.** Un objeto mide 8 bytes de encabezado (id de clase) mas sus atributos; los de la clase padre van
primero, asi que un campo heredado tiene el mismo desplazamiento en toda la jerarquia. `new C(args)` emite
`new`, luego una llamada a `C.$init` si la clase (o un ancestro) tiene atributos con valor inicial, y luego
al constructor. `C.$init` ejecuta primero el de la clase padre. Un metodo recibe `this` como primer
parametro.

**Despacho dinamico.** Una llamada a metodo es directa (`call`) salvo que alguna subclase lo sobrescriba; en
ese caso se emite `callv` y el destino se busca en la `VTABLE` de la clase real del receptor:

```
let a: A = new B();  print(a.f());
    param $a
    t1 = callv A.f, 1
VTABLE A { f -> A.f }
VTABLE B { f -> B.f }
```

**Excepciones.** `try` emite `pushtry Lcatch`; al terminar normalmente `poptry` y salto al final; el bloque
`catch` empieza en `Lcatch` con `e = getexc`. Las operaciones que pueden fallar (`a[i]` fuera de rango,
division entre cero) lanzan la excepcion en tiempo de ejecucion, no se comprueban con instrucciones aparte.

**Conversiones.** El tipo de cada expresion lo dejo anotado el analizador semantico. Cuando un `integer` se
usa donde se espera un `float` (asignacion, argumento, retorno, operando mixto, ternario) se inserta
`itof`; un literal entero se convierte directamente (`3` pasa a `3.0`).

## Registros de activacion

Cada funcion, metodo e inicializador tiene un `RegistroActivacion` (`src/simbolos.py`). Los desplazamientos
son relativos a `fp` y crecen hacia arriba:

```
fp+0    enlace de control      fp del llamador
fp+8    enlace de acceso       fp de la funcion que contiene a esta (closures)
fp+16   direccion de retorno
fp+24   this (solo metodos), parametros, variables locales
...     temporales, 8 bytes cada uno, despues de las locales
```

Las variables se alinean a su tamano (`integer` 4, `boolean` 1, el resto 8). Las variables de un bloque
liberan su espacio al cerrarlo, de modo que bloques hermanos comparten desplazamientos. El `frame` es el
maximo de locales mas el maximo de temporales vivos a la vez.

**Closures.** Cada registro tiene un `nivel`: `$main` es 0 y una funcion dentro de otra tiene el nivel de la
externa mas uno. Una variable declarada en el nivel `v` y usada desde el nivel `c` se escribe `x^(c-v)`. Al
llamar a una funcion de nivel `k` desde el nivel `c`, su enlace de acceso es el marco que esta `c-(k-1)`
enlaces arriba del llamador. Las variables declaradas directamente en el nivel global no usan enlaces, viven
en el area estatica (`gp+offset`).

La tabla de simbolos (`--tabla`) muestra para cada simbolo su `almacen` (`global`, `local`, `parametro`,
`campo`, `funcion`) y su `direccion` (`gp+8`, `fp+24`, `obj+8` o la etiqueta). `--registros` imprime los
registros de activacion y la disposicion de cada clase.

## Asignacion y reciclaje de temporales

`src/temporales.py`. `PoolTemporales.nueva()` entrega el temporal libre de menor numero (o crea uno) y
`liberar()` lo devuelve cuando su valor ya fue consumido. Por eso el numero de temporales distintos de una
funcion es igual al maximo que estuvo vivo a la vez, no al numero de operaciones. Dos casos:

* `a + b + c + d + e` usa un solo temporal (`t1`) para todo el calculo.
* `(a+b)*(c+d) - (e+f)*(g-h)` usa tres, y pidio ocho en total.

Los temporales que cruzan un salto (el resultado de un ternario o de un `&&` usado como valor, el control de
un `switch`, el arreglo y el indice de un `foreach`) se reservan antes de evaluar las subexpresiones y se
liberan al final.

## Supuestos

1. Un temporal vive en el registro de activacion (8 bytes), no en un registro de maquina. La asignacion
   de registros es tarea de la fase de codigo objeto.
2. Una variable declarada sin inicializador no emite codigo; su valor es indefinido hasta la primera asignacion.
3. `/` entre enteros es division entera truncada hacia cero y `%` toma el signo del dividendo.
4. Un metodo usado como valor (`let f = obj.metodo;`) se traduce a `&etiqueta` y pierde el receptor.
5. Los errores de ejecucion (`indice fuera de rango`, `division entre cero`) son excepciones que atrapa `catch`.
6. Solo se genera codigo si el analisis semantico no encontro errores.
7. El tipo concreto de cada operando no aparece en el texto del TAC, pero la cuadrupla lo conserva en el
   campo `tipo` para que la fase siguiente escoja entre instrucciones enteras y de punto flotante.

## Ejecutar el TAC

`src/interprete_tac.py` ejecuta el codigo intermedio. No es parte del enunciado: sirve para comprobar que lo que
genera el compilador hace lo mismo que el programa original. Las pruebas de `tests/test_tac.py` lo usan, y el
IDE lo expone en el boton **Ejecutar**.
