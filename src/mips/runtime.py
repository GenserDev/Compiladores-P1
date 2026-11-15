"""Rutinas de apoyo escritas en ensamblador MIPS. Solo se emiten las que el programa usa.

Convencion: argumentos en $a0/$a1, resultado en $v0. Pueden destruir $t0-$t9, $a0-$a3 y $f0-$f20;
nunca tocan $s, $fp ni $sp (salvo para usar la pila y dejarla igual). El generador vacia los registros
antes de llamarlas.
"""

DATOS = """\
rt_true:    .asciiz "true"
rt_false:   .asciiz "false"
rt_null:    .asciiz "null"
rt_lt:      .asciiz "<"
rt_gt:      .asciiz ">"
rt_lb:      .asciiz "["
rt_rb:      .asciiz "]"
rt_sep:     .asciiz ", "
rt_array:   .asciiz "<array>"
rt_fun:     .asciiz "<funcion>"
rt_uncaught: .asciiz "Excepcion no capturada: "
msg_indice: .asciiz "indice fuera de rango"
msg_div:    .asciiz "division entre cero"
exc_n:      .word 0
exc_msg:    .word 0
exc_pila:   .space 480
"""

RUTINAS = {}


def rutina(nombre, codigo, deps=()):
    RUTINAS[nombre] = (codigo, tuple(deps))


rutina("__itoa", """\
# $a0 = entero -> $v0 = cadena decimal (memoria dinamica)
__itoa:
    move $t0, $a0
    li   $v0, 9
    li   $a0, 12
    syscall
    move $t1, $v0
    addiu $t2, $t1, 11
    sb   $zero, 0($t2)
    bnez $t0, __itoa_nz
    addiu $t2, $t2, -1
    li   $t3, 48
    sb   $t3, 0($t2)
    j    __itoa_fin
__itoa_nz:
    move $t4, $t0
    bgez $t0, __itoa_lazo
    subu $t4, $zero, $t0
__itoa_lazo:
    beqz $t4, __itoa_signo
    li   $t5, 10
    divu $t4, $t5
    mfhi $t6
    mflo $t4
    addiu $t6, $t6, 48
    addiu $t2, $t2, -1
    sb   $t6, 0($t2)
    j    __itoa_lazo
__itoa_signo:
    bgez $t0, __itoa_fin
    addiu $t2, $t2, -1
    li   $t3, 45
    sb   $t3, 0($t2)
__itoa_fin:
    move $v0, $t2
    jr   $ra
""")

rutina("__concat", """\
# $a0 + $a1 (cadenas) -> $v0 (cadena nueva). Una cadena null se trata como "null"
__concat:
    move $t0, $a0
    move $t1, $a1
    bnez $t0, __cc_a
    la   $t0, rt_null
__cc_a:
    bnez $t1, __cc_b
    la   $t1, rt_null
__cc_b:
    move $t2, $zero
__cc_l1:
    addu $t3, $t0, $t2
    lb   $t4, 0($t3)
    beqz $t4, __cc_e1
    addiu $t2, $t2, 1
    j    __cc_l1
__cc_e1:
    move $t5, $zero
__cc_l2:
    addu $t3, $t1, $t5
    lb   $t4, 0($t3)
    beqz $t4, __cc_e2
    addiu $t5, $t5, 1
    j    __cc_l2
__cc_e2:
    addu $t6, $t2, $t5
    addiu $a0, $t6, 1
    li   $v0, 9
    syscall
    move $t7, $v0
__cc_c1:
    lb   $t4, 0($t0)
    beqz $t4, __cc_c2
    sb   $t4, 0($t7)
    addiu $t0, $t0, 1
    addiu $t7, $t7, 1
    j    __cc_c1
__cc_c2:
    lb   $t4, 0($t1)
    sb   $t4, 0($t7)
    beqz $t4, __cc_fin
    addiu $t1, $t1, 1
    addiu $t7, $t7, 1
    j    __cc_c2
__cc_fin:
    jr   $ra
""")

rutina("__strcmp", """\
# $a0 == $a1 (contenido de cadenas) -> $v0 = 1 si son iguales, 0 si no
__strcmp:
    beq  $a0, $a1, __sc_eq
    beqz $a0, __sc_ne
    beqz $a1, __sc_ne
__sc_l:
    lb   $t0, 0($a0)
    lb   $t1, 0($a1)
    bne  $t0, $t1, __sc_ne
    beqz $t0, __sc_eq
    addiu $a0, $a0, 1
    addiu $a1, $a1, 1
    j    __sc_l
__sc_eq:
    li   $v0, 1
    jr   $ra
__sc_ne:
    li   $v0, 0
    jr   $ra
""")

rutina("__ftoa", """\
# $a0 = bits de un float -> $v0 = cadena ("3.5", "2.0", "-0.25"); hasta 6 decimales, sin ceros finales
__ftoa:
    move $t7, $ra
    mtc1 $a0, $f12
    li   $v0, 9
    li   $a0, 48
    syscall
    move $t9, $v0
    move $t8, $t9
    mtc1 $zero, $f14
    c.lt.s $f12, $f14
    bc1f __ft_pos
    li   $t0, 45
    sb   $t0, 0($t8)
    addiu $t8, $t8, 1
    neg.s $f12, $f12
__ft_pos:
    trunc.w.s $f16, $f12
    mfc1 $a0, $f16
    cvt.s.w $f16, $f16
    sub.s $f18, $f12, $f16
    jal  __itoa
__ft_ent:
    lb   $t0, 0($v0)
    beqz $t0, __ft_punto
    sb   $t0, 0($t8)
    addiu $t8, $t8, 1
    addiu $v0, $v0, 1
    j    __ft_ent
__ft_punto:
    li   $t0, 46
    sb   $t0, 0($t8)
    addiu $t8, $t8, 1
    li   $t1, 0
    li   $t2, 0x41200000
    mtc1 $t2, $f20
__ft_frac:
    mul.s $f18, $f18, $f20
    trunc.w.s $f16, $f18
    mfc1 $t0, $f16
    addiu $t3, $t0, 48
    sb   $t3, 0($t8)
    addiu $t8, $t8, 1
    cvt.s.w $f16, $f16
    sub.s $f18, $f18, $f16
    addiu $t1, $t1, 1
    mtc1 $zero, $f14
    c.eq.s $f18, $f14
    bc1t __ft_recorta
    li   $t4, 6
    blt  $t1, $t4, __ft_frac
__ft_recorta:
    lb   $t0, -1($t8)
    li   $t3, 48
    bne  $t0, $t3, __ft_fin
    lb   $t0, -2($t8)
    li   $t3, 46
    beq  $t0, $t3, __ft_fin
    addiu $t8, $t8, -1
    j    __ft_recorta
__ft_fin:
    sb   $zero, 0($t8)
    move $v0, $t9
    jr   $t7
""", ["__itoa"])

rutina("__boolstr", """\
# $a0 (0 o 1) -> $v0 = "true" / "false"
__boolstr:
    la   $v0, rt_false
    beqz $a0, __bs_fin
    la   $v0, rt_true
__bs_fin:
    jr   $ra
""")

rutina("__objstr", """\
# $a0 = objeto -> $v0 = "<Clase>" (el nombre esta en la palabra 0 de la vtable); null -> "null"
__objstr:
    addiu $sp, $sp, -8
    sw   $ra, 4($sp)
    bnez $a0, __os_ok
    la   $v0, rt_null
    j    __os_ret
__os_ok:
    lw   $t0, 0($a0)
    lw   $t0, 0($t0)
    sw   $t0, 0($sp)
    la   $a0, rt_lt
    lw   $a1, 0($sp)
    jal  __concat
    move $a0, $v0
    la   $a1, rt_gt
    jal  __concat
__os_ret:
    lw   $ra, 4($sp)
    addiu $sp, $sp, 8
    jr   $ra
""", ["__concat"])

rutina("__valstr", """\
# $a0 = valor, $a1 = clase del valor (0 int, 1 float, 2 string, 3 bool, 4 objeto, 5 otro; +8 por cada
# nivel de arreglo: 8 = arreglo de enteros, 16 = arreglo de arreglos de enteros) -> $v0 = cadena
__valstr:
    li   $t0, 8
    blt  $a1, $t0, __vs_base
    addiu $a1, $a1, -8
    j    __arrstr
__vs_base:
    beqz $a1, __itoa
    li   $t0, 1
    beq  $a1, $t0, __ftoa
    li   $t0, 2
    beq  $a1, $t0, __vs_str
    li   $t0, 3
    beq  $a1, $t0, __boolstr
    li   $t0, 4
    beq  $a1, $t0, __objstr
    la   $v0, rt_array
    jr   $ra
__vs_str:
    move $v0, $a0
    bnez $v0, __vs_fin
    la   $v0, rt_null
__vs_fin:
    jr   $ra
""", ["__itoa", "__ftoa", "__boolstr", "__objstr", "__arrstr"])

rutina("__arrstr", """\
# $a0 = arreglo, $a1 = clase de los elementos (como en __valstr) -> $v0 = "[a, b, c]"
__arrstr:
    addiu $sp, $sp, -20
    sw   $ra, 16($sp)
    sw   $a0, 0($sp)
    sw   $a1, 4($sp)
    sw   $zero, 8($sp)
    bnez $a0, __as_ok
    la   $v0, rt_null
    j    __as_ret
__as_ok:
    la   $v0, rt_lb
    sw   $v0, 12($sp)
__as_lazo:
    lw   $t0, 0($sp)
    lw   $t1, 8($sp)
    lw   $t2, 0($t0)
    bge  $t1, $t2, __as_cierra
    beqz $t1, __as_sinsep
    lw   $a0, 12($sp)
    la   $a1, rt_sep
    jal  __concat
    sw   $v0, 12($sp)
__as_sinsep:
    lw   $t0, 0($sp)
    lw   $t1, 8($sp)
    sll  $t1, $t1, 2
    addu $t0, $t0, $t1
    lw   $a0, 4($t0)
    lw   $a1, 4($sp)
    jal  __valstr
    lw   $a0, 12($sp)
    move $a1, $v0
    jal  __concat
    sw   $v0, 12($sp)
    lw   $t1, 8($sp)
    addiu $t1, $t1, 1
    sw   $t1, 8($sp)
    j    __as_lazo
__as_cierra:
    lw   $a0, 12($sp)
    la   $a1, rt_rb
    jal  __concat
__as_ret:
    lw   $ra, 16($sp)
    addiu $sp, $sp, 20
    jr   $ra
""", ["__valstr", "__concat"])

rutina("__print_str", """\
# imprime la cadena de $a0 (o "null") y un salto de linea
__print_str:
    bnez $a0, __ps_ok
    la   $a0, rt_null
__ps_ok:
    li   $v0, 4
    syscall
    li   $a0, 10
    li   $v0, 11
    syscall
    jr   $ra
""")

rutina("__pushtry", """\
# $a0 = direccion del manejador; guarda tambien $sp y $fp del llamador
__pushtry:
    lw   $t8, exc_n
    mul  $t9, $t8, 12
    la   $t7, exc_pila
    addu $t7, $t7, $t9
    sw   $a0, 0($t7)
    sw   $sp, 4($t7)
    sw   $fp, 8($t7)
    addiu $t8, $t8, 1
    sw   $t8, exc_n
    jr   $ra
""")

rutina("__throw", """\
# $a0 = mensaje. Salta al manejador mas reciente restaurando su $sp y $fp
__throw:
    sw   $a0, exc_msg
    lw   $t1, exc_n
    beqz $t1, __no_capturada
    addiu $t1, $t1, -1
    sw   $t1, exc_n
    mul  $t2, $t1, 12
    la   $t3, exc_pila
    addu $t3, $t3, $t2
    lw   $t4, 0($t3)
    lw   $sp, 4($t3)
    lw   $fp, 8($t3)
    jr   $t4
__no_capturada:
    la   $a0, rt_uncaught
    li   $v0, 4
    syscall
    lw   $a0, exc_msg
    li   $v0, 4
    syscall
    li   $a0, 10
    li   $v0, 11
    syscall
    li   $a0, 1
    li   $v0, 17
    syscall
""")


def cerrar(usadas):
    """Rutinas pedidas mas sus dependencias, en orden estable."""
    resultado = []
    pendientes = list(usadas)
    while pendientes:
        nombre = pendientes.pop()
        if nombre in resultado:
            continue
        resultado.append(nombre)
        pendientes.extend(RUTINAS[nombre][1])
    return sorted(resultado)


def texto(usadas):
    return "\n".join(RUTINAS[n][0] for n in cerrar(usadas))
