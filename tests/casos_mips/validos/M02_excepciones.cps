function dividir(a: integer, b: integer): integer { return a / b; }
function seguro(a: integer, b: integer): integer {
  try { return dividir(a, b); } catch (e) { print("capturado: " + e); return -1; }
}
print(seguro(10, 2)); print(seguro(1, 0));
let arr: integer[] = [10, 20, 30];
let total: integer = 0;
for (let i: integer = 0; i < 5; i = i + 1) {
  try { total = total + arr[i]; } catch (e) { print("fuera " + i + ": " + e); }
}
print(total);
function anidado(n: integer): integer {
  try {
    try { return dividir(n, n - 1); } catch (e1) { print("interno " + e1); return dividir(n, 0); }
  } catch (e2) { print("externo " + e2); return 99; }
}
print(anidado(5)); print(anidado(1));
function profundo(n: integer): integer {
  if (n == 0) { return dividir(1, 0); }
  return profundo(n - 1) + 1;
}
try { print(profundo(20)); } catch (e) { print("desde lo profundo: " + e); }
let k: integer = 0;
while (k < 3) { try { k = k + 1; if (k == 2) { continue; } print(arr[k]); } catch (e) { print("k=" + k); } }
