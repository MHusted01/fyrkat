//
// SPDX-License-Identifier: BSD-2-Clause
//
// K3: the conductor. The root task signals one task at a time, serves that task's request for its parameters, collects its
// reports, and returns when the task says it is done; it also speaks to the server with the admin badge. Every raw message is
// printed (`K3 rep`, `K3 adm`) before anything is derived from it, so the verifier can recompute every finding from the log.
//

use alloc::vec::Vec;

use crate::k3_abi::*;
use crate::k3_spawn::Domain;
use crate::{Fail, uprintln};

pub(crate) type Report = [u64; 4];

pub(crate) struct World {
    /// The endpoint the root task receives reports and faults on.
    pub(crate) r_ep: sel4::cap::Endpoint,
    /// The root task's capability to the server's endpoint, with the admin badge.
    pub(crate) es_admin: sel4::cap::Endpoint,
    /// A free slot of the root CNode for transient mints (always deleted again).
    pub(crate) scratch: sel4::CPtr,
    /// The notification each domain waits on, by id (index = id).
    pub(crate) go: [Option<sel4::cap::Notification>; 5],
    pub(crate) domains: Vec<Domain>,
}

fn root() -> sel4::cap::CNode {
    sel4::init_thread::slot::CNODE.cap()
}

pub(crate) fn name_of(id: u64) -> &'static str {
    match id {
        ID_C1 => "C1",
        ID_C2 => "C2",
        ID_M => "M",
        ID_S => "S",
        _ => "?",
    }
}

fn reply4(mrs: [u64; 4]) {
    sel4::with_ipc_buffer_mut(|ib| {
        ib.msg_regs_mut()[..4].copy_from_slice(&mrs);
        sel4::reply(ib, sel4::MessageInfo::new(0, 0, 0, 4));
    });
}

impl World {
    pub(crate) fn domain(&self, id: u64) -> Result<&Domain, Fail> {
        self.domains.iter().find(|d| d.id == id).ok_or(Fail::Check("no such domain"))
    }

    /// Signals `step` to task `id`, and serves it until it reports done. Returns its reports, in order.
    pub(crate) fn step(&mut self, id: u64, step: u64, params: [u64; 4]) -> Result<Vec<Report>, Fail> {
        let go = self.go.get(id as usize).copied().flatten().ok_or(Fail::Check("no go notification"))?;
        let dst = root().absolute_cptr(self.scratch);
        dst.mint(&root().absolute_cptr(go.cptr()), sel4::CapRights::write_only(), step)?;
        sel4::cap::Notification::from_bits(self.scratch.bits()).signal();
        dst.delete()?;
        uprintln!("K3 step dom={} step={} params={:x?}", name_of(id), step, params);
        let mut reports = Vec::new();
        loop {
            let got = self.r_ep.recv_with_mrs(());
            let (badge, label, msg) = (got.badge, got.info.label(), got.msg);
            if badge & FAULT_FLAG != 0 {
                uprintln!("K3 fault dom={} label={} mrs={:x?}", name_of(badge & !FAULT_FLAG), label, msg);
                return Err(Fail::Check("a task faulted"));
            }
            if badge != id {
                uprintln!("K3 unexpected dom={} label={} mrs={:x?}", name_of(badge), label, msg);
                return Err(Fail::Check("a message from a task that was not signalled"));
            }
            match label {
                LBL_PARAMS => reply4(params),
                LBL_REPORT => {
                    uprintln!("K3 rep dom={} tag={} v1={} v2={} v3={}", name_of(id), msg[0], msg[1], msg[2], msg[3]);
                    reports.push(msg);
                    reply4([0; 4]);
                }
                LBL_DONE => {
                    reply4([0; 4]);
                    return Ok(reports);
                }
                _ => return Err(Fail::Check("an unknown message from a task")),
            }
        }
    }

    /// One call to the server with the admin badge. Returns (result code, four words); prints it.
    pub(crate) fn admin(&self, op: u64, mrs: [u64; 4]) -> (u64, [u64; 4]) {
        let r = self.es_admin.call_with_mrs(sel4::MessageInfo::new(op, 0, 0, 4), mrs);
        let (rc, m) = (r.info.label(), r.msg);
        uprintln!("K3 adm op={} args={:x?} rc={} m0={} m1={} m2={} m3={}", op, mrs, rc, m[0], m[1], m[2], m[3]);
        (rc, m)
    }
}
