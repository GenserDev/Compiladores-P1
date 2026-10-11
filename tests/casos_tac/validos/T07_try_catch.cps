let a: integer[] = [1,2,3];
for (let i: integer = 0; i < 6; i = i + 1) {
  try {
    if (i == 1) { continue; }
    if (i == 4) { break; }
    print("v=" + a[i]);
  } catch (e) {
    print("err " + e);
  }
}
try { let q: integer = 1 / 0; } catch (e) { print("c: " + e); }
function f(): integer { try { return a[10]; } catch (e) { return -1; } }
print(f());
