//
// SPDX-License-Identifier: BSD-2-Clause
//

//! K3 client and memory owner (results/K3.md). One program for the roles C1, C2 and M: what a task is able to do is decided
//! by the capabilities in its CNode, not by this code. It is **untrusted**: the steps below are what a hostile or buggy
//! driver can do with what it holds. It acts only when the conductor signals a step on its notification, asks the
//! conductor for the step's parameters, reports every observation by IPC (it has no console and uses no kernel debug
//! output), and says when the step is finished. It holds no capability to any other task's CNode or VSpace.

#![no_std]
#![no_main]

use sel4::CapTypeForObjectOfFixedSize;

#[path = "../k3_abi.rs"]
mod k3_abi;
#[path = "../k3_mmio.rs"]
mod k3_mmio;
#[path = "../k3_runtime.rs"]
mod runtime;

use k3_abi::*;
use k3_mmio::{PAGE, Page, barrier};

/// The `edu` device's registers and buffer (QEMU `docs/specs/edu.rst`).
const EDU_ID: usize = 0x00;
const EDU_DMA_SRC: usize = 0x80;
const EDU_DMA_DST: usize = 0x88;
const EDU_DMA_CNT: usize = 0x90;
const EDU_DMA_CMD: usize = 0x98;
const EDU_IDENTIFICATION: u32 = 0x0100_00ed;
const EDU_BUFFER: u64 = 0x4_0000;
const POLL_LIMIT: u32 = 40_000_000;

fn self_cnode() -> sel4::cap::CNode {
    sel4::cap::CNode::from_bits(SLOT_SELF_CNODE)
}

fn slot(index: u64) -> sel4::AbsoluteCPtr {
    self_cnode().absolute_cptr_from_bits_with_depth(index, CNODE_BITS)
}

fn vspace() -> sel4::cap::VSpace {
    sel4::cap::VSpace::from_bits(SLOT_SELF_VSPACE)
}

fn window_va(page: usize) -> usize {
    WINDOW_BASE + page * PAGE
}

/// The numeric value of a kernel error, for reports (0 is success).
fn code<T>(r: Result<T, sel4::Error>) -> u64 {
    match r {
        Ok(_) => 0,
        Err(e) => 1 + e as u64,
    }
}

fn report(tag: u64, a: u64, b: u64, c: u64) {
    sel4::cap::Endpoint::from_bits(SLOT_REPORT).call_with_mrs(sel4::MessageInfo::new(LBL_REPORT, 0, 0, 4), [tag, a, b, c]);
}

fn params(step: u64) -> [u64; 4] {
    sel4::cap::Endpoint::from_bits(SLOT_REPORT).call_with_mrs(sel4::MessageInfo::new(LBL_PARAMS, 0, 0, 1), [step, 0, 0, 0]).msg
}

fn done(step: u64) {
    sel4::cap::Endpoint::from_bits(SLOT_REPORT).call_with_mrs(sel4::MessageInfo::new(LBL_DONE, 0, 0, 1), [step, 0, 0, 0]);
}

struct Task {
    device: Option<Page>,
}

/// Page k of this task's buffers is window page 1 + k.
fn buffer(k: u64) -> Option<Page> {
    if k >= 64 {
        return None;
    }
    // SAFETY: the conductor asks this task to touch only pages the task mapped itself (STEP_ALLOC, STEP_M_FRAME,
    // STEP_MAP_RECEIVED) and whose capability has not been revoked since. That is not something this task can check; a
    // step that touches an unmapped page faults, and the fault is delivered to the conductor and ends the run (the
    // `no-owner-check` mutant's run ends that way, by design, and is accepted by the checker only for that mutant).
    Some(unsafe { Page::at(window_va(1 + k as usize)) })
}

impl Task {
    fn step(&mut self, step: u64, p: [u64; 4]) {
        match step {
            STEP_INIT => self.init(),
            STEP_ALLOC => self.alloc(p[0]),
            STEP_FILL => {
                if let Some(page) = buffer(p[0]) {
                    for j in 0..PATTERN_WORDS {
                        page.w32(j * 4, pattern(p[1], j));
                    }
                }
            }
            STEP_COUNT => {
                let (mut a, mut b, mut zeros) = (0, 0, 0);
                if let Some(page) = buffer(p[0]) {
                    for j in 0..PATTERN_WORDS {
                        let w = page.r32(j * 4);
                        a += u64::from(w == pattern(p[1], j));
                        b += u64::from(w == pattern(p[2], j));
                        zeros += u64::from(w == 0);
                    }
                }
                report(STEP_COUNT, a, b, zeros);
            }
            STEP_DEVOP => self.devop(p[0], p[1]),
            STEP_FREE => {
                let r = call_server(OP_FREE, [p[0], 0, 0, 0], None);
                report(STEP_FREE, r.0, 0, 0);
            }
            STEP_CSPACE_ATTACK => cspace_attack(),
            STEP_REMAP => self.remap(p[0]),
            STEP_DROP_FRAME => {
                let revoke = code(slot(SLOT_RECV_FIRST + p[0]).revoke());
                let delete = code(slot(SLOT_RECV_FIRST + p[0]).delete());
                report(STEP_DROP_FRAME, revoke, delete, 0);
            }
            STEP_TRY_ADMIN => try_admin(),
            STEP_M_FRAME => m_frame(p[0]),
            STEP_M_DONATE => m_donate(p[0], p[1]),
            STEP_MAP_RECEIVED => {
                let frame = sel4::cap::Granule::from_bits(p[1]);
                let rc = code(frame.frame_map(vspace(), window_va(1 + p[0] as usize), sel4::CapRights::read_write(), sel4::VmAttributes::default()));
                let pa = frame.frame_get_address().map_or(0, |a| a as u64);
                report(STEP_MAP_RECEIVED, rc, pa, 0);
            }
            STEP_ALLOC_MANY => alloc_many(p[0]),
            _ => {}
        }
    }

    fn init(&mut self) {
        let mapped = sel4::cap::Granule::from_bits(SLOT_DEVICE).frame_map(
            vspace(),
            window_va(WINDOW_BAR_PAGE),
            sel4::CapRights::read_write(),
            sel4::VmAttributes::NONE,
        );
        if mapped.is_ok() {
            // SAFETY: just mapped read-write; never unmapped by this program.
            let page = unsafe { Page::at(window_va(WINDOW_BAR_PAGE)) };
            self.device = Some(page);
            report(STEP_INIT, 0, u64::from(page.r32(EDU_ID)), u64::from(page.r32(EDU_ID) == EDU_IDENTIFICATION));
        } else {
            self.device = None;
            report(STEP_INIT, code(mapped), 0, 0);
        }
    }

    fn alloc(&mut self, k: u64) {
        let (rc, mrs) = call_server(OP_ALLOC, [0; 4], Some(SLOT_RECV_FIRST + k));
        let (mut maprc, mut pa) = (0, 0);
        if rc == RC_OK {
            let frame = sel4::cap::Granule::from_bits(SLOT_RECV_FIRST + k);
            maprc = code(frame.frame_map(vspace(), window_va(1 + k as usize), sel4::CapRights::read_write(), sel4::VmAttributes::default()));
            pa = frame.frame_get_address().map_or(0, |a| a as u64);
        }
        report(STEP_ALLOC, rc, mrs[0], mrs[1]);
        report(STEP_ALLOC, maprc, pa, 0);
    }

    fn devop(&mut self, kind: u64, addr: u64) {
        let Some(dev) = self.device else {
            report(STEP_DEVOP, 0, 0, 0);
            return;
        };
        let (src, dst, command) = match kind {
            0 => (addr, EDU_BUFFER, 1),
            1 => (EDU_BUFFER, addr, 3),
            2 => (EDU_BUFFER, addr, 0),
            _ => (EDU_BUFFER, addr, 3),
        };
        let wait = kind != 3;
        barrier();
        dev.w64(EDU_DMA_SRC, src);
        dev.w64(EDU_DMA_DST, dst);
        dev.w64(EDU_DMA_CNT, PATTERN_BYTES);
        let mut finished = true;
        if command != 0 {
            dev.w64(EDU_DMA_CMD, command);
            finished = !wait;
            for _ in 0..if wait { POLL_LIMIT } else { 0 } {
                if dev.r32(EDU_DMA_CMD) & 1 == 0 {
                    finished = true;
                    break;
                }
            }
            barrier();
        }
        report(STEP_DEVOP, u64::from(finished), 0, 0);
    }

    fn remap(&mut self, k: u64) {
        let frame = sel4::cap::Granule::from_bits(SLOT_RECV_FIRST + k);
        let unmap = code(frame.frame_unmap());
        let map = code(frame.frame_map(vspace(), window_va(1 + k as usize), sel4::CapRights::read_write(), sel4::VmAttributes::default()));
        report(STEP_REMAP, unmap, map, 0);
    }
}

/// One call to the server; capabilities it replies with land in `recv_slot`. Returns (result code, four words).
fn call_server(op: u64, mrs: [u64; 4], recv_slot: Option<u64>) -> (u64, [u64; 4]) {
    if let Some(s) = recv_slot {
        sel4::with_ipc_buffer_mut(|ib| ib.set_recv_slot(&slot(s)));
    }
    let r = sel4::cap::Endpoint::from_bits(SLOT_ES).call_with_mrs(sel4::MessageInfo::new(op, 0, 0, 4), mrs);
    (r.info.label(), r.msg)
}

/// Everything a task can do to its own CSpace, slot by slot. Reports: [slots a copy succeeded from, of which frames, slots an
/// Untyped_Retype succeeded on], then [slots a TCB suspend succeeded on, slots a Revoke failed on].
/// The destructive operations are applied to *copies* in scratch slots, except `Revoke`, which only removes descendants of the
/// slot's own capability (there are none that this task derived).
fn cspace_attack() {
    const SCRATCH: u64 = SLOT_LAST - 4;
    const SCRATCH2: u64 = SLOT_LAST - 3;
    let dst = self_cnode().absolute_cptr_for_self();
    let (mut populated, mut frames, mut untyped, mut tcb, mut revoked) = (0u64, 0u64, 0u64, 0u64, 0u64);
    for s in 1..SCRATCH {
        if slot(SCRATCH).copy(&slot(s), sel4::CapRights::all()).is_ok() {
            populated += 1;
            if !is_communication_slot(s) && sel4::cap::Granule::from_bits(SCRATCH).frame_get_address().is_ok() {
                frames += 1;
            }
            let _ = slot(SCRATCH).delete();
        }
        if is_communication_slot(s) {
            continue;
        }
        if sel4::cap::Untyped::from_bits(s)
            .untyped_retype(&sel4::cap_type::Granule::object_blueprint(), &dst, SCRATCH2 as usize, 1)
            .is_ok()
        {
            untyped += 1;
            let _ = slot(SCRATCH2).delete();
        }
        if sel4::cap::Tcb::from_bits(s).tcb_suspend().is_ok() {
            tcb += 1;
        }
    }
    // Revoke on every slot, communication slots included (a revoke is an operation on the CNode, not an invocation of the
    // capability, so it is safe on an endpoint): it only removes descendants of that slot's own capability, of which this
    // task has none. Every call must succeed; the number that failed is reported.
    for s in 1..SCRATCH {
        // M's untyped is left out: its frames are children of it, so a revoke of it would destroy M's own frames (the reclaim of
        // that untyped is tested separately, by the memory manager, in T3c). A client has no untyped.
        if s == SLOT_UNTYPED_A {
            continue;
        }
        if slot(s).revoke().is_err() {
            revoked += 1;
        }
    }
    report(STEP_CSPACE_ATTACK, populated, frames, untyped);
    report(STEP_CSPACE_ATTACK, tcb, revoked, 0);
}

fn try_admin() {
    let (ping, _) = call_server(OP_ADMIN_PING, [0; 4], None);
    let (events, _) = call_server(OP_ADMIN_EVENTS, [0; 4], None);
    // A badged endpoint capability cannot be given another badge: the kernel refuses.
    let mint = code(slot(SLOT_LAST - 2).mint(&slot(SLOT_ES), sel4::CapRights::all(), BADGE_ADMIN));
    let _ = slot(SLOT_LAST - 2).delete();
    report(STEP_TRY_ADMIN, ping, events, mint);
}

/// M: a frame made from its own untyped, mapped as its page k.
fn m_frame(k: u64) {
    let dst = self_cnode().absolute_cptr_for_self();
    let s = SLOT_OWN_FIRST + k;
    let rc = code(
        sel4::cap::Untyped::from_bits(SLOT_UNTYPED_A).untyped_retype(&sel4::cap_type::Granule::object_blueprint(), &dst, s as usize, 1),
    );
    let (mut maprc, mut pa) = (0, 0);
    if rc == 0 {
        let frame = sel4::cap::Granule::from_bits(s);
        maprc = code(frame.frame_map(vspace(), window_va(1 + k as usize), sel4::CapRights::read_write(), sel4::VmAttributes::default()));
        pa = frame.frame_get_address().map_or(0, |a| a as u64);
    }
    report(STEP_M_FRAME, rc, maprc, pa);
}

/// M: offers page k's frame to the server for `target`'s stream, with a call that carries the capability.
fn m_donate(k: u64, target: u64) {
    sel4::with_ipc_buffer_mut(|ib| {
        ib.caps_or_badges_mut()[0] = SLOT_OWN_FIRST + k;
    });
    let r = sel4::cap::Endpoint::from_bits(SLOT_ES).call_with_mrs(sel4::MessageInfo::new(OP_DONATE, 0, 1, 1), [target, 0, 0, 0]);
    report(STEP_M_DONATE, r.info.label(), r.msg[0], 0);
}

/// Asks for `n` pages in a row without mapping them. Reports [pages obtained, last result code, bitmask of handles].
fn alloc_many(n: u64) {
    let (mut got, mut last, mut handles) = (0u64, RC_OK, 0u64);
    // Receive slots 8 to 15, so that the slots of the pages the task holds (0 to 7) are not touched.
    for i in 0..n.min(RECV_SLOTS / 2) {
        let (rc, mrs) = call_server(OP_ALLOC, [0; 4], Some(SLOT_RECV_FIRST + RECV_SLOTS / 2 + i));
        last = rc;
        if rc != RC_OK {
            break;
        }
        got += 1;
        handles |= 1 << mrs[1];
    }
    report(STEP_ALLOC_MANY, got, last, handles);
}

fn main() -> ! {
    let mut task = Task { device: None };
    loop {
        let (_, step) = sel4::cap::Notification::from_bits(SLOT_GO).wait();
        let p = params(step);
        task.step(step, p);
        done(step);
    }
}
