class Nodo { let valor: integer; let sig: Nodo;
  function constructor(v: integer) { this.valor = v; this.sig = null; }
  function suma(): integer { if (this.sig == null) { return this.valor; } return this.valor + this.sig.suma(); }
}
class Lista { let cabeza: Nodo; let n: integer = 0;
  function constructor() { this.cabeza = null; }
  function agregar(v: integer): integer { let nuevo: Nodo = new Nodo(v); nuevo.sig = this.cabeza; this.cabeza = nuevo; n = n + 1; return n; }
  function total(): integer { return this.cabeza.suma(); }
}
let l: Lista = new Lista();
l.agregar(1); l.agregar(2); l.agregar(3);
print(l.total()); print(l.n);
let arr: Nodo[] = [new Nodo(5), new Nodo(6)];
print(arr[1].valor + arr[0].suma());
