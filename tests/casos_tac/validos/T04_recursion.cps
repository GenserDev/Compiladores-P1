function fact(n: integer): integer { if (n <= 1) { return 1; } return n * fact(n - 1); }
function fib(n: integer): integer { if (n < 2) { return n; } return fib(n-1) + fib(n-2); }
print(fact(10)); print(fib(15));
