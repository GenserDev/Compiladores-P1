# Arquitectura del compilador

El compilador tiene tres capas, la generada por ANTLR, el analisis semantico propio y las interfaces de
usuario. Cada una depende solo de la anterior.

```
program/Compiscript.g4
        |
        v  antlr -Dlanguage=Python3 -visitor
program/generated/  CompiscriptLexer, CompiscriptParser, CompiscriptVisitor
        |
        v
src/compilador.py  ->  src/analizador.py  ->  src/simbolos.py
                                           ->  src/tipos.py
                                           ->  src/errores.py
                       src/arbol.py
        |
        +--> Driver.py     (linea de comandos)
        +--> ide/app.py    (IDE)
        +--> tests/        (bateria de pruebas)
```

## Modulos

**`src/tipos.py`** define el sistema de tipos. Los primitivos son objetos unicos (`ENTERO`, `FLOTANTE`,
`CADENA`, `BOOLEANO`, `NULO`, `VACIO`) mas los constructores `TipoArreglo`, `TipoFuncion` y `TipoClase`.
Aqui viven las tres funciones que deciden todo el chequeo de tipos, `compatible` para asignaciones,
`unificar` para combinar dos tipos en operaciones y expresiones, y `comparables` para igualdades.
Existe un tipo especial `ERROR` que absorbe cualquier operacion, y por eso un error no genera una cascada
de errores derivados en el resto de la expresion.

**`src/simbolos.py`** define `Simbolo`, `Entorno`, `InfoClase` y `TablaSimbolos`. Un `Entorno` es un
diccionario de simbolos con un puntero a su padre, y la busqueda sube por esa cadena. La tabla guarda
todos los entornos creados, no solo los vivos, para poder mostrarla completa despues de compilar.
Cada simbolo lleva nombre, categoria, tipo, ambito, linea, si es constante, si esta inicializado, y su
`offset` y `tamano` dentro del entorno, que son los datos que van a hacer falta en la fase de generacion
de codigo.

**`src/errores.py`** define `ErrorSemantico` y el `ColectorErrores`. El analisis nunca se detiene en el
primer error, los acumula todos y los ordena por linea y columna al final.

**`src/analizador.py`** es el visitor que recorre el arbol y aplica las reglas. Es el modulo grande.

**`src/arbol.py`** produce la representacion visual del arbol sintactico, en texto indentado para el IDE
y en formato DOT de Graphviz para exportarlo como imagen.

**`src/compilador.py`** es la fachada. Recibe el texto fuente, arma lexer y parser con un listener propio
que captura los errores sintacticos, corre el analizador y devuelve un `Resultado` con errores, tabla,
arbol y parser. Todo lo demas del proyecto entra por aqui.

## Como recorre el arbol el analizador

El recorrido es un visitor, no un listener. La razon es que cada regla de expresion devuelve un tipo, y
con un listener habria que ir guardando esos tipos en una estructura aparte.

**Dos pasadas por cada ambito.** Antes de visitar los statements de un bloque, `declarar_firmas` registra
las clases y las firmas de las funciones que hay en ese bloque. Esto resuelve tres cosas de golpe, la
recursion, las llamadas a funciones declaradas mas abajo, y las clases que se referencian entre si.
Las clases se registran en dos vueltas, primero los nombres y luego los miembros, para que la herencia y
los atributos de tipo clase funcionen sin importar el orden.

**Estado del recorrido.** El analizador mantiene una pila de funciones activas (para validar `return` y
para registrar capturas), una pila de clases activas (para `this`), y dos contadores, `bucles` para
validar `continue` y `rompibles` para validar `break`, que tambien cuenta los `switch`.

**Expresiones.** Cada metodo de expresion devuelve un `Tipo`. Las reglas encadenadas de la gramatica
(`additiveExpr`, `multiplicativeExpr`, `logicalOrExpr`) se recorren de izquierda a derecha acumulando el
tipo del resultado, leyendo el operador con `ctx.getChild`.

**Accesos encadenados.** `leftHandSide` es `primaryAtom` seguido de cero o mas sufijos, y cada sufijo
puede ser una llamada, un indice o un acceso a propiedad. Se resuelve el atomo y luego se aplica cada
sufijo en orden sobre el tipo acumulado, asi que `objeto.metodo()[0].campo` se valida paso a paso.

## Tabla de simbolos

La tabla es un arbol de entornos, no una lista plana. El entorno raiz es `global` y de ahi cuelga uno por
cada funcion, clase, bloque, `for`, `foreach`, `catch` y rama de `switch`. El nombre completo de un ambito
es la ruta desde la raiz, por ejemplo `global.Animal.hablar`.

La resolucion de nombres sube por la cadena de padres. Como el entorno de una funcion anidada apunta al
entorno donde la funcion fue definida y no a donde se llama, los closures funcionan sin codigo extra, y
cuando un identificador se resuelve en un entorno mas externo que la funcion actual se anota en la lista
`capturadas` del simbolo de esa funcion.

Los offsets se asignan de forma incremental dentro de cada entorno segun el tamano del tipo, `integer` 4
bytes, `boolean` 1, y 8 para `float`, `string`, arreglos, objetos y funciones. Esos numeros no se usan
todavia, existen para la fase de generacion de codigo intermedio.

## Decisiones de diseno

**Los errores no detienen la compilacion.** El tipo `ERROR` se propaga silenciosamente, asi que un solo
error no produce diez mensajes derivados. Esto vuelve util la lista de errores del IDE.

**El `+` sobre strings es concatenacion.** El programa de ejemplo del curso hace `"texto: " + numero`, asi
que si cualquiera de los dos operandos es `string` el resultado es `string`.

**El `switch` no exige condicion booleana.** El razonamiento esta en `docs/REGLAS.md`.

**El parser generado esta versionado.** `program/generated` esta en el repositorio para que el proyecto
corra sin tener Java instalado. Para regenerarlo despues de tocar la gramatica esta `generar_parser.sh`.
