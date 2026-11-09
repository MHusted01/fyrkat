//
// SPDX-License-Identifier: BSD-2-Clause
//

//! E2 task A. Calls the server through its badged endpoint capability, then makes two invalid invocations and
//! two attempts to exceed its authority (badge forgery; a read of the server's memory, which ends in a VM fault
//! that the root task receives). Each must be refused or return the expected error.

#![no_std]
#![no_main]

use core::ptr;

use e2_task::abi::{
    CLIENT_BADGE, CNODE_BITS, SECRET_ADDR, SEL4_ILLEGAL_OPERATION, SEL4_INVALID_CAPABILITY,
    SLOT_CNODE, SLOT_EMPTY, SLOT_ENDPOINT, SLOT_MINT_DEST,
};

#[path = "../runtime.rs"]
mod runtime;

fn main() -> ! {
    if let Err(what) = run() {
        sel4::debug_println!("E2_FAIL client: {}", what);
    }
    // Nothing below this line may be reached on success: `run` ends in a fault. Stay out of the way.
    loop {
        sel4::r#yield();
    }
}

fn run() -> Result<(), &'static str> {
    let ep = sel4::cap::Endpoint::from_bits(SLOT_ENDPOINT);

    // 1. A legitimate call is served, and the server saw the badge the kernel attached to this capability.
    let reply = ep.call_with_mrs(sel4::MessageInfo::new(0, 0, 0, 1), [41, 0, 0, 0]);
    if reply.msg[0] != 42 || reply.msg[1] != 1 || reply.msg[2] != CLIENT_BADGE {
        return Err("first call returned an unexpected reply");
    }
    sel4::debug_println!("E2_CLIENT call ok reply={} served={} badge={:#x}", reply.msg[0], reply.msg[1], reply.msg[2]);

    // 2. Invoking an empty slot is refused with InvalidCapability.
    let refused = sel4::cap::Endpoint::from_bits(SLOT_EMPTY).call(sel4::MessageInfo::new(0, 0, 0, 0));
    if refused.label() != SEL4_INVALID_CAPABILITY {
        return Err("empty slot was not refused with InvalidCapability");
    }
    sel4::debug_println!("E2_CLIENT empty-slot refused label={}", refused.label());

    // 3. Invoking a capability of the wrong type (a CNode used as if it were an endpoint) is refused.
    let refused = sel4::cap::Endpoint::from_bits(SLOT_CNODE).call(sel4::MessageInfo::new(0, 0, 0, 0));
    if refused.label() != SEL4_ILLEGAL_OPERATION {
        return Err("wrong-type invocation was not refused with IllegalOperation");
    }
    sel4::debug_println!("E2_CLIENT wrong-type refused label={}", refused.label());

    // 4. Forging a different badge by minting from the badged endpoint capability is refused.
    let cnode = sel4::cap::CNode::from_bits(SLOT_CNODE);
    let forged = cnode.absolute_cptr_from_bits_with_depth(SLOT_MINT_DEST, CNODE_BITS).mint(
        &cnode.absolute_cptr_from_bits_with_depth(SLOT_ENDPOINT, CNODE_BITS),
        sel4::CapRights::write_only(),
        CLIENT_BADGE + 1,
    );
    if forged != Err(sel4::Error::IllegalOperation) {
        return Err("badge forgery was not refused with IllegalOperation");
    }
    sel4::debug_println!("E2_CLIENT badge-forge refused");

    // None of the three refused attempts reached the server: its served-count is still one before this call.
    let reply = ep.call_with_mrs(sel4::MessageInfo::new(0, 0, 0, 1), [100, 0, 0, 0]);
    if reply.msg[0] != 101 || reply.msg[1] != 2 {
        return Err("second call shows the server received something else in between");
    }
    sel4::debug_println!("E2_CLIENT second call ok served={}", reply.msg[1]);

    // 5. The server's secret is not mapped here: this read must fault, and the fault goes to the root task.
    sel4::debug_println!("E2_CLIENT reading server memory");
    // SAFETY: intentionally invalid. SECRET_ADDR is mapped in the server's address space and not in this one,
    // so the read raises a VM fault delivered to the root task instead of completing.
    let leaked = unsafe { ptr::read_volatile(SECRET_ADDR as *const u64) };
    sel4::debug_println!("E2_FAIL client read the server's memory: {:#x}", leaked);
    Err("read of the server's secret did not fault")
}
