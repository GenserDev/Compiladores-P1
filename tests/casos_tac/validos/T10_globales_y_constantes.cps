let contador: integer = 0;
function inc(): integer { contador = contador + 1; return contador; }
inc(); inc();
print(contador);
const K: integer = 5;
function usaK(a: integer): integer { return a * K; }
print(usaK(4));
{ let local: integer = 9;
  function ve(): integer { return local + contador; }
  print(ve()); }
