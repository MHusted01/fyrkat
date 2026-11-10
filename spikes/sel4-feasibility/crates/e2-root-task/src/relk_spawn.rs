//
// SPDX-License-Identifier: BSD-2-Clause
//
// Release-kernel execution test: creating worker threads of the root task, and the slots their capabilities go in.
//

use crate::relk_workers::Entry;
use crate::slots::SlotWindow;
use crate::{Fail, ObjectAllocator};

/// Added to a worker's number to make the badge of its fault capability, so that a fault message and a report of
/// the same worker arrive with different badges.
pub(crate) const FAULT_BADGE: u64 = 0x100;
const STACK_BYTES: usize = 16 * 1024;

/// A worker thread that has been started.
#[derive(Clone, Copy)]
pub(crate) struct Worker {
    pub(crate) tcb: sel4::cap::Tcb,
    /// Badge of the capability the worker reports through.
    pub(crate) badge: u64,
}

pub(crate) struct Spawner {
    ep: sel4::cap::Endpoint,
    slots: SlotWindow,
    next_badge: u64,
}

/// What a worker is started with, besides its entry point.
pub(crate) struct Start {
    pub(crate) entry: Entry,
    /// Second and third arguments; the first is always the address of the worker's report capability.
    pub(crate) args: [u64; 2],
    pub(crate) priority: u64,
    /// The core to run on, for kernels with more than one node. `None` leaves the kernel's default.
    pub(crate) core: Option<u64>,
}

impl Spawner {
    /// `ep` is the endpoint the root task receives reports and faults on.
    pub(crate) fn new(bootinfo: &sel4::BootInfo, ep: sel4::cap::Endpoint) -> Result<Self, Fail> {
        Ok(Self { ep, slots: SlotWindow::new(bootinfo)?, next_badge: 1 })
    }

    /// The next free slot of the window.
    pub(crate) fn slot(&mut self) -> Result<usize, Fail> {
        self.slots.take()
    }

    /// A badged capability to the report endpoint with send and grant-reply rights (enough to `Call`), in a new slot.
    pub(crate) fn badged(&mut self, badge: u64) -> Result<sel4::CPtr, Fail> {
        let slot = self.slot()?;
        let cnode = sel4::init_thread::slot::CNODE.cap();
        let dst = sel4::init_thread::Slot::<sel4::cap_type::Endpoint>::from_index(slot);
        let rights = sel4::CapRightsBuilder::none().write(true).grant_reply(true).build();
        cnode.absolute_cptr(dst.cptr()).mint(&cnode.absolute_cptr(self.ep.cptr()), rights, badge)?;
        Ok(dst.cptr())
    }

    /// Creates a thread in the root task's address space and capability space and starts it at `start.entry` with
    /// its report capability as the first argument. Faults of the thread arrive on the endpoint with the badge
    /// `FAULT_BADGE + worker.badge`.
    pub(crate) fn spawn(&mut self, allocator: &mut ObjectAllocator, start: &Start) -> Result<Worker, Fail> {
        let badge = self.next_badge;
        self.next_badge += 1;
        let report = self.badged(badge)?;
        let fault = self.badged(FAULT_BADGE + badge)?;
        let tcb = allocator.allocate_fixed_sized::<sel4::cap_type::Tcb>()?;
        // No IPC buffer: the buffer address is 0, so the kernel ignores the frame capability, which only has to be a
        // capability the kernel can look up.
        tcb.tcb_configure(
            fault,
            sel4::init_thread::slot::CNODE.cap(),
            sel4::CNodeCapData::new(0, 0),
            sel4::init_thread::slot::VSPACE.cap(),
            0,
            sel4::init_thread::slot::IPC_BUFFER.cap(),
        )?;
        tcb.tcb_set_sched_params(sel4::init_thread::slot::TCB.cap(), 0, start.priority)?;
        set_core(tcb, start.core)?;

        let stack: &'static mut [u8] = alloc::vec![0u8; STACK_BYTES].leak();
        let top = (stack.as_mut_ptr() as usize + stack.len()) & !0xf;
        let mut ctx = sel4::UserContext::default();
        *ctx.pc_mut() = start.entry as usize as u64;
        *ctx.sp_mut() = top as u64;
        *ctx.c_param_mut(0) = report.bits();
        *ctx.c_param_mut(1) = start.args[0];
        *ctx.c_param_mut(2) = start.args[1];
        tcb.tcb_write_all_registers(true, &mut ctx)?;
        Ok(Worker { tcb, badge })
    }
}

sel4::sel4_cfg_if! {
    if #[sel4_cfg(not(MAX_NUM_NODES = "1"))] {
        /// Whether the kernel this task was built for has more than one node.
        pub(crate) const SMP: bool = true;

        pub(crate) fn set_core(tcb: sel4::cap::Tcb, core: Option<u64>) -> Result<(), Fail> {
            match core {
                Some(core) => Ok(tcb.tcb_set_affinity(core)?),
                None => Ok(()),
            }
        }
    } else {
        pub(crate) const SMP: bool = false;

        pub(crate) fn set_core(_tcb: sel4::cap::Tcb, core: Option<u64>) -> Result<(), Fail> {
            // A single-node kernel has no `seL4_TCB_SetAffinity`; asking for a core there is a mistake of the caller.
            match core {
                Some(_) => Err(Fail::Check("a core was requested on a single-node kernel")),
                None => Ok(()),
            }
        }
    }
}
