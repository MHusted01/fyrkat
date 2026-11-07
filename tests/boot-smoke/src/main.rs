//! Toolchain and firmware pipeline check. This is not a kernel.
//!
//! A minimal UEFI application for AArch64 and x86-64: print a marker on the firmware
//! console, then ask the firmware to shut the machine down. `cargo xtask boot` runs it
//! under QEMU and fails unless the marker appears.
#![no_std]
#![no_main]

use core::ffi::c_void;
use core::panic::PanicInfo;

/// `cargo xtask boot` looks for exactly this text on the serial console.
const MARKER: &str = "FYRKAT-BOOT-SMOKE: ok\r\n";
/// `EfiResetShutdown` from the UEFI specification.
const RESET_SHUTDOWN: u32 = 2;
/// UCS-2 buffer size for one console write, including the terminating zero.
const BUFFER_LEN: usize = 64;

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
    /// `GetTime` through `GetNextHighMonotonicCount`, unused here.
    unused: [usize; 10],
    reset_system: extern "efiapi" fn(u32, usize, usize, *const c_void) -> !,
}

/// The system table up to `runtime_services`. Later fields are never read.
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
}

fn print(table: *mut SystemTable, text: &str) {
    let mut buffer = [0u16; BUFFER_LEN];
    for (slot, byte) in buffer.iter_mut().zip(text.bytes().take(BUFFER_LEN - 1)) {
        *slot = u16::from(byte);
    }
    // SAFETY: firmware passes a valid system table to the entry point, and boot services
    // are still active, so the ConOut pointer is valid.
    let output = unsafe { (*table).console_out };
    // SAFETY: ConOut points to a valid text output protocol instance.
    let output_string = unsafe { (*output).output_string };
    // The buffer is zero-terminated because only BUFFER_LEN - 1 slots are written. The
    // returned status is ignored: there is nowhere else to report a console failure.
    output_string(output, buffer.as_ptr());
}

#[unsafe(no_mangle)]
extern "efiapi" fn efi_main(_image: *mut c_void, table: *mut SystemTable) -> usize {
    print(table, MARKER);
    // SAFETY: firmware passes a valid system table to the entry point.
    let runtime = unsafe { (*table).runtime_services };
    // SAFETY: runtime services stay valid for the life of the system table.
    let reset_system = unsafe { (*runtime).reset_system };
    // ResetSystem with a shutdown type does not return.
    reset_system(RESET_SHUTDOWN, 0, 0, core::ptr::null())
}

#[panic_handler]
fn panic(_info: &PanicInfo) -> ! {
    loop {
        core::hint::spin_loop();
    }
}
