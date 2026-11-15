let a: string = "ho" + "la";
let b: string = "hola";
print(a == b); print(a != b); print(a == "adios");
let n: integer = 42; let f: float = 2.5; let t: boolean = true;
print("n=" + n + " f=" + f + " t=" + t + " " + false);
print(t && !t); print(n > 40 && f < 3.0);
let nada: string = null;
print(nada == null);
if (a == b) { print("iguales"); } else { print("distintos"); }
let xs: integer[] = [1, 2, 3]; let ss: string[] = ["x", "y"]; let fs: float[] = [1.5, 0.25];
print(xs); print(ss); print(fs);
print(-17 % 5); print(-17 / 5); print(17 / -5);
print("" + (0 - 5));
print(-2147483647 - 1);
print(2147483647);
let largo: string = "";
for (let i: integer = 0; i < 5; i = i + 1) { largo = largo + i + ","; }
print(largo);
