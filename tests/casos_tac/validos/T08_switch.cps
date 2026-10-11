function nombre(n: integer): string {
  let r: string = "otro";
  switch (n) {
    case 1: r = "uno"; break;
    case 2: r = "dos";
    case 3: r = r + "tres"; break;
    default: r = "def";
  }
  return r;
}
print(nombre(1)); print(nombre(2)); print(nombre(3)); print(nombre(9));
let s: string = "x";
switch (s) { case "x": print("es x"); break; case "y": print("es y"); }
