let x: float = 1.5; let y: float = 0.25;
print(x + y); print(x - y); print(x * y); print(x / y);
print(x > y); print(x <= y); print(x == 1.5); print(x != y);
print(-x);
let acc: float = 0.0;
for (let i: integer = 0; i < 8; i = i + 1) { acc = acc + 0.5; }
print(acc);
function media(a: float, b: float): float { return (a + b) / 2; }
print(media(3.0, 4.5));
print(media(1, 2));
let v: float[] = [1.5, 2.5, 4.0];
let s: float = 0.0;
foreach (e in v) { s = s + e; }
print(s);
if (s > 7.5) { print("mayor"); } else { print("menor o igual"); }
let n: integer = 3;
print(n * 1.5);
print("valor: " + (n / 2.0));
print(10.0 / 4);
let q: float = 1.0 / 3.0;
if (q > 0.33 && q < 0.34) { print("un tercio"); }
