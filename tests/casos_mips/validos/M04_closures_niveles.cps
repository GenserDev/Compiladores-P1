function crear(inicio: integer): integer {
  let c: integer = inicio;
  function inc(): integer { c = c + 1; return c; }
  function dos(): integer { inc(); return inc(); }
  let g = inc;
  g();
  return dos() + inc();
}
print(crear(10));
function a(x: integer): integer {
  function b(y: integer): integer {
    function c(z: integer): integer { x = x + 1; return x + y + z; }
    let h = c;
    return h(100) + c(1000);
  }
  return b(10) + x;
}
print(a(1));
function suma3(p: integer, q: integer, r: integer): integer { return p * 100 + q * 10 + r; }
let s = suma3;
print(s(1, 2, 3));
