function fib(n: integer): integer { if (n < 2) { return n; } return fib(n - 1) + fib(n - 2); }
print(fib(20));
function suma(n: integer): integer { if (n == 0) { return 0; } return n + suma(n - 1); }
print(suma(200));
function par(n: integer): boolean { if (n == 0) { return true; } return impar(n - 1); }
function impar(n: integer): boolean { if (n == 0) { return false; } return par(n - 1); }
print(par(10)); print(impar(7)); print(par(7));
function ack(m: integer, n: integer): integer {
  if (m == 0) { return n + 1; }
  if (n == 0) { return ack(m - 1, 1); }
  return ack(m - 1, ack(m, n - 1));
}
print(ack(2, 3));
function mcd(a: integer, b: integer): integer { if (b == 0) { return a; } return mcd(b, a % b); }
print(mcd(1071, 462));
