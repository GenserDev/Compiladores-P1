class Animal {
  let nombre: string;
  function constructor(nombre: string) { this.nombre = nombre; }
  function hablar(): string { return this.nombre + " hace ruido."; }
}
let a: Animal = new Animal("Rex");
print(a.hablar());
