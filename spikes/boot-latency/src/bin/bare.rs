//! Direct-boot AArch64 image for QEMU `virt`: print over PL011, spin, power off.
#![no_std]
#![no_main]

use core::arch::{asm, global_asm};
use core::panic::PanicInfo;
use core::ptr::write_volatile;

/// PL011 data register on QEMU `virt`.
const UART_DR: *mut u8 = 0x0900_0000 as *mut u8;
/// PSCI 0.2 `SYSTEM_OFF` function id.
const PSCI_SYSTEM_OFF: u64 = 0x8400_0008;
/// Iterations of the fixed integer workload, set at build time.
const SPIN: Option<&str> = option_env!("SPIKE_SPIN");

global_asm!(
    ".section .text._start, \"ax\"",
    ".global _start",
    "_start:",
    "ldr x1, =__stack_top",
    "mov sp, x1",
    "bl spike_main",
    "1: wfe",
    "b 1b",
);

fn parse(digits: Option<&str>) -> u64 {
    let mut value = 0u64;
    if let Some(text) = digits {
        for byte in text.bytes() {
            value = value.wrapping_mul(10).wrapping_add(u64::from(byte - b'0'));
        }
    }
    value
}

fn print(text: &str) {
    for byte in text.bytes() {
        // SAFETY: UART_DR is the always-mapped PL011 MMIO data register on QEMU
        // `virt`; the MMU is off, and this single-threaded spike is its only user.
        unsafe { write_volatile(UART_DR, byte) };
    }
}

fn workload(iterations: u64) -> u64 {
    let mut state = 0x2545_F491_4F6C_DD1Du64;
    for _ in 0..iterations {
        state ^= state << 13;
        state ^= state >> 7;
        state ^= state << 17;
    }
    state
}

#[unsafe(no_mangle)]
extern "C" fn spike_main() -> ! {
    print("FYRKAT-SPIKE bare start\n");
    let result = workload(parse(SPIN));
    print(if result == 0 { "FYRKAT-SPIKE zero\n" } else { "FYRKAT-SPIKE done\n" });
    // SAFETY: PSCI SYSTEM_OFF does not return; QEMU `virt` without EL2/EL3
    // firmware services it through the HVC conduit.
    unsafe { asm!("hvc #0", in("x0") PSCI_SYSTEM_OFF, options(noreturn)) }
}

#[panic_handler]
fn panic(_info: &PanicInfo) -> ! {
    print("FYRKAT-SPIKE panic\n");
    loop {
        core::hint::spin_loop();
    }
}
