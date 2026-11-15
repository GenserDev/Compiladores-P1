// Muchos valores vivos a la vez: obliga a getReg a expulsar registros y a usar $s0..$s7.
function f(): integer {
  let a: integer = 1; let b: integer = 2; let c: integer = 3; let d: integer = 4;
  let e: integer = 5; let g: integer = 6; let h: integer = 7; let k: integer = 8;
  let r: integer = (a*b) + ((c*d) + ((e*g) + ((h*k) + ((a*c) + ((b*d) + ((e*h) + ((g*k) + ((a*d) + ((b*c) + (e*k))))))))));
  let s: integer = 0;
  for (let i: integer = 0; i < 4; i = i + 1) { s = s + a*i + b*i*i - c; }
  return r * 1000 + s;
}
print(f());
function g(x: integer): integer { return x + 1; }
print(g(1) + (g(2) + (g(3) + (g(4) + (g(5) + (g(6) + (g(7) + (g(8) + (g(9) + g(10))))))))));
let t: integer = (1+2)*(3+4)*(5+6)*(7+8) + (9*10 + 11*12) * (13 - 14 + 15*16);
print(t);
