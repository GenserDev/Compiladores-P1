for (let i: integer = 0; i < 4; i = i + 1) {
  for (let j: integer = 0; j < 4; j = j + 1) {
    if (j == 2) { continue; }
    if (i == 3) { break; }
    print(i * 10 + j);
  }
}
let n: integer = 0;
do { n = n + 1; if (n == 2) { continue; } print("n=" + n); } while (n < 4);
function clasificar(x: integer): string {
  switch (x) {
    case 1: return "uno";
    case 2: print("paso por 2");
    case 3: return "dos o tres";
    default: return "otro";
  }
  return "nunca";
}
print(clasificar(1)); print(clasificar(2)); print(clasificar(3)); print(clasificar(8));
function efecto(x: integer): boolean { print("efecto " + x); return x > 1; }
if (efecto(1) && efecto(2)) { print("ambos"); }
if (efecto(3) || efecto(4)) { print("alguno"); }
let r = 5 > 3 ? (2 > 1 ? "a" : "b") : "c";
print(r);
let arr: integer[] = [3, 1, 2];
let cambios: integer = 0;
for (let i: integer = 0; i < 3; i = i + 1) {
  for (let j: integer = 0; j < 2 - i; j = j + 1) {
    if (arr[j] > arr[j + 1]) { let t: integer = arr[j]; arr[j] = arr[j + 1]; arr[j + 1] = t; cambios = cambios + 1; }
  }
}
print(arr); print(cambios);
