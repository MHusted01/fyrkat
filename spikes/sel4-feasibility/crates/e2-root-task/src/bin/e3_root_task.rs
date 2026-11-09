//
// Copyright 2024, Colias Group, LLC (adapted from seL4/rust-sel4 spawn-task, tag v6.0.0)
//
// SPDX-License-Identifier: BSD-2-Clause
//

//! E3 root task: capability revocation. It builds two identical tasks (ids 1 and 2), gives each a badged mint of its
//! endpoint capability `P` (`SLOT_DERIVED`), a copy of that mint (`SLOT_COPY`) and a mint of an unrelated endpoint `Q`
//! (`SLOT_CONTROL`), shows that all three are served, calls `seL4_CNode_Revoke` on `P`, and shows that the first two
//! are now refused (and gone from the tasks' CNodes) while `P`, `Q` and the control capabilities still work.
//!
//! Neither task holds a capability to a CNode, so only the root task can empty a slot. The root task never sees
//! a task fault: the tasks have no fault handler. `E3_MUTANT` (a compile-time variable, unset for the evidence image)
//! replaces the revoke step, to show that each check can fail: a no-op, a revoke of the wrong capability, a revoke of
//! too much, a removal from one task only; and, with two of the root task's probes left out or with the root task
//! answering the call, the detectors that sit behind the probes.

#![no_std]
#![no_main]
#![allow(clippy::useless_conversion)]

extern crate alloc;

use alloc::vec::Vec;

use e2_task::e3_abi::{
    BADGE_CONTROL, BADGE_DERIVED, BADGE_FRESH, CNODE_BITS, CODE_CONTROL_AFTER, CODE_CONTROL_BEFORE,
    CODE_COPY_BEFORE, CODE_DERIVED_AFTER, CODE_DERIVED_BEFORE, CODE_FRESH_AFTER, EVENT_MASK, SLOT_CONTROL, SLOT_COPY, SLOT_DERIVED,
    SLOT_EMPTY, SLOT_EVENT, SLOT_FRESH, SLOT_GO, event_badge,
};
use object::File;
use sel4_root_task::{Never, root_task};

#[path = "../child_vspace.rs"]
#[allow(dead_code)]
mod child_vspace;
#[path = "../e3_spawn.rs"]
mod e3_spawn;
#[path = "../object_allocator.rs"]
mod object_allocator;

use child_vspace::create_child_vspace;
use e3_spawn::{Seed, init_free_page_addr, make_cnode, start};
use object_allocator::ObjectAllocator;

const TASK_ELF: &[u8] = include_bytes!(env!("E3_TASK_ELF"));
const MUTANT: Option<&str> = option_env!("E3_MUTANT");
const TASK_IDS: [u64; 2] = [1, 2];

/// Why the root task could not finish building or checking the system. Only ever printed, through `Debug`.
#[derive(Debug)]
#[allow(dead_code)]
pub(crate) enum Fail {
    Sel4(sel4::Error),
    OutOfSlots,
    NoUntyped,
    Elf,
    Layout,
    Check(&'static str),
}

impl From<sel4::Error> for Fail {
    fn from(e: sel4::Error) -> Self {
        Fail::Sel4(e)
    }
}

#[root_task(heap_size = 1024 * 64)]
fn main(bootinfo: &sel4::BootInfoPtr) -> sel4::Result<Never> {
    match run(bootinfo) {
        Ok(()) => sel4::debug_println!("E3_PASS"),
        Err(fail) => sel4::debug_println!("E3_FAIL root: {:?}", fail),
    }
    sel4::init_thread::suspend_self()
}

struct Task {
    id: u64,
    cnode: sel4::cap::CNode,
    go: sel4::cap::Notification,
}

struct System {
    root_cnode: sel4::cap::CNode,
    /// The root task's capability to the endpoint the tasks' derived capabilities come from (the ancestor).
    p: sel4::cap::Endpoint,
    /// An endpoint `P` has nothing to do with.
    q: sel4::cap::Endpoint,
    /// A free slot of the root task's CNode, used as the destination of probing copies (always deleted again).
    scratch: sel4::CPtr,
    tasks: Vec<Task>,
}

fn call_rights() -> sel4::CapRights {
    sel4::CapRightsBuilder::none().write(true).grant_reply(true).build()
}

fn run(bootinfo: &sel4::BootInfoPtr) -> Result<(), Fail> {
    sel4::debug_println!("E3_ROOT start");
    sel4::debug_println!("E3_ROOT mutant={}", MUTANT.unwrap_or("none"));
    let sys = build(bootinfo)?;
    sel4::debug_println!("E3_ROOT built: P, Q, 2 tasks with derived, copy and control capabilities");

    for task in &sys.tasks {
        for (slot, want) in [(SLOT_DERIVED, true), (SLOT_COPY, true), (SLOT_CONTROL, true)] {
            probe_task(&sys, task, "before", slot, want)?;
        }
        probe_task(&sys, task, "before", SLOT_EMPTY, false)?;
        probe_task(&sys, task, "before", SLOT_FRESH, false)?;
    }
    probe_root(&sys, "before", "P", sys.p.cptr())?;
    for task in &sys.tasks {
        task.go.signal();
        expect_call(sys.p, "P", task, BADGE_DERIVED, CODE_DERIVED_BEFORE)?;
        expect_call(sys.p, "P", task, BADGE_DERIVED, CODE_COPY_BEFORE)?;
        expect_call(sys.q, "Q", task, BADGE_CONTROL, CODE_CONTROL_BEFORE)?;
        expect_event(sys.p, task)?;
    }

    revoke(&sys)?;

    probe_root(&sys, "after", "P", sys.p.cptr())?;
    probe_root(&sys, "after", "Q", sys.q.cptr())?;
    for task in &sys.tasks {
        // The mutant that leaves these two probes out shows that the task's own calls detect a surviving capability
        // when the probes do not.
        if !matches!(MUTANT, Some("noop-revoke-blind-probes" | "serve-refused")) {
            probe_task(&sys, task, "after", SLOT_DERIVED, false)?;
            probe_task(&sys, task, "after", SLOT_COPY, false)?;
        }
        probe_task(&sys, task, "after", SLOT_EMPTY, false)?;
        probe_task(&sys, task, "after", SLOT_FRESH, false)?;
        probe_task(&sys, task, "after", SLOT_CONTROL, true)?;
        task.go.signal();
        if MUTANT == Some("serve-refused") {
            // A root task that answered a call which should have been refused: the task's own check must catch it.
            expect_call(sys.p, "P", task, BADGE_DERIVED, CODE_DERIVED_AFTER)?;
        }
        // The task's calls through the derived and copied slots and the never-populated slot are refused at once, so
        // the first thing to reach the root task is its event. A call that got through would arrive on `P` first.
        expect_event(sys.p, task)?;
        expect_call(sys.q, "Q", task, BADGE_CONTROL, CODE_CONTROL_AFTER)?;
        expect_event(sys.p, task)?;
    }

    let root_cnode = sys.root_cnode;
    for task in &sys.tasks {
        // `P` is still a capability to mint from, and what it mints works.
        task.cnode
            .absolute_cptr_from_bits_with_depth(SLOT_FRESH, CNODE_BITS)
            .mint(&root_cnode.absolute_cptr(sys.p.cptr()), call_rights(), BADGE_FRESH + task.id)?;
        probe_task(&sys, task, "fresh", SLOT_FRESH, true)?;
        task.go.signal();
        expect_call(sys.p, "P", task, BADGE_FRESH, CODE_FRESH_AFTER)?;
        expect_event(sys.p, task)?;
    }
    Ok(())
}

fn build(bootinfo: &sel4::BootInfoPtr) -> Result<System, Fail> {
    let mut allocator = ObjectAllocator::new(bootinfo)?;
    let free_page_addr = init_free_page_addr(bootinfo)?;
    let root_cnode = sel4::init_thread::slot::CNODE.cap();
    // The last free slot: the allocator hands slots out from the first one upwards.
    let scratch =
        sel4::init_thread::Slot::<sel4::cap_type::Unspecified>::from_index(bootinfo.empty().range().end - 1).cptr();

    let p = allocator.allocate_fixed_sized::<sel4::cap_type::Endpoint>()?;
    let q = allocator.allocate_fixed_sized::<sel4::cap_type::Endpoint>()?;
    // Task events arrive as signals on this notification, which wakes the root task wherever it is receiving.
    let events = allocator.allocate_fixed_sized::<sel4::cap_type::Notification>()?;
    sel4::init_thread::slot::TCB.cap().tcb_bind_notification(events)?;

    let image = File::parse(TASK_ELF).map_err(|_| Fail::Elf)?;
    let mut tasks = Vec::new();
    for id in TASK_IDS {
        let go = allocator.allocate_fixed_sized::<sel4::cap_type::Notification>()?;
        let child = create_child_vspace(
            &mut allocator,
            &image,
            sel4::init_thread::slot::VSPACE.cap(),
            free_page_addr,
            sel4::init_thread::slot::ASID_POOL.cap(),
        )?;
        let seeds = [
            Seed { slot: SLOT_DERIVED, src: p.cptr(), rights: call_rights(), badge: BADGE_DERIVED + id },
            Seed { slot: SLOT_CONTROL, src: q.cptr(), rights: call_rights(), badge: BADGE_CONTROL + id },
            Seed {
                slot: SLOT_GO,
                src: go.cptr(),
                rights: sel4::CapRightsBuilder::none().read(true).build(),
                badge: 0,
            },
            Seed { slot: SLOT_EVENT, src: events.cptr(), rights: sel4::CapRights::write_only(), badge: event_badge(id) },
        ];
        let cnode = make_cnode(&mut allocator, &seeds)?;
        // A copy of the minted capability, made by the root task, so that it is a descendant of it.
        cnode.absolute_cptr_from_bits_with_depth(SLOT_COPY, CNODE_BITS).copy(
            &cnode.absolute_cptr_from_bits_with_depth(SLOT_DERIVED, CNODE_BITS),
            call_rights(),
        )?;
        start(&mut allocator, &child, &image, cnode)?;
        tasks.push(Task { id, cnode, go });
    }
    Ok(System { root_cnode, p, q, scratch, tasks })
}

/// The one step under test: `seL4_CNode_Revoke` on the root task's capability `P`. A mutant replaces it; the log says which.
fn revoke(sys: &System) -> Result<(), Fail> {
    let root = sys.root_cnode;
    sel4::debug_println!("E3_ROOT revoke step");
    match MUTANT {
        None => {
            sel4::debug_println!("E3_ROOT revoke P");
            root.absolute_cptr(sys.p.cptr()).revoke()?;
        }
        Some("noop-revoke" | "noop-revoke-blind-probes" | "serve-refused") => {
            sel4::debug_println!("E3_ROOT mutant: no revoke");
        }
        Some("revoke-wrong-ancestor") => {
            sel4::debug_println!("E3_ROOT mutant: revoke Q, not P");
            root.absolute_cptr(sys.q.cptr()).revoke()?;
        }
        Some("revoke-too-much") => {
            sel4::debug_println!("E3_ROOT mutant: revoke P, then Q");
            root.absolute_cptr(sys.p.cptr()).revoke()?;
            root.absolute_cptr(sys.q.cptr()).revoke()?;
        }
        Some("revoke-task-1-only") => {
            sel4::debug_println!("E3_ROOT mutant: delete task 1's slots 1 and 2, no revoke");
            let cnode = sys.tasks[0].cnode;
            cnode.absolute_cptr_from_bits_with_depth(SLOT_DERIVED, CNODE_BITS).delete()?;
            cnode.absolute_cptr_from_bits_with_depth(SLOT_COPY, CNODE_BITS).delete()?;
        }
        Some(_) => return Err(Fail::Check("unknown mutant")),
    }
    sel4::debug_println!("E3_ROOT revoke returned");
    Ok(())
}

/// Tries to copy the capability in `slot` of the task's CNode into the root task's scratch slot, then deletes the
/// copy. `populated` says whether that is expected to succeed. A copy from an empty slot is refused by the kernel.
fn probe_task(sys: &System, task: &Task, phase: &str, slot: u64, populated: bool) -> Result<(), Fail> {
    let src = task.cnode.absolute_cptr_from_bits_with_depth(slot, CNODE_BITS);
    probe(sys, src, populated, |outcome| {
        sel4::debug_println!("E3_ROOT {}: task {} slot {} copy {}", phase, task.id, slot, outcome)
    })
}

fn probe_root(sys: &System, phase: &str, name: &str, cptr: sel4::CPtr) -> Result<(), Fail> {
    probe(sys, sys.root_cnode.absolute_cptr(cptr), true, |outcome| {
        sel4::debug_println!("E3_ROOT {}: {} in the root task's CNode copy {}", phase, name, outcome)
    })
}

fn probe(
    sys: &System,
    src: sel4::AbsoluteCPtr,
    populated: bool,
    say: impl Fn(&dyn core::fmt::Display),
) -> Result<(), Fail> {
    let dest = || sys.root_cnode.absolute_cptr(sys.scratch);
    match (dest().copy(&src, sel4::CapRights::all()), populated) {
        (Ok(()), true) => {
            dest().delete()?;
            say(&"ok");
            Ok(())
        }
        (Err(e), false) => {
            say(&format_args!("refused ({:?})", e));
            Ok(())
        }
        (Ok(()), false) => {
            dest().delete()?;
            say(&"ok, but the slot should be empty");
            Err(Fail::Check("a slot that should be empty is populated"))
        }
        (Err(e), true) => {
            say(&format_args!("refused ({:?}), but the slot should be populated", e));
            Err(Fail::Check("a slot that should be populated is empty"))
        }
    }
}

enum Incoming {
    Event(u64),
    Call { badge: u64, code: u64 },
}

fn next(ep: sel4::cap::Endpoint) -> Incoming {
    let received = ep.recv_with_mrs(());
    if received.badge & EVENT_MASK != 0 {
        Incoming::Event(received.badge)
    } else {
        Incoming::Call { badge: received.badge, code: received.msg[0] }
    }
}

/// Waits on `ep` for a call from `task` with the given badge base and code, and answers it with `code + 1` and the id.
fn expect_call(
    ep: sel4::cap::Endpoint,
    name: &str,
    task: &Task,
    badge_base: u64,
    code: u64,
) -> Result<(), Fail> {
    match next(ep) {
        Incoming::Call { badge, code: got } if badge == badge_base + task.id && got == code => {
            sel4::debug_println!("E3_ROOT recv on {}: task {} badge={:#x} code={:#x}", name, task.id, badge, got);
            sel4::with_ipc_buffer_mut(|ib| {
                let regs = ib.msg_regs_mut();
                regs[0] = code + 1;
                regs[1] = task.id;
                sel4::reply(ib, sel4::MessageInfo::new(0, 0, 0, 2));
            });
            Ok(())
        }
        Incoming::Call { badge, code: got } => {
            sel4::debug_println!("E3_ROOT unexpected call on {}: badge={:#x} code={:#x}", name, badge, got);
            Err(Fail::Check("an unexpected call arrived"))
        }
        Incoming::Event(badge) => {
            sel4::debug_println!("E3_ROOT unexpected event on {}: badge={:#x}", name, badge);
            Err(Fail::Check("an event arrived where a call was due"))
        }
    }
}

/// Waits on `ep` for the next event of `task`. Anything else, in particular a call, means the task's previous step
/// did not end as expected.
fn expect_event(ep: sel4::cap::Endpoint, task: &Task) -> Result<(), Fail> {
    match next(ep) {
        Incoming::Event(badge) if badge == event_badge(task.id) => {
            sel4::debug_println!("E3_ROOT event from task {}", task.id);
            Ok(())
        }
        Incoming::Event(badge) => {
            sel4::debug_println!("E3_ROOT event with badge {:#x}, wanted task {}", badge, task.id);
            Err(Fail::Check("an event from the wrong task"))
        }
        Incoming::Call { badge, code } => {
            sel4::debug_println!("E3_ROOT call reached the root task: badge={:#x} code={:#x}", badge, code);
            Err(Fail::Check("a call arrived where the task's event was due"))
        }
    }
}
