.section .text.start,"ax",%progbits
.global _start
.type _start,%function
_start:
    mov x29, xzr
    mov x30, xzr
    bl k1_main
1:  b 1b
.size _start, .-_start
