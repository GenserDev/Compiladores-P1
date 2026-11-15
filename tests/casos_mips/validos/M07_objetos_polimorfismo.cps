class Figura {
  let nombre: string;
  function constructor(n: string) { this.nombre = n; }
  function area(): integer { return 0; }
  function describir(): string { return nombre + " area=" + this.area(); }
}
class Rect : Figura {
  let w: integer; let h: integer;
  function constructor(w: integer, h: integer) { this.nombre = "rect"; this.w = w; this.h = h; }
  function area(): integer { return w * h; }
}
class Cuadrado : Rect {
  function constructor(l: integer) { this.nombre = "cuadrado"; this.w = l; this.h = l; }
  function describir(): string { return "[" + this.nombre + "] " + this.area(); }
}
let fs: Figura[] = [new Figura("generica"), new Rect(2, 3), new Cuadrado(4)];
foreach (f in fs) { print(f.describir()); }
let total: integer = 0;
for (let i: integer = 0; i < 3; i = i + 1) { total = total + fs[i].area(); }
print(total);
let c: Cuadrado = new Cuadrado(5);
c.w = 6;
print(c.area());
print(c);
class Contador {
  let n: integer = 0;
  function inc(): Contador { n = n + 1; return this; }
  function valor(): integer { return n; }
}
let k: Contador = new Contador();
print(k.inc().inc().inc().valor());
let otro: Contador = null;
print(otro == null);
