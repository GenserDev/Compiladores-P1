function externa(): integer {
  function interna(): integer { return 1; }
  return interna() + 1;
}
print(externa());
