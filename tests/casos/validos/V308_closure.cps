function contador(): integer {
  let base: integer = 10;
  function siguiente(): integer { return base + 1; }
  return siguiente();
}
print(contador());
