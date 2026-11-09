//
// SPDX-License-Identifier: BSD-2-Clause
//

//! E3 task (the root task starts two copies, ids 1 and 2, each with its own address space and CNode). It holds no
//! capability to its own CNode, so it cannot empty a slot itself. It uses the capabilities in its slots only when the
//! root task signals it:
//! - go 1: calls through the derived, copied and control endpoint capabilities; each must be served.
//! - go 2 (after the root task revoked): the derived and copied capabilities and an always-empty slot must be refused
//!   with a non-zero error label (the exact label is observed, not required); the control capability must be served.
//! - go 3: a capability minted after the revoke must be served.
//!
//! A call that the kernel refuses returns at once with the error as the reply label, and a served call returns the
//! root task's reply (label 0). Every step ends by signalling the root task, which is how it keeps pace.

#![no_std]
#![no_main]

use e2_task::e3_abi::{
    CODE_CONTROL_AFTER, CODE_CONTROL_BEFORE, CODE_COPY_AFTER, CODE_COPY_BEFORE, CODE_DERIVED_AFTER,
    CODE_DERIVED_BEFORE, CODE_EMPTY_AFTER, CODE_FRESH_AFTER, SLOT_CONTROL, SLOT_COPY, SLOT_DERIVED, SLOT_EMPTY,
    SLOT_EVENT, SLOT_FRESH, SLOT_GO,
};

#[path = "../runtime.rs"]
mod runtime;

fn main() -> ! {
    if let Err(what) = run() {
        sel4::debug_println!("E3_FAIL task: {}", what);
    }
    // Done, or failed: stay blocked on the go-signal for good.
    loop {
        wait_go();
    }
}

fn wait_go() {
    sel4::cap::Notification::from_bits(SLOT_GO).wait();
}

fn event() {
    sel4::cap::Notification::from_bits(SLOT_EVENT).signal();
}

/// Calls through `slot` with `code`; the call must be served by the root task. Returns the task id it reports.
fn served(slot: u64, code: u64) -> Result<u64, &'static str> {
    let reply = sel4::cap::Endpoint::from_bits(slot)
        .call_with_mrs(sel4::MessageInfo::new(0, 0, 0, 1), [code, 0, 0, 0]);
    if reply.info.label() != 0 || reply.msg[0] != code + 1 {
        return Err("a call that should be served was not");
    }
    Ok(reply.msg[1])
}

/// Calls through `slot` with `code`; the kernel must refuse it (non-zero error label). Returns that label.
fn refused(slot: u64, code: u64) -> Result<u64, &'static str> {
    let reply = sel4::cap::Endpoint::from_bits(slot)
        .call_with_mrs(sel4::MessageInfo::new(0, 0, 0, 1), [code, 0, 0, 0]);
    match reply.info.label() {
        0 => Err("a call that should be refused was served"),
        label => Ok(label),
    }
}

fn run() -> Result<(), &'static str> {
    wait_go();
    let id = served(SLOT_DERIVED, CODE_DERIVED_BEFORE)?;
    sel4::debug_println!("E3_TASK {} before: derived slot served", id);
    served(SLOT_COPY, CODE_COPY_BEFORE)?;
    sel4::debug_println!("E3_TASK {} before: copy slot served", id);
    served(SLOT_CONTROL, CODE_CONTROL_BEFORE)?;
    sel4::debug_println!("E3_TASK {} before: control slot served", id);
    event();

    wait_go();
    let label = refused(SLOT_DERIVED, CODE_DERIVED_AFTER)?;
    sel4::debug_println!("E3_TASK {} after: derived slot refused label={}", id, label);
    let label = refused(SLOT_COPY, CODE_COPY_AFTER)?;
    sel4::debug_println!("E3_TASK {} after: copy slot refused label={}", id, label);
    let label = refused(SLOT_EMPTY, CODE_EMPTY_AFTER)?;
    sel4::debug_println!("E3_TASK {} after: never-populated slot refused label={}", id, label);
    event();
    served(SLOT_CONTROL, CODE_CONTROL_AFTER)?;
    sel4::debug_println!("E3_TASK {} after: control slot served", id);
    event();

    wait_go();
    served(SLOT_FRESH, CODE_FRESH_AFTER)?;
    sel4::debug_println!("E3_TASK {} after: fresh slot served", id);
    event();
    Ok(())
}
