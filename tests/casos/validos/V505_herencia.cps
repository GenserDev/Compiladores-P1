class Animal {
  let nombre: string;
  function constructor(nombre: string) { this.nombre = nombre; }
  function hablar(): string { return this.nombre + " hace ruido."; }
}
class Perro : Animal {
  function hablar(): string { return this.nombre + " ladra."; }
}
let p: Perro = new Perro("Toby");
print(p.hablar());
