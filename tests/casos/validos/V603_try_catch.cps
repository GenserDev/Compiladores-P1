let l: integer[] = [1, 2];
try {
  let x: integer = l[10];
  print(x);
} catch (err) {
  print("error: " + err);
}
