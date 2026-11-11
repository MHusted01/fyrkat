//
// SPDX-License-Identifier: BSD-2-Clause
//
// Raw seL4 system calls for worker threads that have neither an IPC buffer nor thread-local storage, so they cannot
// use the `sel4` crate's calls (those find the IPC buffer through a thread-local). A message of up to four words
// travels in registers only, which is all a worker needs to report a result.
//
// The register convention is the one of the pinned seL4's `libsel4/sel4_arch_include/aarch64/sel4/sel4_arch/syscalls.h`
// (`arm_sys_send_recv`): x0 the capability address (the badge on return), x1 the message information word, x2 to x5
// the first four message registers, x7 the system-call number, entered with `svc #0`. Non-MCS kernels only: on MCS the
// numbers differ and x6 carries a reply capability.
//

use core::arch::asm;

/// `seL4_SysCall` in every non-MCS configuration (`libsel4/include/sel4/syscall.h`, generated).
const SYS_CALL: i64 = -1;
/// The number `seL4_SysDebugPutChar` has in a non-MCS kernel **with** `CONFIG_PRINTING`. A kernel without it has no
/// system call of that number: the smallest it knows is `seL4_SysNBRecv`, -8.
pub(crate) const SYS_DEBUG_PUT_CHAR: i64 = -9;

/// Message registers a worker can pass without an IPC buffer.
pub(crate) const FAST_REGS: usize = 4;

/// What comes back from a `call`: the message information word and the four message registers.
#[derive(Clone, Copy)]
pub(crate) struct Answer {
    pub(crate) info: u64,
    pub(crate) mr: [u64; FAST_REGS],
}

impl Answer {
    /// The label of the answer: the caller's own protocol value, or a kernel error code when the kernel answered.
    pub(crate) fn label(self) -> u64 {
        self.info >> 12
    }
}

/// `seL4_Call` on the capability at `cptr` with `label` and four message words, all in registers.
pub(crate) fn call(cptr: u64, label: u64, mr: [u64; FAST_REGS]) -> Answer {
    let mut info = (label << 12) | FAST_REGS as u64;
    let [mut m0, mut m1, mut m2, mut m3] = mr;
    // SAFETY: `svc #0` enters the kernel, which reads x0 to x5 and x7 and writes x0 to x5 (and may change x6 and x7); every one of
    // those is declared as an operand, so the compiler keeps nothing live in them. The kernel touches no memory of
    // this thread for a register-only message (the length is 4, so no IPC buffer word is read, and this thread has no
    // IPC buffer for the kernel to write to), and it does not use this thread's stack.
    unsafe {
        asm!(
            "svc #0",
            inout("x0") cptr => _,
            inout("x1") info,
            inout("x2") m0,
            inout("x3") m1,
            inout("x4") m2,
            inout("x5") m3,
            lateout("x6") _,
            inout("x7") SYS_CALL => _,
            options(nostack),
        );
    }
    Answer { info, mr: [m0, m1, m2, m3] }
}

/// Issues the system call number `SYS_DEBUG_PUT_CHAR` with `byte` as its argument. On a kernel with printing this is
/// `seL4_DebugPutChar` and it returns; on a kernel without printing the number is unknown, the kernel raises an
/// unknown-syscall fault for this thread, and the call does not return unless the fault handler resumes the thread.
pub(crate) fn debug_put_char_probe(byte: u8) {
    // SAFETY: as `call`: the kernel reads x0 and x7, and every register it may write is declared. On a printing kernel
    // the call returns with nothing else changed. On a kernel without printing the thread is stopped with an
    // unknown-syscall fault and execution continues here only if the fault's handler answers it; a handler could then
    // also rewrite this thread's stack pointer, link register and program counter, which this block does not declare.
    // The only handler is the root task of this test, which never answers that fault, so the thread stays stopped.
    unsafe {
        asm!(
            "svc #0",
            inout("x0") u64::from(byte) => _,
            lateout("x1") _,
            lateout("x2") _,
            lateout("x3") _,
            lateout("x4") _,
            lateout("x5") _,
            lateout("x6") _,
            inout("x7") SYS_DEBUG_PUT_CHAR => _,
            options(nostack),
        );
    }
}
