//! Minimal UEFI application shared by AArch64 and x86-64: print, run one fixed
//! workload, shut down. The workload is chosen at build time so that emulator
//! cost can be compared across integer, memory and exception-heavy behaviour.
#![no_std]
#![no_main]

use core::ffi::c_void;
use core::panic::PanicInfo;

/// Iterations of the selected workload, set at build time.
const SPIN: Option<&str> = option_env!("SPIKE_SPIN");
/// Workload selector: `alu` (default), `mem` or `trap`.
const KIND: Option<&str> = option_env!("SPIKE_KIND");
/// 64 MiB working set in 4 KiB pages: larger than the host's caches.
const MEM_PAGES: usize = 16_384;
/// `AllocateAnyPages` and `EfiLoaderData` from the UEFI specification.
const ALLOCATE_ANY_PAGES: u32 = 0;
const LOADER_DATA: u32 = 2;
/// `EfiResetShutdown` from the UEFI specification.
const RESET_SHUTDOWN: u32 = 2;

#[repr(C)]
struct TableHeader {
    signature: u64,
    revision: u32,
    header_size: u32,
    crc32: u32,
    reserved: u32,
}

#[repr(C)]
struct TextOutput {
    reset: usize,
    output_string: extern "efiapi" fn(*mut TextOutput, *const u16) -> usize,
}

#[repr(C)]
struct RuntimeServices {
    header: TableHeader,
    /// GetTime through GetNextHighMonotonicCount, unused here.
    unused: [usize; 10],
    reset_system: extern "efiapi" fn(u32, usize, usize, *const c_void) -> !,
}

#[repr(C)]
struct BootServices {
    header: TableHeader,
    /// RaiseTPL and RestoreTPL, unused here.
    unused: [usize; 2],
    allocate_pages: extern "efiapi" fn(u32, u32, usize, *mut u64) -> usize,
}

#[repr(C)]
struct SystemTable {
    header: TableHeader,
    firmware_vendor: *const u16,
    firmware_revision: u32,
    console_in_handle: *mut c_void,
    console_in: *mut c_void,
    console_out_handle: *mut c_void,
    console_out: *mut TextOutput,
    standard_error_handle: *mut c_void,
    standard_error: *mut c_void,
    runtime_services: *mut RuntimeServices,
    boot_services: *mut BootServices,
}

fn parse(digits: Option<&str>) -> u64 {
    let mut value = 0u64;
    if let Some(text) = digits {
        for byte in text.bytes() {
            value = value.wrapping_mul(10).wrapping_add(u64::from(byte - b'0'));
        }
    }
    value
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

/// Random read-modify-write over a buffer larger than cache, to exercise the
/// memory path that a software MMU must emulate on every access.
fn memory_workload(table: *mut SystemTable, iterations: u64) -> u64 {
    let mut base = 0u64;
    // SAFETY: boot services are active and `base` is a valid out-pointer.
    let status = unsafe {
        let services = (*table).boot_services;
        ((*services).allocate_pages)(ALLOCATE_ANY_PAGES, LOADER_DATA, MEM_PAGES, &raw mut base)
    };
    if status != 0 || iterations == 0 {
        return u64::from(status == 0);
    }
    let words = MEM_PAGES * 4096 / 8;
    let mask = (words - 1) as u64;
    let buffer = base as *mut u64;
    let mut state = 0x9E37_79B9_7F4A_7C15u64;
    for _ in 0..iterations {
        state = state.wrapping_mul(6_364_136_223_846_793_005).wrapping_add(1_442_695_040_888_963_407);
        // SAFETY: firmware returned MEM_PAGES pages at `base`, and the mask keeps
        // the index inside that allocation. Firmware identity-maps loader data.
        unsafe {
            let slot = buffer.add(((state >> 33) & mask) as usize);
            slot.write_volatile(slot.read_volatile().wrapping_add(state));
        }
    }
    state | 1
}

#[cfg(target_arch = "aarch64")]
core::arch::global_asm!(
    ".section .text",
    ".balign 2048",
    "spike_vectors:",
    ".rept 16",
    "eret",
    ".balign 128",
    ".endr",
);

/// Take and return from `iterations` synchronous exceptions at the current EL.
#[cfg(target_arch = "aarch64")]
fn trap_workload(iterations: u64) -> u64 {
    use core::arch::asm;
    unsafe extern "C" {
        static spike_vectors: u8;
    }
    let (mut saved_vbar, mut saved_daif): (u64, u64);
    // SAFETY: interrupts stay masked while our table is installed, so only the
    // SVC below reaches it. Every entry is ERET, and the original VBAR and DAIF
    // are restored before returning to firmware.
    unsafe {
        asm!("mrs {0}, daif", "msr daifset, #0xf", "mrs {1}, vbar_el1", out(reg) saved_daif, out(reg) saved_vbar);
        asm!("msr vbar_el1, {0}", "isb", in(reg) &raw const spike_vectors);
        for _ in 0..iterations {
            asm!("svc #0");
        }
        asm!("msr vbar_el1, {0}", "isb", "msr daif, {1}", in(reg) saved_vbar, in(reg) saved_daif);
    }
    iterations | 1
}

#[cfg(target_arch = "x86_64")]
core::arch::global_asm!(".section .text", "spike_isr:", "iretq");

#[cfg(target_arch = "x86_64")]
#[repr(C, packed)]
struct DescriptorTablePointer {
    limit: u16,
    base: u64,
}

/// Take and return from `iterations` software interrupts at the current ring.
#[cfg(target_arch = "x86_64")]
fn trap_workload(iterations: u64) -> u64 {
    use core::arch::asm;
    unsafe extern "C" {
        static spike_isr: u8;
    }
    const VECTOR: usize = 0x80;
    const INTERRUPT_GATE: u64 = 0x8E;
    let handler = &raw const spike_isr as u64;
    let selector: u16;
    // SAFETY: reading CS has no side effects.
    unsafe { asm!("mov {0:x}, cs", out(reg) selector) };
    let mut table = [0u64; 512];
    table[VECTOR * 2] = (handler & 0xFFFF)
        | (u64::from(selector) << 16)
        | (INTERRUPT_GATE << 40)
        | ((handler >> 16) & 0xFFFF) << 48;
    table[VECTOR * 2 + 1] = handler >> 32;
    let new = DescriptorTablePointer { limit: 4095, base: table.as_ptr() as u64 };
    let mut old = DescriptorTablePointer { limit: 0, base: 0 };
    let flags: u64;
    // SAFETY: interrupts are disabled while the temporary IDT is installed, so
    // only the INT below reaches it. Its one gate targets an IRETQ stub, and the
    // firmware IDT and flags are restored before returning.
    unsafe {
        asm!("pushfq", "pop {0}", "cli", out(reg) flags);
        asm!("sidt [{0}]", in(reg) &raw mut old);
        asm!("lidt [{0}]", in(reg) &raw const new);
        for _ in 0..iterations {
            asm!("int 0x80");
        }
        asm!("lidt [{0}]", in(reg) &raw const old);
        asm!("push {0}", "popfq", in(reg) flags);
    }
    iterations | 1
}

fn print(table: *mut SystemTable, text: &str) {
    let mut buffer = [0u16; 64];
    for (slot, byte) in buffer.iter_mut().zip(text.bytes().take(63)) {
        *slot = u16::from(byte);
    }
    // SAFETY: firmware passes a valid system table to the entry point and boot
    // services are active, so ConOut and its OutputString member are valid.
    unsafe {
        let output = (*table).console_out;
        ((*output).output_string)(output, buffer.as_ptr());
    }
}

#[unsafe(no_mangle)]
extern "efiapi" fn efi_main(_image: *mut c_void, table: *mut SystemTable) -> usize {
    print(table, "FYRKAT-SPIKE uefi start\r\n");
    let iterations = parse(SPIN);
    let result = match KIND {
        Some("mem") => memory_workload(table, iterations),
        Some("trap") => trap_workload(iterations),
        _ => workload(iterations),
    };
    print(table, if result == 0 { "FYRKAT-SPIKE zero\r\n" } else { "FYRKAT-SPIKE done\r\n" });
    // SAFETY: runtime services stay valid for the life of the system table, and
    // ResetSystem with a shutdown type does not return.
    unsafe { ((*(*table).runtime_services).reset_system)(RESET_SHUTDOWN, 0, 0, core::ptr::null()) }
}

#[panic_handler]
fn panic(_info: &PanicInfo) -> ! {
    loop {
        core::hint::spin_loop();
    }
}
