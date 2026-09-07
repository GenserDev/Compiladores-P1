from antlr4 import TerminalNode


def etiqueta(nodo, reglas):
    if isinstance(nodo, TerminalNode):
        return repr(nodo.getText())
    return reglas[nodo.getRuleIndex()]


def a_texto(nodo, reglas, nivel=0):
    lineas = ["{}{}".format("  " * nivel, etiqueta(nodo, reglas))]
    for i in range(nodo.getChildCount()):
        lineas.extend(a_texto(nodo.getChild(i), reglas, nivel + 1))
    return lineas


def texto(arbol, parser):
    return "\n".join(a_texto(arbol, parser.ruleNames))


def a_dot(nodo, reglas, contador, lineas, padre=None):
    identificador = "n{}".format(contador[0])
    contador[0] += 1
    forma = "box" if isinstance(nodo, TerminalNode) else "ellipse"
    nombre = etiqueta(nodo, reglas).replace('"', '\\"')
    lineas.append('  {} [label="{}", shape={}];'.format(identificador, nombre, forma))
    if padre is not None:
        lineas.append("  {} -> {};".format(padre, identificador))
    for i in range(nodo.getChildCount()):
        a_dot(nodo.getChild(i), reglas, contador, lineas, identificador)
    return identificador


def dot(arbol, parser):
    lineas = ["digraph arbol {", "  node [fontname=\"Helvetica\"];"]
    a_dot(arbol, parser.ruleNames, [0], lineas)
    lineas.append("}")
    return "\n".join(lineas)
