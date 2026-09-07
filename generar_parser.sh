#!/bin/bash
set -e
cd "$(dirname "$0")/program"
java -jar ../tools/antlr-4.13.1-complete.jar -Dlanguage=Python3 -visitor -no-listener -o generated Compiscript.g4
echo "parser generado en program/generated"
