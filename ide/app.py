import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from src.compilador import compilar

EJEMPLO = os.path.join(RAIZ, "program", "ejemplo.cps")


class IDE(tk.Tk):
    def __init__(self):
        tk.Tk.__init__(self)
        self.title("Compiscript IDE")
        self.geometry("1100x720")
        self.ruta = None
        self.construir_barra()
        self.construir_editor()
        self.construir_paneles()
        self.cargar_inicial()

    def construir_barra(self):
        barra = ttk.Frame(self, padding=6)
        barra.pack(fill="x")
        ttk.Button(barra, text="Abrir", command=self.abrir).pack(side="left", padx=2)
        ttk.Button(barra, text="Guardar", command=self.guardar).pack(side="left", padx=2)
        ttk.Button(barra, text="Compilar", command=self.compilar).pack(side="left", padx=2)
        ttk.Button(barra, text="Exportar arbol", command=self.exportar_dot).pack(side="left", padx=2)
        self.estado = ttk.Label(barra, text="listo")
        self.estado.pack(side="right")

    def construir_editor(self):
        marco = ttk.Frame(self)
        marco.pack(fill="both", expand=True, padx=6)
        self.numeros = tk.Text(marco, width=5, padx=4, takefocus=0, border=0,
                               background="#eeeeee", state="disabled", font=("Menlo", 12))
        self.numeros.pack(side="left", fill="y")
        self.editor = tk.Text(marco, wrap="none", undo=True, font=("Menlo", 12))
        self.editor.pack(side="left", fill="both", expand=True)
        barra_v = ttk.Scrollbar(marco, command=self.desplazar)
        barra_v.pack(side="right", fill="y")
        self.editor.configure(yscrollcommand=self.sincronizar)
        self.barra_v = barra_v
        self.editor.tag_configure("error", background="#ffd6d6")
        self.editor.bind("<KeyRelease>", lambda e: self.numerar())

    def desplazar(self, *args):
        self.editor.yview(*args)
        self.numeros.yview(*args)

    def sincronizar(self, inicio, fin):
        self.barra_v.set(inicio, fin)
        self.numeros.yview_moveto(inicio)

    def numerar(self):
        total = int(self.editor.index("end-1c").split(".")[0])
        self.numeros.configure(state="normal")
        self.numeros.delete("1.0", "end")
        self.numeros.insert("1.0", "\n".join(str(i) for i in range(1, total + 1)))
        self.numeros.configure(state="disabled")

    def construir_paneles(self):
        panel = ttk.Notebook(self)
        panel.pack(fill="both", expand=True, padx=6, pady=6)

        marco_errores = ttk.Frame(panel)
        self.lista_errores = ttk.Treeview(marco_errores, columns=("codigo", "linea", "mensaje"),
                                          show="headings", height=8)
        for columna, ancho in (("codigo", 80), ("linea", 80), ("mensaje", 900)):
            self.lista_errores.heading(columna, text=columna)
            self.lista_errores.column(columna, width=ancho, anchor="w")
        self.lista_errores.pack(fill="both", expand=True)
        self.lista_errores.bind("<<TreeviewSelect>>", self.ir_al_error)
        panel.add(marco_errores, text="Errores")

        marco_tabla = ttk.Frame(panel)
        columnas = ("nombre", "categoria", "tipo", "ambito", "nivel", "const", "init", "offset", "tamano", "linea")
        self.tabla_simbolos = ttk.Treeview(marco_tabla, columns=columnas, show="headings", height=8)
        for columna in columnas:
            self.tabla_simbolos.heading(columna, text=columna)
            self.tabla_simbolos.column(columna, width=110, anchor="w")
        self.tabla_simbolos.pack(fill="both", expand=True)
        panel.add(marco_tabla, text="Tabla de simbolos")

        marco_arbol = ttk.Frame(panel)
        self.vista_arbol = tk.Text(marco_arbol, wrap="none", font=("Menlo", 11))
        self.vista_arbol.pack(fill="both", expand=True)
        panel.add(marco_arbol, text="Arbol sintactico")

    def cargar_inicial(self):
        if os.path.exists(EJEMPLO):
            self.editor.insert("1.0", open(EJEMPLO).read())
            self.ruta = EJEMPLO
        self.numerar()

    def abrir(self):
        ruta = filedialog.askopenfilename(filetypes=[("Compiscript", "*.cps"), ("Todos", "*.*")])
        if not ruta:
            return
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", open(ruta).read())
        self.ruta = ruta
        self.numerar()
        self.estado.configure(text=os.path.basename(ruta))

    def guardar(self):
        ruta = self.ruta or filedialog.asksaveasfilename(defaultextension=".cps")
        if not ruta:
            return
        open(ruta, "w").write(self.editor.get("1.0", "end-1c"))
        self.ruta = ruta
        self.estado.configure(text="guardado en {}".format(os.path.basename(ruta)))

    def compilar(self):
        fuente = self.editor.get("1.0", "end-1c")
        resultado = compilar(fuente)
        self.editor.tag_remove("error", "1.0", "end")
        self.lista_errores.delete(*self.lista_errores.get_children())
        self.tabla_simbolos.delete(*self.tabla_simbolos.get_children())
        for error in resultado.errores:
            self.lista_errores.insert("", "end", values=(error.codigo, error.linea, error.mensaje))
            self.editor.tag_add("error", "{}.0".format(error.linea), "{}.end".format(error.linea))
        if resultado.tabla is not None:
            for fila in resultado.tabla.filas():
                self.tabla_simbolos.insert("", "end", values=tuple(fila.values()))
        self.vista_arbol.delete("1.0", "end")
        self.vista_arbol.insert("1.0", resultado.arbol_texto())
        self.resultado = resultado
        if resultado.exitoso():
            self.estado.configure(text="compilacion exitosa")
        else:
            self.estado.configure(text="{} error(es)".format(len(resultado.errores)))

    def ir_al_error(self, evento):
        seleccion = self.lista_errores.selection()
        if not seleccion:
            return
        linea = self.lista_errores.item(seleccion[0])["values"][1]
        self.editor.see("{}.0".format(linea))
        self.editor.mark_set("insert", "{}.0".format(linea))
        self.editor.focus_set()

    def exportar_dot(self):
        if not hasattr(self, "resultado"):
            messagebox.showinfo("Compiscript", "Compila primero para generar el arbol")
            return
        ruta = filedialog.asksaveasfilename(defaultextension=".dot")
        if not ruta:
            return
        open(ruta, "w").write(self.resultado.arbol_dot())
        self.estado.configure(text="arbol exportado a {}".format(os.path.basename(ruta)))


if __name__ == "__main__":
    IDE().mainloop()
