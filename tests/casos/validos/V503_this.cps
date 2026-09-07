class Contador {
  let n: integer;
  function constructor() { this.n = 0; }
  function subir(): integer { this.n = this.n + 1; return this.n; }
}
let c: Contador = new Contador();
print(c.subir());
