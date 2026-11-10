//
// SPDX-License-Identifier: BSD-2-Clause
//
// Release-kernel execution test: the worker threads. Each is a second thread of the root task's own address space
// and capability space, with no IPC buffer and no thread-local storage, so it uses only the register-only calls of
// `rawsys.rs` and the atomics below. A worker never prints: it reports to the root task by `seL4_Call`, and the root
// task attributes the report by the badge of the capability the worker was given.
//
// These workers are test code inside the root task's trust domain. They share its capability space, so nothing here
// is an isolation claim: the tests exercise kernel paths (IPC, faults, revocation, page permissions, the timer, and
// on an SMP kernel the other cores) and say whether each behaved as the kernel's interface specifies.
//

use core::arch::asm;
use core::sync::atomic::{AtomicBool, AtomicU64, Ordering};

use crate::rawsys::{self, Answer};

/// Labels of the worker protocol (the message label is 52 bits wide; these are arbitrary distinct values).
pub(crate) const L_IPC: u64 = 0x101;
pub(crate) const L_IPC_REPLY: u64 = 0x102;
pub(crate) const L_STEP: u64 = 0x103;
pub(crate) const L_GO: u64 = 0x104;
pub(crate) const L_DONE: u64 = 0x105;
pub(crate) const L_PING: u64 = 0x106;
pub(crate) const L_PONG: u64 = 0x107;

/// How far each of the two preemption workers must see the other get before it stops.
pub(crate) const PAIR_TARGET: u64 = 1000;
/// The most iterations a preemption or SMP worker makes before it gives up and reports what it saw.
pub(crate) const SPIN_LIMIT: u64 = 2_000_000_000;
/// Cores the SMP test can address.
pub(crate) const MAX_CORES: usize = 8;

pub(crate) static PAIR: [AtomicU64; 2] = [AtomicU64::new(0), AtomicU64::new(0)];
pub(crate) static CORE_COUNT: [AtomicU64; MAX_CORES] = [const { AtomicU64::new(0) }; MAX_CORES];
pub(crate) static CORE_STOP: [AtomicBool; MAX_CORES] = [const { AtomicBool::new(false) }; MAX_CORES];

/// The answer the IPC worker expects for the two words it sends.
pub(crate) fn mix(x: u64, y: u64) -> u64 {
    (x ^ y).rotate_left(17).wrapping_add(0x5eed)
}

pub(crate) type Entry = extern "C" fn(u64, u64, u64) -> !;

/// Last report of a worker. The root task does not answer it, so the worker stays blocked in the kernel.
fn finish(cptr: u64, mr: [u64; 4]) -> ! {
    rawsys::call(cptr, L_DONE, mr);
    loop {
        core::hint::spin_loop();
    }
}

/// Reads one byte at `addr` with a plain load instruction.
///
/// # Safety
///
/// `addr` must be either an address at which this thread's access traps (the kernel then stops the thread and no
/// value is produced), or a mapped byte that no Rust reference covers.
unsafe fn load_byte(addr: u64) -> u8 {
    let value: u32;
    // SAFETY: the caller guarantees the two cases above; the instruction reads one byte and writes only the output
    // register.
    unsafe {
        asm!("ldrb {v:w}, [{a}]", a = in(reg) addr, v = out(reg) value, options(nostack, readonly));
    }
    value as u8
}

/// Writes one byte at `addr` with a plain store instruction.
///
/// # Safety
///
/// As `load_byte`; and if the byte is mapped writable, nothing else may rely on its value.
unsafe fn store_byte(addr: u64, value: u8) {
    // SAFETY: the caller guarantees the cases above; the instruction writes one byte at `addr` and nothing else.
    unsafe {
        asm!("strb {v:w}, [{a}]", a = in(reg) addr, v = in(reg) u32::from(value), options(nostack));
    }
}

/// IPC: sends two words, checks the answer, reports whether it was the expected one.
pub(crate) extern "C" fn ipc_worker(cptr: u64, x: u64, y: u64) -> ! {
    let answer: Answer = rawsys::call(cptr, L_IPC, [x, y, 0, 0]);
    let ok = answer.label() == L_IPC_REPLY && answer.mr[0] == mix(x, y);
    finish(cptr, [u64::from(ok), answer.mr[0], answer.label(), 0])
}

/// Fault: reads `addr`, which the root task left unmapped. Reaching the report means the read did not fault.
pub(crate) extern "C" fn read_fault_worker(cptr: u64, addr: u64, _unused: u64) -> ! {
    // SAFETY: the root task passes an address it has left (or made) unmapped, so the access traps; if the kernel
    // wrongly let it through, the byte read is only reported, never interpreted.
    let value = unsafe { load_byte(addr) };
    finish(cptr, [0xbad, u64::from(value), 0, 0])
}

/// Debug system call: issues the number `seL4_DebugPutChar` has on a printing kernel, then reports that it returned.
pub(crate) extern "C" fn debug_syscall_worker(cptr: u64, byte: u64, _unused: u64) -> ! {
    rawsys::debug_put_char_probe(byte as u8);
    finish(cptr, [1, 0, 0, 0])
}

/// Revocation: calls through `victim` (a capability the root task will revoke), tells the root task, calls again.
pub(crate) extern "C" fn revoke_worker(cptr: u64, victim: u64, _unused: u64) -> ! {
    let first = rawsys::call(victim, L_PING, [1, 0, 0, 0]);
    rawsys::call(cptr, L_STEP, [first.label(), 0, 0, 0]);
    let second = rawsys::call(victim, L_PING, [2, 0, 0, 0]);
    finish(cptr, [first.label(), second.label(), 0, 0])
}

/// Page permissions: reads the byte at `addr` (mapped read-only), reports it, then writes to it. Reaching the last
/// report means the write did not fault.
pub(crate) extern "C" fn write_fault_worker(cptr: u64, addr: u64, _unused: u64) -> ! {
    // SAFETY: the root task mapped `addr` readable for this test and holds no reference to that page (it accesses the
    // same frame through a different mapping, with volatile reads and writes only).
    let value = unsafe { load_byte(addr) };
    rawsys::call(cptr, L_STEP, [u64::from(value), 0, 0, 0]);
    // SAFETY: `addr` is mapped read-only, so the store traps; if the kernel wrongly allowed it, the page is test data
    // that the root task reads back with a volatile read, and reports.
    unsafe { store_byte(addr, 0xee) };
    finish(cptr, [0xbad, 0, 0, 0])
}

/// Preemption: two of these run at the same priority on one core. Each counts, and stops when it has seen the other
/// reach `PAIR_TARGET`, which can only happen if the kernel's timer interrupt preempts whichever runs first.
pub(crate) extern "C" fn pair_worker(cptr: u64, me: u64, _unused: u64) -> ! {
    let (mine, other) = if me == 0 { (&PAIR[0], &PAIR[1]) } else { (&PAIR[1], &PAIR[0]) };
    let mut iterations = 0u64;
    while iterations < SPIN_LIMIT {
        mine.fetch_add(1, Ordering::Relaxed);
        iterations += 1;
        if iterations >= PAIR_TARGET && other.load(Ordering::Relaxed) >= PAIR_TARGET {
            break;
        }
    }
    finish(cptr, [iterations, other.load(Ordering::Relaxed), 0, 0])
}

/// SMP: counts in `CORE_COUNT[index]` until the root task sets the stop flag, then reports how far it got.
pub(crate) extern "C" fn core_worker(cptr: u64, index: u64, _unused: u64) -> ! {
    let index = (index as usize) % MAX_CORES;
    let mut iterations = 0u64;
    while iterations < SPIN_LIMIT && !CORE_STOP[index].load(Ordering::Relaxed) {
        CORE_COUNT[index].fetch_add(1, Ordering::Relaxed);
        iterations += 1;
    }
    finish(cptr, [iterations, 0, 0, 0])
}
