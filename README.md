# Compiscript

Proyecto 1 del curso de Construccion de Compiladores, Universidad del Valle de Guatemala, 2026.

Analizador sintactico y semantico para Compiscript, un subset de TypeScript. El proyecto genera el parser
con ANTLR a partir de `program/Compiscript.g4`, recorre el arbol con un visitor que aplica las reglas
semanticas del lenguaje, construye una tabla de simbolos con entornos anidados, y expone todo en un IDE
donde se puede escribir codigo, compilarlo y ver los errores, la tabla y el arbol sintactico.

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

El IDE abre con `program/ejemplo.cps` cargado. El boton Compilar llena las tres pestanas de abajo, la
lista de errores, la tabla de simbolos y el arbol sintactico. Al hacer clic en un error el editor salta a
esa linea.

## Otros comandos

Correr la bateria de pruebas, son 76 casos, uno valido y uno fallido por cada regla semantica.

```bash
python3 -m pytest tests -q
```

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
src/analizador.py          visitor con las reglas semanticas
src/arbol.py               arbol sintactico en texto y en DOT
src/compilador.py          fachada que junta parser y analizador
ide/app.py                 IDE
tests/casos/               casos de prueba en Compiscript
docs/ARQUITECTURA.md       diseno de la implementacion
docs/REGLAS.md             catalogo de reglas y codigos de error
```

## Notas

El parser generado esta versionado en `program/generated`, asi que no hace falta tener Java para correr el
compilador. Java solo se necesita si se modifica la gramatica.

La gramatica tiene un solo cambio respecto a la del curso, se agrego el tipo `float` y su literal, porque
el enunciado los pide en las reglas de operaciones aritmeticas y la gramatica original no los incluye.

El IDE usa Tkinter, que viene con Python. En Linux puede hacer falta instalar `python3-tk`.
