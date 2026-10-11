function crearContador(): integer {
  let cuenta: integer = 10;
  function siguiente(): integer {
    cuenta = cuenta + 1;
    return cuenta;
  }
  siguiente();
  siguiente();
  return siguiente();
}
print(crearContador());
function externa(x: integer): integer {
  function media(y: integer): integer {
    function interna(z: integer): integer { return x + y + z; }
    return interna(3);
  }
  return media(2);
}
print(externa(1));
