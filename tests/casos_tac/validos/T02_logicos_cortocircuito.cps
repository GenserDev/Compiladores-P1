function t(x: boolean): boolean { print("t"); return x; }
let a = true && t(false) || t(true);
print(a);
let b = !(1 < 2) || 3 == 3;
print(b);
let c = false && t(true);
print(c);
if (1 < 2 && 2 < 3 || false) { print("ok"); }
let v = 3 > 2 ? "si" : "no"; print(v);
let w = (1 > 2) ? 10 : 20; print(w);
let z = true ? 1 : 2.5; print(z);
