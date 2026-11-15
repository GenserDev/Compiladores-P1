let contador: integer = 0;
const LIMITE: integer = 5;
function tocar(): integer { contador = contador + 1; return contador; }
tocar(); tocar();
print(contador);
function seis(a: integer, b: integer, c: integer, d: integer, e: integer, f: integer): integer {
  return a - b + c * d - e + f;
}
print(seis(1, 2, 3, 4, 5, 6));
function mezcla(a: integer, x: float, s: string, b: boolean): string { return s + a + "," + x + "," + b; }
print(mezcla(7, 2.5, "p", true));
function intercambio(v: integer[], i: integer, j: integer): integer { let t: integer = v[i]; v[i] = v[j]; v[j] = t; return v[i]; }
let datos: integer[] = [9, 8, 7];
print(intercambio(datos, 0, 2)); print(datos);
let i: integer = 0;
while (i < LIMITE) { i = i + 1; if (i % 2 == 1) { contador = contador + i; } }
print(contador);
let m: integer[][] = [[1, 2], [3, 4]];
m[0][1] = m[1][0] * 10;
print(m);
