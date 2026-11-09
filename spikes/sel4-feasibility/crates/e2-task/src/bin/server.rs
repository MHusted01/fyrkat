//
// SPDX-License-Identifier: BSD-2-Clause
//

//! E2 task B. Owns a secret in memory only it maps, receives calls on the shared endpoint and replies with
//! the request plus one, how many requests it has served, and the badge the kernel attached.

#![no_std]
#![no_main]

use core::ptr;

use e2_task::abi::{SECRET_ADDR, SECRET_VALUE, SLOT_ENDPOINT};

#[path = "../runtime.rs"]
mod runtime;

fn main() -> ! {
    // SAFETY: the root task mapped one writable granule at SECRET_ADDR in this task's address space.
    unsafe { ptr::write_volatile(SECRET_ADDR as *mut u64, SECRET_VALUE) };
    // Positive control for the client's later fault: the secret really is mapped and readable here.
    // SAFETY: same mapping as above.
    let readback = unsafe { ptr::read_volatile(SECRET_ADDR as *const u64) };
    if readback != SECRET_VALUE {
        sel4::debug_println!("E2_FAIL server: secret readback {:#x}", readback);
    }
    sel4::debug_println!("E2_SERVER secret mapped and readable");

    let ep = sel4::cap::Endpoint::from_bits(SLOT_ENDPOINT);
    let mut served: u64 = 0;
    sel4::debug_println!("E2_SERVER ready");
    let (_, mut badge) = ep.recv(());
    loop {
        served += 1;
        let request = sel4::with_ipc_buffer(|ib| ib.msg_regs()[0]);
        sel4::debug_println!("E2_SERVER got request={} badge={:#x} served={}", request, badge, served);
        sel4::with_ipc_buffer_mut(|ib| {
            let regs = ib.msg_regs_mut();
            regs[0] = request + 1;
            regs[1] = served;
            regs[2] = badge;
        });
        (_, badge) = ep.reply_recv(sel4::MessageInfo::new(0, 0, 0, 3), ());
    }
}
