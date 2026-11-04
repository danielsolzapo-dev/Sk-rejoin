/* Minimal Windows x64 launcher. The app itself runs in Python. */
.text
.globl main
main:
    sub $72, %rsp
    xor %ecx, %ecx
    lea path(%rip), %rdx
    mov $32768, %r8d
    call *getmodule(%rip)
    test %eax, %eax
    jz fail
    cmp $32768, %eax
    jae fail
    lea path(%rip), %r10
    lea (%r10,%rax,2), %r11
find_separator:
    sub $2, %r11
    cmp %r10, %r11
    jb fail
    cmpw $92, (%r11)
    jne find_separator
    movw $0, (%r11)
    xor %ecx, %ecx
    xor %edx, %edx
    lea python(%rip), %r8
    lea args(%rip), %r9
    lea path(%rip), %rax
    mov %rax, 32(%rsp)
    movq $1, 40(%rsp)
    call *shell(%rip)
    cmp $32, %rax
    jbe fail
    xor %ecx, %ecx
    call *exitprocess(%rip)
fail:
    xor %ecx, %ecx
    lea error(%rip), %rdx
    lea title(%rip), %r8
    mov $16, %r9d
    call *message(%rip)
    mov $1, %ecx
    call *exitprocess(%rip)
python: .short 112,121,119,46,101,120,101,0
args: .short 45,51,32,97,112,112,46,112,121,0
title: .short 82,101,106,111,105,110,32,68,101,115,107,0
error: .short 73,110,115,116,97,108,101,32,80,121,116,104,111,110,32,51,32,99,111,109,32,111,32,108,97,117,110,99,104,101,114,32,112,121,119,46,101,120,101,46,0
.bss
.balign 16
path: .skip 65536
.section .idata$2,"aw"
idata:
.macro rva label
.long \label - idata + 0x2000
.endm
.macro descriptor lookup, dll, address
rva \lookup
.long 0,0
rva \dll
rva \address
.endm
descriptor kernel_l, kernel, getmodule
descriptor shell_l, shell_dll, shell
descriptor user_l, user_dll, message
.long 0,0,0,0,0
.balign 8
.macro thunk label
rva \label
.long 0
.endm
kernel_l: thunk gm
thunk ep
.quad 0
shell_l: thunk se
.quad 0
user_l: thunk mb
.quad 0
getmodule: thunk gm
exitprocess: thunk ep
.quad 0
shell: thunk se
.quad 0
message: thunk mb
.quad 0
kernel: .asciz "KERNEL32.dll"
shell_dll: .asciz "SHELL32.dll"
user_dll: .asciz "USER32.dll"
.balign 2
gm: .short 0
.asciz "GetModuleFileNameW"
.balign 2
ep: .short 0
.asciz "ExitProcess"
.balign 2
se: .short 0
.asciz "ShellExecuteW"
.balign 2
mb: .short 0
.asciz "MessageBoxW"
