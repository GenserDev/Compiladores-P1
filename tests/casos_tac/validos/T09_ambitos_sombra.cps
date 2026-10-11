let x: integer = 1;
{ let x: integer = 2; print(x); { let x: integer = 3; print(x); } print(x); }
print(x);
function g(): integer { let x: integer = 100; { let x: integer = 5; x = x + 1; } return x; }
print(g());
let t1: integer = 7; print(t1 + 1);
