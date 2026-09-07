# Catalogo de reglas semanticas

Cada regla del enunciado tiene un codigo de error, un caso valido y un caso fallido en `tests/casos`.
Los archivos de prueba se llaman igual que el codigo, asi que `tests/casos/invalidos/E100_aritmetica_no_numerica.cps`
es el caso fallido de `E100` y `tests/casos/validos/V100_aritmetica.cps` es el exitoso.

## Sistema de tipos

**E100** Los operadores `+`, `-`, `*` y `/` requieren operandos `integer` o `float`. El `+` con al menos
un `string` se trata como concatenacion y produce `string`.

**E101** Los operadores `&&`, `||` y `!` requieren operandos `boolean`.

**E102** Las comparaciones `==`, `!=`, `<`, `<=`, `>` y `>=` requieren tipos comparables. Los ordenamientos
solo aceptan numerico contra numerico o `string` contra `string`.

**E103** El valor asignado debe ser compatible con el tipo declarado de la variable.

**E104** El inicializador de una declaracion debe ser compatible con el tipo anotado.

**E105** Todos los elementos de un arreglo literal deben unificar en un mismo tipo.

**E106** El indice de un arreglo debe ser `integer`.

**E107** Solo se puede indexar un arreglo. Tambien cubre el iterable de `foreach`.

**E108** El operador unario `-` requiere un operando numerico.

**E109** El operador `%` requiere ambos operandos `integer`.

## Manejo de ambito

**E200** No se puede usar un identificador que no fue declarado en el ambito actual ni en uno superior.

**E201** No se puede declarar dos veces el mismo identificador en el mismo ambito.

**E202** No se puede reasignar una constante. La gramatica ya obliga a inicializar toda `const`, asi que
una constante sin inicializador es un error sintactico `E000`.

Se abre un entorno nuevo para cada funcion, clase, bloque, `for`, `foreach`, `catch` y rama de `switch`.

## Funciones y procedimientos

**E300** El numero de argumentos debe coincidir con el numero de parametros.

**E301** Cada argumento debe ser compatible con el tipo del parametro en la misma posicion.

**E302** El valor de un `return` debe ser compatible con el tipo de retorno declarado.

**E303** No se puede declarar dos funciones, dos metodos ni dos clases con el mismo nombre. El lenguaje
no soporta sobrecarga.

**E304** Solo se puede llamar a un valor de tipo funcion.

**E305** Una funcion con tipo de retorno declarado debe tener al menos un `return` con valor.

**E602** Una funcion no puede repetir el nombre de un parametro.

La recursion funciona porque las firmas de todas las funciones de un bloque se declaran antes de recorrer
los cuerpos. Los closures funcionan porque el entorno de una funcion anidada apunta al entorno donde fue
definida, y cada variable resuelta fuera de ese entorno queda registrada en `capturadas`.

## Control de flujo

**E400** Las condiciones de `if`, `while`, `do-while`, `for` y del operador ternario deben ser `boolean`.

**E401** `break` solo puede aparecer dentro de un bucle o de un `switch`.

**E402** `continue` solo puede aparecer dentro de un bucle.

**E403** `return` solo puede aparecer dentro de una funcion.

**E404** La etiqueta de cada `case` debe ser comparable con la expresion del `switch`.

Sobre el `switch`, el enunciado pide que su condicion sea `boolean`, pero el programa de ejemplo del curso
hace `switch (addFive)` sobre un `integer` y el propio lenguaje no tendria sentido con un `switch` booleano.
La decision fue permitir cualquier tipo en el `switch` y validar en su lugar que cada `case` sea comparable
con el, que es la version util de la misma regla.

## Clases y objetos

**E500** El tipo o la clase usada debe estar declarada.

**E501** El atributo o metodo accedido con `.` debe existir en la clase o en alguna de sus ancestras.

**E502** La llamada al constructor debe coincidir en numero y tipo de argumentos. Una clase sin constructor
propio hereda el de su padre.

**E503** `this` solo puede usarse dentro del cuerpo de una clase.

**E504** No se puede acceder a una propiedad sobre un valor que no es un objeto.

**E505** La clase padre debe existir y no puede ser la clase misma.

## Generales

**E600** No puede haber instrucciones despues de un `return`, `break` o `continue` en el mismo bloque.

**E601** Una funcion no puede aparecer como operando de una operacion aritmetica.

**E000** Errores sintacticos reportados por ANTLR.

## Extension a la gramatica

La gramatica original no tiene `float`, pero el enunciado lo exige en las reglas aritmeticas. Se agregaron
dos lineas a `program/Compiscript.g4`, el token `FloatLiteral` y el tipo base `float`. Es el unico cambio
respecto a la gramatica del curso.
