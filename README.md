# Compiscript

Proyecto 1 del curso de Construccion de Compiladores, Universidad del Valle de Guatemala, 2026.

Analizador sintactico y semantico para Compiscript, un subset de TypeScript. El proyecto genera el parser
con ANTLR a partir de `program/Compiscript.g4`, recorre el arbol con un visitor que aplica las reglas
semanticas del lenguaje, construye una tabla de simbolos con entornos anidados, y expone todo en un IDE
donde se puede escribir codigo, compilarlo y ver los errores, la tabla, el arbol sintactico, el codigo
intermedio (TAC) y los registros de activacion, y ejecutar el programa a traves del TAC.

## Como correr el proyecto

**1. Clonar el repositorio y entrar a la carpeta**

```bash
git clone https://github.com/GenserDev/Compiladores-P1.git && cd Compiladores-P1
```

**2. Crear un entorno virtual y activarlo**

```bash
python3 -m venv .venv && source .venv/bin/activate
```

**3. Instalar las dependencias**

```bash
pip install -r requirements.txt
```

**4. Compilar un archivo desde la linea de comandos**

```bash
python3 Driver.py program/ejemplo.cps --tabla
```

**5. Abrir el IDE**

```bash
python3 ide/app.py
```

El IDE abre con `program/ejemplo.cps` cargado. El boton Compilar llena las tres pestañas de abajo, la
lista de errores, la tabla de simbolos y el arbol sintactico. Al hacer clic en un error el editor salta a
esa linea.

## Codigo intermedio

```bash
python3 Driver.py program/ejemplo.cps --tac               # codigo de tres direcciones
python3 Driver.py program/ejemplo.cps --tac --lineas      # con la linea fuente de cada instruccion
python3 Driver.py program/ejemplo.cps --registros         # registros de activacion y disposicion de clases
python3 Driver.py program/ejemplo.cps --tabla             # tabla de simbolos con direcciones
```

El TAC solo se genera si el analisis semantico no encontro errores. La descripcion completa del lenguaje
intermedio esta en `docs/LENGUAJE_INTERMEDIO.md`.

## Otros comandos

Correr la bateria de pruebas completa.

```bash
python3 -m pytest tests -q
```

`tests/test_semantico.py` son los 76 casos de la fase 1, uno valido y uno fallido por cada regla semantica.
`tests/test_tac.py` es la bateria de la fase 2: compila cada programa de `tests/casos_tac/validos` a TAC,
revisa que este bien formado, lo ejecuta en el interprete y compara lo que imprime con el archivo `.out`;
los de `tests/casos_tac/invalidos` deben fallar sin generar TAC. Ademas prueba la forma exacta del TAC, el
reciclaje de temporales, los registros de activacion y la tabla de simbolos.

Exportar el arbol sintactico a Graphviz y convertirlo a imagen.

```bash
python3 Driver.py program/ejemplo.cps --dot arbol.dot && dot -Tpng arbol.dot -o arbol.png
```

Regenerar el parser despues de modificar la gramatica. Necesita Java 17.

```bash
./generar_parser.sh
```

Correr todo dentro de Docker sin instalar nada.

```bash
docker build --rm -t compiscript . && docker run --rm -ti compiscript
```

## Estructura

```
program/Compiscript.g4     gramatica ANTLR
program/generated/         lexer, parser y visitor generados
src/tipos.py               sistema de tipos y reglas de compatibilidad
src/simbolos.py            tabla de simbolos y entornos
src/analizador.py          visitor con las reglas semanticas, deja el arbol anotado
src/generador.py           visitor que genera el codigo intermedio (TAC)
src/tac.py                 instrucciones, funciones y programa TAC
src/temporales.py          asignacion y reciclaje de temporales
src/interprete_tac.py      interprete del TAC, para pruebas y para el IDE
src/arbol.py               arbol sintactico en texto y en DOT
src/compilador.py          fachada que junta parser y analizador
ide/app.py                 IDE
tests/casos/               casos de prueba de la fase 1
tests/casos_tac/           casos de prueba de la fase 2
docs/ARQUITECTURA.md       diseño de la implementacion
docs/LENGUAJE_INTERMEDIO.md  el lenguaje intermedio, esquemas de traduccion y supuestos
docs/REGLAS.md             catalogo de reglas y codigos de error
```
