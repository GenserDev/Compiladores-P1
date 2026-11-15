// 5000 llamadas anidadas: el marco de pila crece y se desarma correctamente (el interprete de Python no llega a tanta profundidad).
function suma(n: integer): integer { if (n == 0) { return 0; } return n + suma(n - 1); }
print(suma(5000));
function cuenta(n: integer, acc: integer): integer { if (n == 0) { return acc; } return cuenta(n - 1, acc + 2); }
print(cuenta(4000, 0));
