try { print(1 / 0); } catch (e) { print("atrapada: " + e); print(2 / 0); }
print("nunca se imprime");
