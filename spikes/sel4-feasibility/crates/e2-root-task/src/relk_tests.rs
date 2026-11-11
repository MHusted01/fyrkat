//
// SPDX-License-Identifier: BSD-2-Clause
//
// Release-kernel execution test: the tests. Each starts workers (`relk_workers.rs`), receives what they report or
// how they fault, compares it with what the kernel's interface specifies, and prints the observation and a verdict.
//

use core::sync::atomic::Ordering;

use crate::relk_spawn::{FAULT_BADGE, SMP, Start, Worker};
use crate::relk_workers::{self as workers, L_DONE, L_GO, L_IPC, L_IPC_REPLY, L_PING, L_PONG, L_STEP};
use crate::{Ctx, Fail, MUTANT, uprint, uprintln};

/// Priority of every worker; the root task runs at the kernel's maximum, 255.
const WORKER_PRIORITY: u64 = 100;
/// An address nothing is mapped at: above the root task's image and the device window, far below the top of user space.
const UNMAPPED_ADDR: u64 = 0x6000_0abc;
/// Badge of the capability that the revocation test revokes the copy of.
const VICTIM_BADGE: u64 = 0x77;
/// `seL4_InvalidCapability`: what the kernel answers a `Call` on an empty slot with (`libsel4/include/sel4/errors.h`).
const INVALID_CAPABILITY: u64 = sel4::Error::InvalidCapability as u64;
/// Data-fault status code classes of `ESR_EL1` (Arm ARM, ISS encoding for a data abort): bits [5:2] of the DFSC.
const DFSC_CLASS_TRANSLATION: u64 = 0b0001;
const DFSC_CLASS_PERMISSION: u64 = 0b0011;
/// How long the root task spins while it watches another core's counter.
const WATCH_LIMIT: u64 = 400_000_000;
const WATCH_TARGET: u64 = 1000;

/// What arrives on the endpoint: a worker's report, or the kernel's message about a worker's fault.
enum Event {
    Report { badge: u64, label: u64, mr: [u64; 4] },
    Fault { badge: u64, fault: sel4::Fault },
}

fn next_event(ctx: &Ctx) -> Event {
    let (info, badge) = ctx.ep.recv(());
    if badge & FAULT_BADGE != 0 {
        let fault = sel4::with_ipc_buffer(|ib| sel4::Fault::new(ib, &info));
        Event::Fault { badge: badge & !FAULT_BADGE, fault }
    } else {
        let mr = sel4::with_ipc_buffer(|ib| {
            let regs = ib.msg_regs();
            [regs[0], regs[1], regs[2], regs[3]]
        });
        Event::Report { badge, label: info.label(), mr }
    }
}

/// Answers the worker whose `Call` was received last.
fn answer(label: u64, word: u64) {
    sel4::with_ipc_buffer_mut(|ib| {
        ib.msg_regs_mut()[0] = word;
        sel4::reply(ib, sel4::MessageInfoBuilder::default().label(label).length(1).build());
    });
}

fn describe(event: &Event) {
    match event {
        Event::Report { badge, label, mr } => uprintln!("RELK   got report badge={:#x} label={:#x} mr={:x?}", badge, label, mr),
        Event::Fault { badge, fault } => uprintln!("RELK   got fault from worker {:#x}: {:x?}", badge, fault),
    }
}

fn spawn(ctx: &mut Ctx, entry: workers::Entry, args: [u64; 2], core: Option<u64>) -> Result<Worker, Fail> {
    ctx.spawner.spawn(&mut ctx.allocator, &Start { entry, args, priority: WORKER_PRIORITY, core })
}

pub(crate) fn run_all(ctx: &mut Ctx) -> Result<(), Fail> {
    let ok = notification(ctx)?;
    ctx.verdict("notification-badge", ok);
    let ok = ipc(ctx)?;
    ctx.verdict("ipc-call-reply", ok);
    let ok = vm_fault(ctx)?;
    ctx.verdict("vm-fault-delivery", ok);
    let ok = debug_syscall(ctx)?;
    ctx.verdict("debug-syscall", ok);
    let ok = revoke(ctx)?;
    ctx.verdict("revoke-badged-copy", ok);
    let ok = page_permissions(ctx)?;
    ctx.verdict("page-permission-and-unmap", ok);
    let ok = preemption(ctx)?;
    ctx.verdict("timer-preemption", ok);
    if SMP {
        let ok = other_cores(ctx)?;
        ctx.verdict("smp-other-cores", ok);
    } else {
        uprintln!("RELK smp-other-cores: not applicable, the kernel has one node");
    }
    Ok(())
}

/// Retype, mint with a badge, signal through the badged capability, wait on the unbadged one.
fn notification(ctx: &mut Ctx) -> Result<bool, Fail> {
    const BADGE: u64 = 0x1337;
    let unbadged = ctx.allocator.allocate_fixed_sized::<sel4::cap_type::Notification>()?;
    let slot = sel4::init_thread::Slot::<sel4::cap_type::Notification>::from_index(ctx.spawner.slot()?);
    let cnode = sel4::init_thread::slot::CNODE.cap();
    cnode.absolute_cptr(slot.cptr()).mint(&cnode.absolute_cptr(unbadged.cptr()), sel4::CapRights::write_only(), BADGE)?;
    slot.cap().signal();
    let (_, observed) = unbadged.wait();
    uprintln!("RELK notification: signalled through badge {:#x}, wait returned badge {:#x}", BADGE, observed);
    Ok(observed == BADGE)
}

/// A worker calls with two words; the root task checks the badge and the words, answers, and the worker confirms.
fn ipc(ctx: &mut Ctx) -> Result<bool, Fail> {
    let (x, y) = (0x1111_2222_3333_4444u64, 0x0f0f_f0f0_55aa_aa55u64);
    let worker = spawn(ctx, workers::ipc_worker, [x, y], None)?;
    let first = next_event(ctx);
    describe(&first);
    let delivered = matches!(first, Event::Report { badge, label: L_IPC, mr } if badge == worker.badge && mr[0] == x && mr[1] == y);
    if !delivered {
        return Ok(false);
    }
    answer(L_IPC_REPLY, workers::mix(x, y));
    let second = next_event(ctx);
    describe(&second);
    Ok(matches!(second, Event::Report { badge, label: L_DONE, mr } if badge == worker.badge && mr[0] == 1 && mr[1] == workers::mix(x, y)))
}

/// A worker reads an unmapped address; the kernel must deliver a VM fault naming that address.
fn vm_fault(ctx: &mut Ctx) -> Result<bool, Fail> {
    let worker = spawn(ctx, workers::read_fault_worker, [UNMAPPED_ADDR, 0], None)?;
    let event = next_event(ctx);
    describe(&event);
    Ok(matches!(event, Event::Fault { badge, fault: sel4::Fault::VmFault(ref vm) }
        if badge == worker.badge && vm.addr() == UNMAPPED_ADDR && !vm.is_prefetch() && dfsc_class(vm.fsr()) == DFSC_CLASS_TRANSLATION))
}

fn dfsc_class(fsr: u64) -> u64 {
    (fsr >> 2) & 0xf
}

fn is_write(fsr: u64) -> bool {
    (fsr >> 6) & 1 == 1
}

/// A worker issues the system-call number of `seL4_DebugPutChar`. A kernel built with printing prints the byte and
/// returns; a kernel built without it does not know the number and raises an unknown-syscall fault. The expectation
/// is the configuration this image was built against, so the test also fails if image and kernel disagree.
fn debug_syscall(ctx: &mut Ctx) -> Result<bool, Fail> {
    let expect_accepted = sel4::sel4_cfg_bool!(PRINTING);
    uprint!("RELK debug-syscall: what the kernel prints for the probe byte is between the brackets: [");
    let worker = spawn(ctx, workers::debug_syscall_worker, [u64::from(b'#'), 0], None)?;
    let event = next_event(ctx);
    uprintln!("]");
    describe(&event);
    let accepted = match event {
        Event::Report { badge, label: L_DONE, mr } if badge == worker.badge && mr[0] == 1 => Some(true),
        Event::Fault { badge, fault: sel4::Fault::UnknownSyscall(ref unknown) }
            if badge == worker.badge && unknown.syscall() == crate::rawsys::SYS_DEBUG_PUT_CHAR as u64 =>
        {
            Some(false)
        }
        _ => None,
    };
    uprintln!("RELK debug-syscall: kernel_accepts_debug_putchar={:?} expected_from_build_configuration={}", accepted, expect_accepted);
    Ok(accepted == Some(expect_accepted))
}

/// A badged capability A to the endpoint, a copy S of it (A's child in the derivation tree), a worker that calls
/// through S. After the first call the root task revokes A, which must delete S and keep A. The second call must then
/// be answered by the kernel with `seL4_InvalidCapability` and must not reach the root task.
fn revoke(ctx: &mut Ctx) -> Result<bool, Fail> {
    let cnode = sel4::init_thread::slot::CNODE.cap();
    let parent = ctx.spawner.badged(VICTIM_BADGE)?;
    let child = sel4::init_thread::Slot::<sel4::cap_type::Endpoint>::from_index(ctx.spawner.slot()?);
    cnode.absolute_cptr(child.cptr()).copy(&cnode.absolute_cptr(parent), sel4::CapRights::all())?;
    let worker = spawn(ctx, workers::revoke_worker, [child.cptr().bits(), 0], None)?;

    let first = next_event(ctx);
    describe(&first);
    if !matches!(first, Event::Report { badge: VICTIM_BADGE, label: L_PING, mr } if mr[0] == 1) {
        return Ok(false);
    }
    answer(L_PONG, 0);
    let step = next_event(ctx);
    describe(&step);
    if !matches!(step, Event::Report { badge, label: L_STEP, mr } if badge == worker.badge && mr[0] == L_PONG) {
        return Ok(false);
    }
    if MUTANT == Some("skip-revoke") {
        uprintln!("RELK revoke: MUTANT skip-revoke, the revocation is not made");
    } else {
        cnode.absolute_cptr(parent).revoke()?;
        uprintln!("RELK revoke: revoked the badged parent capability");
    }
    answer(L_GO, 0);

    let mut after = next_event(ctx);
    describe(&after);
    let reached_root = matches!(after, Event::Report { badge: VICTIM_BADGE, .. });
    if reached_root {
        // The call through the copy still arrived: answer it so that the worker can make its last report.
        answer(L_PONG, 0);
        after = next_event(ctx);
        describe(&after);
    }
    let refused = matches!(after, Event::Report { badge, label: L_DONE, mr }
        if badge == worker.badge && mr[0] == L_PONG && mr[1] == INVALID_CAPABILITY);
    // The parent must have survived its own revocation: a copy can still be made from it.
    let again = sel4::init_thread::Slot::<sel4::cap_type::Endpoint>::from_index(ctx.spawner.slot()?);
    let parent_kept = cnode.absolute_cptr(again.cptr()).copy(&cnode.absolute_cptr(parent), sel4::CapRights::all()).is_ok();
    uprintln!(
        "RELK revoke: second call reached the root task={} kernel answered InvalidCapability({})={} parent still usable={}",
        reached_root, INVALID_CAPABILITY, refused, parent_kept
    );
    Ok(!reached_root && refused && parent_kept)
}

/// One frame, mapped read-write for the root task and, through a copy of its capability, read-only at a second
/// address. A worker must be able to read the second address and must fault on writing it; after the copy is
/// unmapped a read of the same address must fault as a translation fault.
fn page_permissions(ctx: &mut Ctx) -> Result<bool, Fail> {
    const PATTERN: u32 = 0x5a;
    let cnode = sel4::init_thread::slot::CNODE.cap();
    let frame = ctx.allocator.allocate_fixed_sized::<sel4::cap_type::Granule>()?;
    // SAFETY: the frame was retyped from an untyped just now, so nothing refers to its memory, and its capability is
    // never revoked or deleted.
    let (writable, paddr) = unsafe { ctx.mapper.map_ram(frame) }?;
    writable.w32(0, PATTERN);
    let copy = sel4::init_thread::Slot::<sel4::cap_type::Granule>::from_index(ctx.spawner.slot()?);
    cnode.absolute_cptr(copy.cptr()).copy(&cnode.absolute_cptr(frame.cptr()), sel4::CapRights::all())?;
    let addr = if MUTANT == Some("rw-alias") {
        uprintln!("RELK page-permission: MUTANT rw-alias, the second view is mapped writable");
        // SAFETY: a second mapping of the frame above (a copy of its capability), reached only by the worker's single
        // load and store instructions; the returned page is used for its address only.
        unsafe { ctx.mapper.map_ram(copy.cap()) }?.0.addr() as u64
    } else {
        ctx.mapper.map_read_only(copy.cap())?.addr() as u64
    };
    uprintln!("RELK page-permission: frame at physical {:#x}, read-write at {:#x}, second view at {:#x}", paddr, writable.addr(), addr);

    let worker = spawn(ctx, workers::write_fault_worker, [addr, 0], None)?;
    let read = next_event(ctx);
    describe(&read);
    if !matches!(read, Event::Report { badge, label: L_STEP, mr } if badge == worker.badge && mr[0] == u64::from(PATTERN)) {
        return Ok(false);
    }
    answer(L_GO, 0);
    let write = next_event(ctx);
    describe(&write);
    let write_refused = matches!(write, Event::Fault { badge, fault: sel4::Fault::VmFault(ref vm) }
        if badge == worker.badge && vm.addr() == addr && is_write(vm.fsr()) && dfsc_class(vm.fsr()) == DFSC_CLASS_PERMISSION);
    let unchanged = writable.r32(0) == PATTERN;
    uprintln!("RELK page-permission: write through the second view refused={} frame still holds the pattern={}", write_refused, unchanged);

    copy.cap().frame_unmap()?;
    let reader = spawn(ctx, workers::read_fault_worker, [addr, 0], None)?;
    let after_unmap = next_event(ctx);
    describe(&after_unmap);
    let unmapped = matches!(after_unmap, Event::Fault { badge, fault: sel4::Fault::VmFault(ref vm) }
        if badge == reader.badge && vm.addr() == addr && dfsc_class(vm.fsr()) == DFSC_CLASS_TRANSLATION);
    uprintln!("RELK page-permission: read after unmapping the second view faults={}", unmapped);
    Ok(write_refused && unchanged && unmapped)
}

/// Two workers of equal priority on the root task's core, each of which stops only when it has seen the other make
/// progress. Neither blocks, so both finishing shows that the kernel's timer interrupt preempted them.
fn preemption(ctx: &mut Ctx) -> Result<bool, Fail> {
    let core = SMP.then_some(0);
    workers::PAIR[0].store(0, Ordering::Relaxed);
    workers::PAIR[1].store(0, Ordering::Relaxed);
    let a = spawn(ctx, workers::pair_worker, [0, 0], core)?;
    let b = spawn(ctx, workers::pair_worker, [1, 0], core)?;
    let mut ok = true;
    let mut seen = [false, false];
    for _ in 0..2 {
        let event = next_event(ctx);
        describe(&event);
        match event {
            Event::Report { badge, label: L_DONE, mr } if (badge == a.badge || badge == b.badge) && mr[0] < workers::SPIN_LIMIT && mr[1] >= workers::PAIR_TARGET => {
                seen[usize::from(badge == b.badge)] = true;
            }
            _ => ok = false,
        }
    }
    Ok(ok && seen == [true, true])
}

/// On a kernel with several nodes: a worker of lower priority than the root task, placed on another core, must make
/// progress while the root task spins without entering the kernel; the same worker placed on the root task's own core
/// must make none; and a core number the kernel does not have must be refused.
fn other_cores(ctx: &mut Ctx) -> Result<bool, Fail> {
    let nodes = ctx.bootinfo.inner().numNodes as usize;
    if nodes < 2 || nodes > workers::MAX_CORES {
        uprintln!("RELK smp: the kernel reports {} nodes; the test needs 2 to {}", nodes, workers::MAX_CORES);
        return Ok(false);
    }
    let mut ok = true;
    for core in 1..nodes {
        let worker = spawn(ctx, workers::core_worker, [core as u64, 0], Some(core as u64))?;
        let spins = watch(core);
        workers::CORE_STOP[core].store(true, Ordering::Relaxed);
        let event = next_event(ctx);
        let reported = matches!(event, Event::Report { badge, label: L_DONE, .. } if badge == worker.badge);
        uprintln!("RELK smp: core {}: worker progress seen after {:?} spins of the root task (None: never), final report received={}", core, spins, reported);
        describe(&event);
        ok &= spins.is_some() && reported;
    }

    // Control: the same worker on the root task's own core cannot run while the root task (priority 255) spins.
    let control = spawn(ctx, workers::core_worker, [0, 0], Some(0))?;
    let spins = watch(0);
    control.tcb.tcb_suspend()?;
    let count = workers::CORE_COUNT[0].load(Ordering::Relaxed);
    uprintln!("RELK smp: control on core 0: progress seen={:?} (expected None), counter after suspending it={}", spins, count);
    ok &= spins.is_none() && count == 0;

    let tcb = ctx.allocator.allocate_fixed_sized::<sel4::cap_type::Tcb>()?;
    let refused = crate::relk_spawn::set_core(tcb, Some(nodes as u64));
    uprintln!("RELK smp: placing a thread on core {} (one past the last): {:?}", nodes, refused);
    ok &= matches!(refused, Err(Fail::Sel4(_)));
    Ok(ok)
}

/// Spins, without entering the kernel, until the worker of `core` has counted to `WATCH_TARGET`. Returns how many
/// spins that took, or `None` if it did not happen within `WATCH_LIMIT`.
fn watch(core: usize) -> Option<u64> {
    for spins in 0..WATCH_LIMIT {
        if workers::CORE_COUNT[core].load(Ordering::Relaxed) >= WATCH_TARGET {
            return Some(spins);
        }
        core::hint::spin_loop();
    }
    None
}
