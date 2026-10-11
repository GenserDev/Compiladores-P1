let i: integer = 0; let s: integer = 0;
while (i < 10) { i = i + 1; if (i % 2 == 0) { continue; } if (i > 7) { break; } s = s + i; }
print(s);
let j: integer = 0;
do { j = j + 3; } while (j < 10);
print(j);
for (;;) { j = j - 1; if (j < 5) { break; } }
print(j);
