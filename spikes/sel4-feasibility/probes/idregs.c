/* A3 probe: print AArch64 ID registers on the PL011 UART of the QEMU virt machine, then halt.
 * Freestanding, no kernel. Spike code. Built and run by probe-idregs.sh. */
typedef unsigned long u64;

#define UART ((volatile unsigned char *)0x09000000UL)

static void putc_(char c) { *UART = (unsigned char)c; }

static void puts_(const char *s) {
    while (*s) {
        putc_(*s++);
    }
}

static void hex(u64 v) {
    for (int i = 60; i >= 0; i -= 4) {
        putc_("0123456789abcdef"[(v >> i) & 15]);
    }
}

#define RD(reg) ({ u64 v_; __asm__ volatile("mrs %0, " #reg : "=r"(v_)); v_; })
#define SHOW(reg) do { puts_(#reg "="); hex(RD(reg)); puts_("\n"); } while (0)

__asm__(".section .text.boot\n.globl _start\n_start:\n"
        "  ldr x0, =0x40200000\n  mov sp, x0\n  bl probe_main\n1: wfe\n  b 1b\n");

void probe_main(void) {
    puts_("PROBE-BEGIN\n");
    SHOW(CurrentEL);
    SHOW(MIDR_EL1);
    SHOW(ID_AA64MMFR0_EL1);
    SHOW(ID_AA64MMFR1_EL1);
    SHOW(ID_AA64PFR0_EL1);
    SHOW(ID_AA64ISAR0_EL1);
    u64 mmfr0 = RD(ID_AA64MMFR0_EL1);
    puts_("ASIDBits(MMFR0[7:4])=");
    hex((mmfr0 >> 4) & 0xf);
    puts_("  (0=8-bit, 2=16-bit)\nPROBE-END\n");
}
