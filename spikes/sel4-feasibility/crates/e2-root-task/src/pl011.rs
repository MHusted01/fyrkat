//
// SPDX-License-Identifier: BSD-2-Clause
//
// A user-level console on the PL011 UART of QEMU `virt` (registers at 0x09000000), for kernels built without
// `KernelPrinting`: such a kernel has no `seL4_DebugPutChar`, so a task that wants to say anything has to drive the
// UART itself. The kernel leaves the UART to user level (`tools/hardware.yml` marks it `user: true`, and maps it for
// itself only under `CONFIG_PRINTING`), so its page is inside a device untyped of the boot information.
//
// Polled transmit only: no receive, no interrupts. Register offsets and bits are those of the Arm PrimeCell UART
// (PL011) Technical Reference Manual, DDI 0183, chapter 3. The baud-rate divisors are left as the earlier boot stage
// set them: QEMU ignores them, and on hardware they depend on a clock this code does not know. Emulator use only.
//
// Only the thread that called `init` should print: there is no lock, and a second writer would interleave bytes (never
// worse: each byte is one register write). This is a convention, not something the module enforces; the one way another
// thread gets here is the panic hook of a worker thread that panics, whose garbled message is still better than none.
//

use core::fmt;
use core::sync::atomic::{AtomicUsize, Ordering};

use crate::a5_mmio::Page;

/// Physical address of the PL011 on QEMU `virt` (the `pl011@9000000` node of QEMU's device tree).
pub(crate) const UART_PADDR: usize = 0x0900_0000;

const DR: usize = 0x00;
const FR: usize = 0x18;
const LCR_H: usize = 0x2c;
const CR: usize = 0x30;
const IMSC: usize = 0x38;
const ICR: usize = 0x44;

const FR_BUSY: u32 = 1 << 3;
const FR_TXFF: u32 = 1 << 5;
const LCR_H_FEN: u32 = 1 << 4;
const LCR_H_WLEN_8: u32 = 0b11 << 5;
const CR_UARTEN: u32 = 1 << 0;
const CR_TXE: u32 = 1 << 8;
/// How many times `put_byte` and `init` poll a status bit before giving up, so that a dead UART cannot hang the task.
const POLL_LIMIT: u32 = 1_000_000;

/// Virtual address of the mapped UART page; 0 until `init` has run.
static UART_VA: AtomicUsize = AtomicUsize::new(0);
/// Bytes dropped because the transmit FIFO stayed full for `POLL_LIMIT` polls. Reported by `dropped`.
static DROPPED: AtomicUsize = AtomicUsize::new(0);

/// Programs the UART for 8 data bits, FIFOs on, transmitter on, all interrupts masked, and makes it the console.
/// Follows the TRM's order: wait for the current character, disable, flush (FIFOs off), program, enable.
pub(crate) fn init(page: Page) {
    for _ in 0..POLL_LIMIT {
        if page.r32(FR) & FR_BUSY == 0 {
            break;
        }
    }
    page.w32(CR, 0);
    page.w32(LCR_H, LCR_H_WLEN_8);
    page.w32(IMSC, 0);
    page.w32(ICR, 0x7ff);
    page.w32(LCR_H, LCR_H_WLEN_8 | LCR_H_FEN);
    page.w32(CR, CR_UARTEN | CR_TXE);
    UART_VA.store(page.addr(), Ordering::Release);
}

/// The console's UART page, once `init` has run.
fn uart() -> Option<Page> {
    let va = UART_VA.load(Ordering::Acquire);
    // SAFETY: the only value ever stored in `UART_VA` besides 0 is `Page::addr` of the page passed to `init`, which the
    // device mapper mapped read-write from a device frame it retyped itself, never unmaps, and whose capability nothing
    // in these programs revokes.
    (va != 0).then(|| unsafe { Page::from_addr(va) })
}

/// The control register as the UART reports it, for the log (shows that the programming above took effect).
pub(crate) fn control() -> Option<u32> {
    uart().map(|page| page.r32(CR))
}

pub(crate) fn dropped() -> usize {
    DROPPED.load(Ordering::Relaxed)
}

/// Sends one byte, waiting for room in the transmit FIFO. Before `init` it does nothing.
pub(crate) fn put_byte(byte: u8) {
    let Some(page) = uart() else {
        return;
    };
    for _ in 0..POLL_LIMIT {
        if page.r32(FR) & FR_TXFF == 0 {
            page.w32(DR, u32::from(byte));
            return;
        }
    }
    DROPPED.fetch_add(1, Ordering::Relaxed);
}

/// `core::fmt` sink for the console; newlines are sent as CR LF.
pub(crate) struct Console;

impl fmt::Write for Console {
    fn write_str(&mut self, s: &str) -> fmt::Result {
        for byte in s.bytes() {
            if byte == b'\n' {
                put_byte(b'\r');
            }
            put_byte(byte);
        }
        Ok(())
    }
}

/// Prints a line on the user-level console. Works on every kernel configuration, with or without kernel printing.
#[macro_export]
macro_rules! uprintln {
    ($($arg:tt)*) => {{
        use core::fmt::Write as _;
        // The console's `write_str` never fails, so the result carries no information.
        let _ = writeln!($crate::pl011::Console, $($arg)*);
    }};
}

/// As `uprintln!`, without the line end.
#[macro_export]
macro_rules! uprint {
    ($($arg:tt)*) => {{
        use core::fmt::Write as _;
        // The console's `write_str` never fails, so the result carries no information.
        let _ = write!($crate::pl011::Console, $($arg)*);
    }};
}
