class Animal {
  let nombre: string;
  let patas: integer = 4;
  function constructor(nombre: string) { this.nombre = nombre; }
  function hablar(): string { return nombre + " hace ruido " + patas; }
  function quien(): string { return this.hablar(); }
}
class Perro : Animal {
  let truco: string = "sentado";
  function hablar(): string { return this.nombre + " ladra y hace " + this.truco; }
}
let p: Perro = new Perro("Toby");
print(p.hablar()); print(p.quien()); print(p.patas);
p.patas = 3; p.nombre = "Rex";
print(p.patas + 1); print(p.nombre);
let a: Animal = new Animal("Gato");
print(a.hablar());
let b: Animal = new Perro("Fido");
print(b.hablar());
