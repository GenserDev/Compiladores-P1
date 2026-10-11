let m: integer[][] = [[1,2,3],[4,5,6]];
m[1][2] = 60;
let suma: integer = 0;
foreach (fila in m) { foreach (x in fila) { suma = suma + x; } }
print(suma);
let nombres: string[] = ["a","b"];
nombres[0] = nombres[0] + "z";
print(nombres[0] + nombres[1]);
let vacio: integer[] = [];
print(m[0][0] + m[1][0]);
let f: float[] = [1, 2.5];
print(f[0] + f[1]);
