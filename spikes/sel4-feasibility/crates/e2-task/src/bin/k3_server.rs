//
// SPDX-License-Identifier: BSD-2-Clause
//

//! K3 SMMU server (results/K3.md). The only task that holds the SMMU, the pool untyped `U_pool` and the untyped for the SMMU's
//! own structures. Single-threaded: it receives on its endpoint and answers; the only call it ever makes is one failure
//! report to the conductor if its set-up fails, before it serves (so it cannot deadlock with the conductor). A client is identified by the badge of the capability it called through; the conductor's badge is
//! `BADGE_ADMIN`.
//!
//! The invariant it exists to keep: **a pool page is freed only after its stream's translation is cleared, invalidated and
//! synced, and only then is its untyped revoked** (teardown). Build-time `K3_MUTANT` breaks one rule on purpose:
//! `skip-invalidate`, `reclaim-while-mapped`, `no-owner-check`, `death-without-teardown`, `shared-address-space`.
//! Build-time `K3_MODE=naive` builds the *control*: it also accepts a frame donated by a caller and maps it, which is the
//! arrangement A5 step 2 showed to be unsafe; the design build refuses donations and keeps no capability a caller sends.

#![no_std]
#![no_main]

use sel4::CapTypeForObjectOfFixedSize;

#[path = "../k3_abi.rs"]
mod k3_abi;
#[path = "../k3_mmio.rs"]
mod k3_mmio;
#[path = "../k3_smmu.rs"]
mod k3_smmu;
#[path = "../k3_runtime.rs"]
mod runtime;

use k3_abi::*;
use k3_mmio::{PAGE, Page};
use k3_smmu::{AddrSpace, Event, IOVA_BASE, Ram, Smmu};

const MUTANT: Option<&str> = option_env!("K3_MUTANT");
const NAIVE: bool = is_naive(option_env!("K3_MODE"));

/// `str` comparison is not available in a constant, so this compares the bytes.
const fn is_naive(mode: Option<&str>) -> bool {
    match mode {
        Some(m) => {
            let (m, want) = (m.as_bytes(), b"naive");
            if m.len() != want.len() {
                return false;
            }
            let mut i = 0;
            while i < m.len() {
                if m[i] != want[i] {
                    return false;
                }
                i += 1;
            }
            true
        }
        None => false,
    }
}

/// Number of address spaces (one per client stream) and the pages the SMMU structures use.
const AS_COUNT: usize = 2;
const SMMU_RAM_PAGES: usize = 3 + AS_COUNT * 4;
/// Window page indices: 0 and 1 are the SMMU register pages, RAM follows.
const WINDOW_RAM_FIRST: usize = 2;

#[derive(Clone, Copy)]
struct PoolPage {
    mapped: bool,
    owner: u64,
    /// The address space the page is mapped in, fixed when it is mapped (a later re-bind of the owner cannot redirect a teardown).
    as_idx: usize,
    pa: u64,
    iova: u64,
}

struct Server {
    smmu: Smmu,
    spaces: [AddrSpace; AS_COUNT],
    /// Per client id (index = id): the address space index it is bound to.
    client_as: [Option<usize>; 4],
    /// Per client id: the stream id the conductor bound to it (events are counted per client).
    client_sid: [u32; 4],
    /// Per address space: bit k set when the I/O page k is in use.
    iova_used: [u64; AS_COUNT],
    pages: [PoolPage; POOL_PAGES],
    revokes: u64,
    allocs: u64,
    overflows: u64,
    smmu_pas: [u64; SMMU_RAM_PAGES],
}

fn self_cnode() -> sel4::cap::CNode {
    sel4::cap::CNode::from_bits(SLOT_SELF_CNODE)
}

fn slot(index: u64) -> sel4::AbsoluteCPtr {
    self_cnode().absolute_cptr_from_bits_with_depth(index, CNODE_BITS)
}

fn va_of(window_page: usize) -> usize {
    WINDOW_BASE + window_page * PAGE
}

fn setup() -> Result<Server, &'static str> {
    let vspace = sel4::cap::VSpace::from_bits(SLOT_SELF_VSPACE);
    let dst = self_cnode().absolute_cptr_for_self();
    // The two register pages of the SMMU, mapped as device memory.
    for (i, s) in [SLOT_DEVICE, SLOT_DEVICE1].into_iter().enumerate() {
        sel4::cap::Granule::from_bits(s)
            .frame_map(vspace, va_of(i), sel4::CapRights::read_write(), sel4::VmAttributes::NONE)
            .map_err(|_| "mapping an SMMU register page failed")?;
    }
    // SAFETY (both `Page::at` calls): the pages were just mapped read-write at these addresses and are never unmapped.
    let (regs, regs1) = unsafe { (Page::at(va_of(0)), Page::at(va_of(1))) };

    // The memory the SMMU reads by itself, from `U_srv`.
    let mut ram = [None::<Ram>; SMMU_RAM_PAGES];
    let untyped = sel4::cap::Untyped::from_bits(SLOT_UNTYPED_A);
    for (j, r) in ram.iter_mut().enumerate() {
        let s = SLOT_SMMU_RAM + j as u64;
        untyped
            .untyped_retype(&sel4::cap_type::Granule::object_blueprint(), &dst, s as usize, 1)
            .map_err(|_| "retyping SMMU memory failed")?;
        let frame = sel4::cap::Granule::from_bits(s);
        frame
            .frame_map(vspace, va_of(WINDOW_RAM_FIRST + j), sel4::CapRights::read_write(), sel4::VmAttributes::default())
            .map_err(|_| "mapping SMMU memory failed")?;
        let pa = frame.frame_get_address().map_err(|_| "reading a frame address failed")? as u64;
        // SAFETY: just mapped read-write; the capability stays in a slot nothing revokes or deletes (the untyped is never revoked).
        *r = Some(Ram { page: unsafe { Page::at(va_of(WINDOW_RAM_FIRST + j)) }, pa });
    }
    let mut smmu_pas = [0u64; SMMU_RAM_PAGES];
    for (pa, r) in smmu_pas.iter_mut().zip(ram.iter()) {
        *pa = r.map_or(0, |r| r.pa);
    }
    let mut it = ram.into_iter().flatten();
    let mut next = || it.next().ok_or("out of SMMU pages");
    let (strtab, cmdq, eventq) = (next()?, next()?, next()?);
    let mut smmu = Smmu::new(regs, regs1, strtab, cmdq, eventq);
    smmu.enable()?;
    let a0 = AddrSpace::new([next()?, next()?, next()?], next()?, 1);
    let a1 = AddrSpace::new([next()?, next()?, next()?], next()?, if MUTANT == Some("shared-asid") { 1 } else { 2 });

    // The pool: one 4 KiB untyped per page.
    let pool = sel4::cap::Untyped::from_bits(SLOT_UNTYPED_B);
    for i in 0..POOL_PAGES as u64 {
        pool.untyped_retype(&sel4::ObjectBlueprint::Untyped { size_bits: 12 }, &dst, (SLOT_POOL_UNTYPED + i) as usize, 1)
            .map_err(|_| "carving the pool failed")?;
    }
    if NAIVE {
        set_recv(SLOT_DONATION);
    }
    Ok(Server {
        smmu,
        spaces: [a0, a1],
        client_as: [None; 4],
        client_sid: [u32::MAX; 4],
        iova_used: [0; AS_COUNT],
        pages: [PoolPage { mapped: false, owner: 0, as_idx: 0, pa: 0, iova: 0 }; POOL_PAGES],
        revokes: 0,
        allocs: 0,
        overflows: 0,
        smmu_pas,
    })
}

/// Makes `index` the slot capabilities sent to the server land in. The design build never calls this.
fn set_recv(index: u64) {
    sel4::with_ipc_buffer_mut(|ib| ib.set_recv_slot(&slot(index)));
}

impl Server {
    fn alloc(&mut self, client: u64) -> Result<(u64, u64), u64> {
        let as_idx = self.client_as.get(client as usize).copied().flatten().ok_or(RC_BAD_ARGS)?;
        let i = self.pages.iter().position(|p| !p.mapped).ok_or(RC_NO_MEMORY)?;
        let k = (!self.iova_used[as_idx]).trailing_zeros() as u64;
        if k >= 64 {
            return Err(RC_NO_MEMORY);
        }
        let dst = self_cnode().absolute_cptr_for_self();
        sel4::cap::Untyped::from_bits(SLOT_POOL_UNTYPED + i as u64)
            .untyped_retype(&sel4::cap_type::Granule::object_blueprint(), &dst, (SLOT_POOL_FRAME + i as u64) as usize, 1)
            .map_err(|_| RC_NO_MEMORY)?;
        let pa = sel4::cap::Granule::from_bits(SLOT_POOL_FRAME + i as u64).frame_get_address().map_err(|_| RC_SMMU)? as u64;
        let iova = IOVA_BASE + k * PAGE as u64;
        self.spaces[as_idx].map(iova, pa, true).map_err(|_| RC_SMMU)?;
        self.iova_used[as_idx] |= 1 << k;
        self.pages[i] = PoolPage { mapped: true, owner: client, as_idx, pa, iova };
        self.allocs += 1;
        Ok((iova, i as u64))
    }

    /// The order of I2: clear, invalidate, sync, then revoke the page's untyped; only then is the page free.
    fn teardown(&mut self, i: usize) -> Result<(), u64> {
        let p = self.pages[i];
        let as_idx = p.as_idx;
        let space = self.spaces[as_idx];
        if MUTANT != Some("reclaim-while-mapped") {
            space.unmap(p.iova).map_err(|_| RC_SMMU)?;
            if MUTANT != Some("skip-invalidate") {
                self.smmu.invalidate_page(space.asid, p.iova).map_err(|_| RC_SMMU)?;
            }
            self.smmu.sync().map_err(|_| RC_SMMU)?;
        }
        self.release(i, as_idx)
    }

    /// Revokes the page's untyped (every copy of its frame goes with it) and marks it free.
    fn release(&mut self, i: usize, as_idx: usize) -> Result<(), u64> {
        slot(SLOT_POOL_UNTYPED + i as u64).revoke().map_err(|_| RC_SMMU)?;
        self.revokes += 1;
        let p = self.pages[i];
        let k = (p.iova - IOVA_BASE) / PAGE as u64;
        self.iova_used[as_idx] &= !(1 << k);
        self.pages[i].mapped = false;
        Ok(())
    }

    fn free(&mut self, client: u64, handle: u64) -> Result<(), u64> {
        let i = usize::try_from(handle).ok().filter(|i| *i < POOL_PAGES).ok_or(RC_BAD_HANDLE)?;
        if !self.pages[i].mapped {
            return Err(RC_BAD_HANDLE);
        }
        if self.pages[i].owner != client && MUTANT != Some("no-owner-check") {
            return Err(RC_NOT_OWNER);
        }
        self.teardown(i)
    }

    fn dead(&mut self, client: u64) -> Result<u64, u64> {
        let mut n = 0;
        for i in 0..POOL_PAGES {
            if self.pages[i].mapped && self.pages[i].owner == client {
                if MUTANT == Some("death-without-teardown") {
                    // The bug: the pages are given back without the translation being touched.
                    self.release(i, self.pages[i].as_idx)?;
                } else {
                    self.teardown(i)?;
                }
                n += 1;
            }
        }
        Ok(n)
    }

    fn donate(&mut self, target: u64, caps_received: usize) -> Result<u64, u64> {
        if !NAIVE {
            return Err(RC_NO_DONATIONS);
        }
        if caps_received == 0 {
            return Err(RC_BAD_ARGS);
        }
        let as_idx = self.client_as.get(target as usize).copied().flatten().ok_or(RC_BAD_ARGS)?;
        let pa = sel4::cap::Granule::from_bits(SLOT_DONATION).frame_get_address().map_err(|_| RC_BAD_ARGS)? as u64;
        let k = (!self.iova_used[as_idx]).trailing_zeros() as u64;
        let iova = IOVA_BASE + k * PAGE as u64;
        self.spaces[as_idx].map(iova, pa, true).map_err(|_| RC_SMMU)?;
        self.iova_used[as_idx] |= 1 << k;
        Ok(iova)
    }

    fn events(&mut self) -> [u64; 4] {
        let mut buf = [Event::default(); 16];
        let (n, overflowed) = self.smmu.drain_events(&mut buf);
        if overflowed {
            self.overflows += 1;
        }
        let mut counts = [0u64; 3];
        for e in &buf[..n] {
            if e.sid == self.client_sid[ID_C1 as usize] {
                counts[0] += 1;
            } else if e.sid == self.client_sid[ID_C2 as usize] {
                counts[1] += 1;
            } else {
                counts[2] += 1;
            }
        }
        [counts[0], counts[1], counts[2], self.overflows]
    }
}

fn reply(rc: u64, mrs: [u64; 4], cap_slot: Option<u64>) {
    sel4::with_ipc_buffer_mut(|ib| {
        let regs = ib.msg_regs_mut();
        regs[..4].copy_from_slice(&mrs);
        let extra = match cap_slot {
            Some(s) => {
                ib.caps_or_badges_mut()[0] = s;
                1
            }
            None => 0,
        };
        sel4::reply(ib, sel4::MessageInfo::new(rc, 0, extra, 4));
    });
}

fn serve(srv: &mut Server) -> ! {
    let ep = sel4::cap::Endpoint::from_bits(SLOT_ES);
    loop {
        let got = ep.recv_with_mrs(());
        let (label, badge, msg) = (got.info.label(), got.badge, got.msg);
        let admin = badge == BADGE_ADMIN;
        let client = badge;
        // A message shorter than the operation needs would read stale registers: refuse it.
        let needed = match label {
            OP_FREE | OP_DONATE | OP_ADMIN_DEAD | OP_ADMIN_PAGEINFO | OP_ADMIN_SMMU_PA | OP_ADMIN_PROBE => 1,
            OP_ADMIN_BIND => 3,
            _ => 0,
        };
        if got.info.length() < needed {
            reply(RC_BAD_ARGS, [0; 4], None);
            continue;
        }
        match label {
            OP_ALLOC if !admin => match srv.alloc(client) {
                Ok((iova, handle)) => reply(RC_OK, [iova, handle, 0, 0], Some(SLOT_POOL_FRAME + handle)),
                Err(rc) => reply(rc, [0; 4], None),
            },
            OP_FREE if !admin => match srv.free(client, msg[0]) {
                Ok(()) => reply(RC_OK, [0; 4], None),
                Err(rc) => reply(rc, [0; 4], None),
            },
            OP_DONATE if !admin => match srv.donate(msg[0], got.info.extra_caps()) {
                Ok(iova) => reply(RC_OK, [iova, 0, 0, 0], None),
                Err(rc) => reply(rc, [got.info.extra_caps() as u64, 0, 0, 0], None),
            },
            OP_ADMIN_PING | OP_ADMIN_BIND | OP_ADMIN_DEAD | OP_ADMIN_EVENTS | OP_ADMIN_STATS | OP_ADMIN_PAGEINFO | OP_ADMIN_SMMU_PA | OP_ADMIN_PROBE
                if !admin =>
            {
                reply(RC_ADMIN_ONLY, [0; 4], None)
            }
            OP_ADMIN_PING => reply(RC_OK, [0; 4], None),
            OP_ADMIN_BIND => {
                let (c, sid, mut idx) = (msg[0], msg[1] as u32, msg[2] as usize);
                if MUTANT == Some("shared-address-space") {
                    idx = 0;
                }
                if c as usize >= srv.client_as.len() || idx >= AS_COUNT || srv.pages.iter().any(|p| p.mapped && p.owner == c) {
                    reply(RC_BAD_ARGS, [0; 4], None);
                } else {
                    srv.client_as[c as usize] = Some(idx);
                    srv.client_sid[c as usize] = sid;
                    match srv.smmu.bind_stream(sid, &srv.spaces[idx]) {
                        Ok(()) => reply(RC_OK, [0; 4], None),
                        Err(_) => reply(RC_SMMU, [0; 4], None),
                    }
                }
            }
            OP_ADMIN_DEAD => match srv.dead(msg[0]) {
                Ok(n) => reply(RC_OK, [n, 0, 0, 0], None),
                Err(rc) => reply(rc, [0; 4], None),
            },
            OP_ADMIN_EVENTS => reply(RC_OK, srv.events(), None),
            OP_ADMIN_STATS => reply(RC_OK, [srv.smmu.stats.commands, srv.smmu.stats.syncs, srv.revokes, srv.allocs], None),
            OP_ADMIN_PAGEINFO => {
                let i = msg[0] as usize;
                match srv.pages.get(i) {
                    Some(p) => reply(RC_OK, [u64::from(p.mapped), p.owner, p.pa, p.iova], None),
                    None => reply(RC_BAD_HANDLE, [0; 4], None),
                }
            }
            OP_ADMIN_SMMU_PA => reply(RC_OK, [srv.smmu_pas.get(msg[0] as usize).copied().unwrap_or(0), 0, 0, 0], None),
            OP_ADMIN_PROBE => {
                let i = msg[0];
                if i as usize >= POOL_PAGES {
                    reply(RC_BAD_HANDLE, [0; 4], None);
                } else {
                    let pa = sel4::cap::Granule::from_bits(SLOT_POOL_FRAME + i).frame_get_address().map_or(0, |a| a as u64);
                    let dst = self_cnode().absolute_cptr_for_self();
                    let retype = sel4::cap::Untyped::from_bits(SLOT_POOL_UNTYPED + i).untyped_retype(
                        &sel4::cap_type::Granule::object_blueprint(),
                        &dst,
                        SLOT_PROBE as usize,
                        1,
                    );
                    let rc = match retype {
                        Ok(()) => match slot(SLOT_PROBE).delete() {
                            Ok(()) => 0,
                            Err(_) => 0xdead,
                        },
                        Err(e) => 1 + e as u64,
                    };
                    reply(RC_OK, [pa, rc, 0, 0], None);
                }
            }
            _ => reply(RC_BAD_OP, [0; 4], None),
        }
    }
}

fn main() -> ! {
    match setup() {
        Ok(mut srv) => serve(&mut srv),
        Err(what) => {
            // Tell the conductor why, by calling its endpoint once with a failure report, then stop.
            let ep = sel4::cap::Endpoint::from_bits(SLOT_REPORT);
            let bytes = what.as_bytes();
            let mut w = [0u64; 4];
            for (i, b) in bytes.iter().take(24).enumerate() {
                w[1 + i / 8] |= u64::from(*b) << (8 * (i % 8));
            }
            w[0] = 0xdead;
            ep.call_with_mrs(sel4::MessageInfo::new(LBL_REPORT, 0, 0, 4), w);
            loop {
                sel4::cap::Notification::from_bits(SLOT_GO).wait();
            }
        }
    }
}
