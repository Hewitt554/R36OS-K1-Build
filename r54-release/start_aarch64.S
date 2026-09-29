.global _start
.type _start,%function
_start:
    mov x0, sp
    bl start_c
    mov x8, #93
    svc #0
1:  wfe
    b 1b
