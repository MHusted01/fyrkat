//
// SPDX-License-Identifier: BSD-2-Clause
//
// K3: the tests of results/K3.md section 5, as a script run by the conductor. Each observation prints its raw numbers on a
// `K3 obs` line; the verdict printed on the `K3 test` line follows from them by the rules in the design, and
// `verify_k3.py` recomputes every verdict from the raw lines. A test whose precondition does not hold is VOID, not passed.
//

use alloc::vec::Vec;

use crate::k3_abi::*;
use crate::k3_world::{Report, World, name_of};
use crate::slots::SlotWindow;
use crate::{Fail, MODE, MUTANT, a5_mmio::Page, uprintln};

pub(crate) struct Context {
    /// The stream ids of the two `edu` devices (C1's and C2's).
    pub(crate) sids: [u32; 2],
    /// The root task's own mappings of the two devices' registers.
    pub(crate) late: [Page; 2],
    /// The untyped the root task, as memory manager, gave M a copy of.
    pub(crate) mm_untyped: sel4::cap::Untyped,
    pub(crate) root_slots: SlotWindow,
}

// Pattern bases. Every page of a test holds a pattern of its own so that a word can be traced to where it came from.
const A: u64 = 0x11;
const B: u64 = 0x22;
const C: u64 = 0x33;
const MARKER: u64 = 0x44;
const ATTACK: u64 = 0x55;
const X: u64 = 0x66;
const S3: u64 = 0x77;
const Y: u64 = 0x88;
const DM: u64 = 0x99;
const SG: u64 = 0xaa;
const Z: u64 = 0xbb;
const W: u64 = 0xcc;
const S4: u64 = 0xdd;
const WALL: u64 = 0xee;
/// A pattern base with no zero word (the pattern of base 0 has one, which a refused read would mimic): used where the target's content is unknown.
/// 1 + the kernel's `NotEnoughMemory` (the server reports 1 + the error number): what a retype of an untyped that still has a child gets.
const NOT_ENOUGH_MEMORY: u64 = 11;
const STRUCT: u64 = 0xf0;

/// Where the root task puts the frame it hands to C2 (outside the receive slots the server uses).
const SLOT_G: u64 = 60;
const WORDS: u64 = PATTERN_WORDS as u64;
/// An I/O address in the window that is never mapped for anyone.
const UNMAPPED: u64 = 0x1_0000_0000 + 100 * PAGE as u64;
const DEVICE_BUFFER_OK: u64 = 1;

#[derive(Default)]
struct Tally {
    passed: u32,
    failed: u32,
    void: u32,
}

impl Tally {
    fn test(&mut self, id: &str, ok: bool, note: &str) {
        if ok {
            self.passed += 1;
        } else {
            self.failed += 1;
        }
        uprintln!("K3 test id={} result={} note=\"{}\"", id, if ok { "PASS" } else { "FAIL" }, note);
    }

    fn void(&mut self, id: &str, why: &str) {
        self.void += 1;
        uprintln!("K3 test id={} result=VOID note=\"{}\"", id, why);
    }
}

#[derive(Clone, Copy, Default)]
struct Page4 {
    rc: u64,
    iova: u64,
    handle: u64,
    pa: u64,
}

fn rep(reports: &[Report], index: usize) -> Result<Report, Fail> {
    reports.get(index).copied().ok_or(Fail::Check("a task reported less than the step defines"))
}

fn alloc(w: &mut World, id: u64, k: u64) -> Result<Page4, Fail> {
    let r = w.step(id, STEP_ALLOC, [k, 0, 0, 0])?;
    let (a, b) = (rep(&r, 0)?, rep(&r, 1)?);
    Ok(Page4 { rc: a[1] | (b[1] << 8), iova: a[2], handle: a[3], pa: b[2] })
}

fn fill(w: &mut World, id: u64, k: u64, base: u64) -> Result<(), Fail> {
    w.step(id, STEP_FILL, [k, base, 0, 0]).map(|_| ())
}

fn count(w: &mut World, id: u64, k: u64, a: u64, b: u64) -> Result<(u64, u64), Fail> {
    count3(w, id, k, a, b).map(|(x, y, _)| (x, y))
}

/// As `count`, and also the number of words that are zero. QEMU's SMMU model leaves a device's buffer zero when a read is
/// refused (results/A5-step1.md), so a refused read shows as zeros, not as the old contents.
fn count3(w: &mut World, id: u64, k: u64, a: u64, b: u64) -> Result<(u64, u64, u64), Fail> {
    let r = w.step(id, STEP_COUNT, [k, a, b, 0])?;
    let r = rep(&r, 0)?;
    Ok((r[1], r[2], r[3]))
}

/// A device operation: 0 read into the device's buffer, 1 write from it, 2 program a write without starting it.
fn devop(w: &mut World, id: u64, kind: u64, addr: u64) -> Result<bool, Fail> {
    let r = w.step(id, STEP_DEVOP, [kind, addr, 0, 0])?;
    Ok(rep(&r, 0)?[1] == DEVICE_BUFFER_OK)
}

/// The SMMU's event records since the last call: [on C1's stream, on C2's stream, on others, last address].
fn events(w: &World) -> [u64; 4] {
    w.admin(OP_ADMIN_EVENTS, [0; 4]).1
}

fn faults_of(att: u64, ev: [u64; 4]) -> u64 {
    if att == ID_C1 { ev[0] } else { ev[1] }
}

#[derive(Clone, Copy)]
struct Leak {
    marker: u64,
    zeros: u64,
    secret: u64,
    faults: u64,
    finished: bool,
}

impl Leak {
    fn outcome(&self) -> &'static str {
        if self.secret == WORDS && self.marker == 0 {
            "REACHED"
        } else if self.zeros == WORDS && self.secret == 0 && self.faults >= 1 {
            "REFUSED"
        } else {
            "MIXED"
        }
    }
}

/// `att`'s device reads 64 bytes from the bus address `target` into its buffer and writes the buffer to `att`'s own page
/// (`own_k` at `own_iova`), which held the marker. The words now in the page are the marker (the read did not happen), the
/// target's data, or something else.
fn leak(w: &mut World, att: u64, own_k: u64, own_iova: u64, target: u64, secret: u64, label: &str) -> Result<Leak, Fail> {
    fill(w, att, own_k, MARKER)?;
    devop(w, att, 0, own_iova)?;
    let _ = events(w);
    let f1 = devop(w, att, 0, target)?;
    let f2 = devop(w, att, 1, own_iova)?;
    let (marker, secret_n, zeros) = count3(w, att, own_k, MARKER, secret)?;
    let faults = faults_of(att, events(w));
    let l = Leak { marker, zeros, secret: secret_n, faults, finished: f1 && f2 };
    uprintln!(
        "K3 obs id={} kind=leak attacker={} target={:#x} marker_words={} zero_words={} secret_words={} faults={} finished={} outcome={}",
        label, name_of(att), target, l.marker, l.zeros, l.secret, l.faults, l.finished, l.outcome()
    );
    Ok(l)
}

#[derive(Clone, Copy)]
struct Clobber {
    intact: u64,
    attacked: u64,
    faults: u64,
    finished: bool,
}

impl Clobber {
    fn outcome(&self) -> &'static str {
        if self.attacked == WORDS {
            "REACHED"
        } else if self.intact == WORDS && self.attacked == 0 {
            "INTACT"
        } else {
            "MIXED"
        }
    }
}

/// `att`'s device writes 64 bytes of the attack pattern to `target`; `victim`'s page `victim_k` (which held
/// `victim_base`) is then counted.
#[allow(clippy::too_many_arguments)]
fn clobber(w: &mut World, att: u64, own_k: u64, own_iova: u64, target: u64, victim: u64, victim_k: u64, victim_base: u64, label: &str) -> Result<Clobber, Fail> {
    fill(w, att, own_k, ATTACK)?;
    devop(w, att, 0, own_iova)?;
    let _ = events(w);
    let finished = devop(w, att, 1, target)?;
    let faults = faults_of(att, events(w));
    let (intact, attacked) = count(w, victim, victim_k, victim_base, ATTACK)?;
    let c = Clobber { intact, attacked, faults, finished };
    uprintln!(
        "K3 obs id={} kind=clobber attacker={} target={:#x} victim={} intact_words={} attacked_words={} faults={} finished={} outcome={}",
        label, name_of(att), target, name_of(victim), c.intact, c.attacked, c.faults, c.finished, c.outcome()
    );
    Ok(c)
}

/// (populated slots, frames, untyped) among slots 1 to `SLOT_LAST - 5` of domain `id`, found by copying each into a scratch
/// slot of the root task. The untyped probe is a retype and is therefore made for the clients only.
fn inventory(w: &World, ctx: &mut SlotWindow, id: u64, when: &str, probe_untyped: bool) -> Result<(u64, u64, u64), Fail> {
    let root = sel4::init_thread::slot::CNODE.cap();
    let dst = |index: usize| root.absolute_cptr(sel4::init_thread::Slot::<sel4::cap_type::Unspecified>::from_index(index).cptr());
    let copy_slot = ctx.take()?;
    let object_slot = ctx.take()?;
    let cnode = w.domain(id)?.cnode;
    let (mut populated, mut frames, mut untyped) = (0u64, 0u64, 0u64);
    let mut pas: Vec<u64> = Vec::new();
    for s in 1..(SLOT_LAST - 4) {
        let src = cnode.absolute_cptr_from_bits_with_depth(s, CNODE_BITS);
        if dst(copy_slot).copy(&src, sel4::CapRights::all()).is_err() {
            continue;
        }
        populated += 1;
        let copy = sel4::init_thread::Slot::<sel4::cap_type::Granule>::from_index(copy_slot).cap();
        if is_communication_slot(s) {
            // An invocation on an endpoint copy would be a call; the slot is counted and not probed.
            dst(copy_slot).delete()?;
            continue;
        }
        if let Ok(pa) = copy.frame_get_address() {
            frames += 1;
            pas.push(pa as u64);
        }
        if probe_untyped {
            let ut = sel4::init_thread::Slot::<sel4::cap_type::Untyped>::from_index(copy_slot).cap();
            let blueprint = <sel4::cap_type::Granule as sel4::CapTypeForObjectOfFixedSize>::object_blueprint();
            if ut.untyped_retype(&blueprint, &root.absolute_cptr_for_self(), object_slot, 1).is_ok() {
                untyped += 1;
                let _ = dst(object_slot).delete();
            }
        }
        dst(copy_slot).delete()?;
    }
    uprintln!("K3 inventory dom={} when={} populated={} frames={} untyped={} frame_pas={:x?}", name_of(id), when, populated, frames, untyped, pas);
    Ok((populated, frames, untyped))
}

/// Tries to copy slot `slot` of domain `id` (root task side). Returns the kernel's answer: None if it was copied (and removed again).
fn probe_slot(w: &World, ctx: &mut SlotWindow, id: u64, slot: u64) -> Result<Option<sel4::Error>, Fail> {
    let root = sel4::init_thread::slot::CNODE.cap();
    let index = ctx.take()?;
    let dst = root.absolute_cptr(sel4::init_thread::Slot::<sel4::cap_type::Unspecified>::from_index(index).cptr());
    let src = w.domain(id)?.cnode.absolute_cptr_from_bits_with_depth(slot, CNODE_BITS);
    match dst.copy(&src, sel4::CapRights::all()) {
        Ok(()) => {
            dst.delete()?;
            Ok(None)
        }
        Err(e) => Ok(Some(e)),
    }
}

/// Starts the transfer a stopped driver left programmed: the root task writes the command register of the device through
/// its own mapping. Returns whether the device reported the transfer finished.
fn late_trigger(page: Page) -> bool {
    page.w64(0x98, 3);
    for _ in 0..40_000_000u32 {
        if page.r32(0x98) & 1 == 0 {
            return true;
        }
    }
    false
}

pub(crate) fn run(w: &mut World, mut ctx: Context) -> Result<(u32, u32, u32), Fail> {
    let mut t = Tally::default();
    let naive = MODE == "naive";
    uprintln!("K3 script mode={} mutant={}", MODE, MUTANT);

    // ---- set-up: the SMMU server is up, the streams are bound --------------------------------------------------------
    let (rc, _) = w.admin(OP_ADMIN_PING, [0; 4]);
    t.test("S0a", rc == RC_OK, "the server answers its first admin call (it is serving)");
    for (id, i, as_idx) in [(ID_C1, 0, 0), (ID_C2, 1, 1)] {
        let (rc, _) = w.admin(OP_ADMIN_BIND, [id, u64::from(ctx.sids[i]), as_idx, 0]);
        t.test(if id == ID_C1 { "S0b" } else { "S0c" }, rc == RC_OK, "a client's stream is bound to its own address space");
    }
    for id in [ID_C1, ID_C2, ID_M] {
        let r = w.step(id, STEP_INIT, [0; 4])?;
        let r = rep(&r, 0)?;
        if id != ID_M {
            t.test("S0d", r[1] == 0 && r[3] == 1, "a client mapped its device and read the edu identification");
        }
    }
    for id in [ID_C1, ID_C2] {
        inventory(w, &mut ctx.root_slots, id, "start", true)?;
    }
    let (inv_pop_m, _, _) = inventory(w, &mut ctx.root_slots, ID_M, "start", false)?;
    let _ = inv_pop_m;

    // ---- T1: the negative test ---------------------------------------------------------------------------------------
    let stats0 = w.admin(OP_ADMIN_STATS, [0; 4]).1;
    let a = alloc(w, ID_C1, 0)?;
    let stats1 = w.admin(OP_ADMIN_STATS, [0; 4]).1;
    let b = alloc(w, ID_C1, 1)?;
    let c = alloc(w, ID_C2, 0)?;
    t.test("T1pre", a.rc == 0 && b.rc == 0 && c.rc == 0 && a.pa != b.pa && a.pa != c.pa, "the clients obtained distinct pool pages");
    uprintln!("K3 cost op=alloc commands={} syncs={} revokes={}", stats1[0] - stats0[0], stats1[1] - stats0[1], stats1[2] - stats0[2]);
    fill(w, ID_C1, 0, A)?;
    fill(w, ID_C1, 1, B)?;
    fill(w, ID_C2, 0, C)?;
    // M's frame, from its own untyped: the page the device must not reach (and, later, the one M donates).
    let m = w.step(ID_M, STEP_M_FRAME, [0, 0, 0, 0])?;
    let m = rep(&m, 0)?;
    let m_pa = m[3];
    fill(w, ID_M, 0, DM)?;
    uprintln!("K3 pages C1a_pa={:#x} C1b_pa={:#x} C2c_pa={:#x} M_pa={:#x} C1a_iova={:#x} C1b_iova={:#x} C2c_iova={:#x}", a.pa, b.pa, c.pa, m_pa, a.iova, b.iova, c.iova);

    // (a) positive control: the device moves C1's page a into C1's page b.
    devop(w, ID_C1, 0, a.iova)?;
    devop(w, ID_C1, 1, b.iova)?;
    let (na, nb) = count(w, ID_C1, 1, A, B)?;
    uprintln!("K3 obs id=T1a kind=roundtrip attacker=C1 words_from_source={} words_old={}", na, nb);
    t.test("T1a", na == WORDS && nb == 0, "positive control: the device reached its own mapped pages in both directions");

    // (b) an unmapped I/O address.
    let l = leak(w, ID_C1, 1, b.iova, UNMAPPED, C, "T1b")?;
    t.test("T1b", l.outcome() == "REFUSED", "a read of an unmapped I/O address is refused and a translation fault is recorded");
    // (c) physical addresses of other parties' pages used as bus addresses.
    let l1 = leak(w, ID_C1, 1, b.iova, c.pa, C, "T1c1")?;
    let l2 = leak(w, ID_C1, 1, b.iova, m_pa, DM, "T1c2")?;
    t.test("T1c", l1.outcome() == "REFUSED" && l2.outcome() == "REFUSED", "a read at the physical address of C2's page and of M's page is refused");
    // (c3) the SMMU's own structures (stream table entry of C1's stream, command queue, first level-1 table): their words are
    // not zero, so a read that got through would show it. The server tells the root task where they are.
    let pa_of = |w: &World, i: u64| w.admin(OP_ADMIN_SMMU_PA, [i, 0, 0, 0]).1[0];
    let structures = [("strtab", pa_of(w, 0) + u64::from(ctx.sids[0]) * 64), ("cmdq", pa_of(w, 1)), ("l1", pa_of(w, 3))];
    let mut all_refused = true;
    for (name, pa) in structures {
        let l = leak(w, ID_C1, 1, b.iova, pa, STRUCT, &alloc::format!("T1c3-{}", name))?;
        all_refused &= l.outcome() == "REFUSED";
    }
    t.test("T1c3", all_refused, "a read at the physical address of the SMMU's stream table entry, command queue and level-1 table is refused");
    // C2's device uses its page first, so that a cache keyed by something shared between the two streams would hold C2's translation.
    devop(w, ID_C2, 0, c.iova)?;
    // C2 round-trips its own page through its own second page: it must read its own data even though C1 used the same I/O
    // address first (with one ASID shared by two streams, a cached translation of C1's could be served to C2).
    let c2b = alloc(w, ID_C2, 7)?;
    fill(w, ID_C2, 7, B)?;
    devop(w, ID_C2, 0, c.iova)?;
    devop(w, ID_C2, 1, c2b.iova)?;
    let (n_own, n_old) = count(w, ID_C2, 7, C, B)?;
    uprintln!("K3 obs id=T1g kind=roundtrip attacker=C2 words_from_source={} words_old={}", n_own, n_old);
    t.test("T1g", c2b.rc == 0 && n_own == WORDS && n_old == 0, "C2's device reads C2's own page at an I/O address that C1's device also uses");
    // (d) the I/O address that C2's page has in C2's space, used by C1.
    let ld = leak(w, ID_C1, 1, b.iova, c.iova, C, "T1d")?;
    let (own_a, own_c) = count(w, ID_C1, 1, A, C)?;
    uprintln!("K3 obs id=T1d2 kind=aliasing attacker=C1 target={:#x} words_of_C1_page_a={} words_of_C2_secret={}", c.iova, own_a, own_c);
    t.test("T1d", ld.secret == 0 && own_c == 0 && own_a == WORDS, "the I/O address of C2's page, in C1's space, reaches C1's own page and not C2's data");
    // (e) writes.
    fill(w, ID_C1, 1, B)?;
    let w1 = clobber(w, ID_C1, 1, b.iova, UNMAPPED, ID_C2, 0, C, "T1e1")?;
    let w2 = clobber(w, ID_C1, 1, b.iova, c.pa, ID_C2, 0, C, "T1e2")?;
    let w3 = clobber(w, ID_C1, 1, b.iova, c.iova, ID_C2, 0, C, "T1e3")?;
    let w4 = clobber(w, ID_C1, 1, b.iova, m_pa, ID_M, 0, DM, "T1e4")?;
    t.test("T1e", [w1, w2, w3, w4].iter().all(|x| x.outcome() == "INTACT"), "no write reached C2's or M's page");
    t.test("T1e0", w1.faults >= 1 && w2.faults >= 1 && w4.faults >= 1, "the refused writes left fault records");

    // (f) a client cannot free another client's page.
    let wpage = alloc(w, ID_C1, 3)?;
    let r = w.step(ID_C2, STEP_FREE, [wpage.handle, 0, 0, 0])?;
    let rc_other = rep(&r, 0)?[1];
    let info = w.admin(OP_ADMIN_PAGEINFO, [wpage.handle, 0, 0, 0]).1;
    uprintln!("K3 obs id=T1f kind=free rc_other={} mapped={} owner={}", rc_other, info[0], info[1]);
    t.test("T1f", rc_other == RC_NOT_OWNER && info[0] == 1 && info[1] == ID_C1, "C2 cannot free C1's page; the page stays mapped and owned by C1");
    let r = w.step(ID_C1, STEP_FREE, [wpage.handle, 0, 0, 0])?;
    let _ = rep(&r, 0)?;

    // ---- T2: cooperative teardown -------------------------------------------------------------------------------------
    let x = alloc(w, ID_C1, 2)?;
    fill(w, ID_C1, 2, X)?;
    devop(w, ID_C1, 0, x.iova)?;
    fill(w, ID_C1, 1, B)?;
    devop(w, ID_C1, 1, b.iova)?;
    let (nx, _) = count(w, ID_C1, 1, X, B)?;
    uprintln!("K3 obs id=T2pre kind=roundtrip rc={} words_from_source={}", x.rc, nx);
    t.test("T2pre", x.rc == 0 && nx == WORDS, "positive control: the device reached the page before it was freed");
    let before = w.admin(OP_ADMIN_STATS, [0; 4]).1;
    let r = w.step(ID_C1, STEP_FREE, [x.handle, 0, 0, 0])?;
    let freed = rep(&r, 0)?[1];
    let after = w.admin(OP_ADMIN_STATS, [0; 4]).1;
    uprintln!("K3 cost op=free commands={} syncs={} revokes={}", after[0] - before[0], after[1] - before[1], after[2] - before[2]);
    t.test("T2free", freed == RC_OK, "the owner can free its page");
    let la = leak(w, ID_C1, 1, b.iova, x.iova, X, "T2a")?;
    t.test("T2a", la.outcome() == "REFUSED", "after the free, the old I/O address is refused and a fault is recorded");
    let gone = probe_slot(w, &mut ctx.root_slots, ID_C1, SLOT_RECV_FIRST + 2)?;
    uprintln!("K3 obs id=T2b kind=slot dom=C1 slot={} copy={:?}", SLOT_RECV_FIRST + 2, gone);
    t.test("T2b", gone.is_some(), "C1's capability to the freed frame is gone");
    let c2x = alloc(w, ID_C2, 1)?;
    uprintln!("K3 pages C1x_pa={:#x} C2x_pa={:#x}", x.pa, c2x.pa);
    if c2x.rc != 0 || c2x.pa != x.pa {
        t.void("T2c", "C2 did not receive the physical page C1 freed");
    } else {
        fill(w, ID_C2, 1, S3)?;
        let r = w.step(ID_C1, STEP_FREE, [x.handle, 0, 0, 0])?;
        let stale = rep(&r, 0)?[1];
        let info = w.admin(OP_ADMIN_PAGEINFO, [x.handle, 0, 0, 0]).1;
        uprintln!("K3 obs id=T2e kind=free rc_stale={} mapped={} owner={}", stale, info[0], info[1]);
        t.test("T2e", stale == RC_NOT_OWNER && info[0] == 1 && info[1] == ID_C2, "C1's free of a handle that now belongs to C2 is refused and the page stays C2's");
        let ld = leak(w, ID_C1, 1, b.iova, x.iova, S3, "T2d1")?;
        let cd = clobber(w, ID_C1, 1, b.iova, x.iova, ID_C2, 1, S3, "T2d2")?;
        t.test("T2d", ld.outcome() == "REFUSED" && cd.outcome() == "INTACT", "C2 holds the reused page; C1's device reaches nothing of it through the old address");
    }

    // ---- T3: revoke-while-mapped --------------------------------------------------------------------------------------
    // (a) a mapped page, and every party tries to take it back.
    let y = alloc(w, ID_C1, 4)?;
    fill(w, ID_C1, 4, Y)?;
    devop(w, ID_C1, 0, y.iova)?;
    fill(w, ID_C1, 1, B)?;
    devop(w, ID_C1, 1, b.iova)?;
    let (ny, _) = count(w, ID_C1, 1, Y, B)?;
    uprintln!("K3 obs id=T3pre kind=roundtrip rc={} words_from_source={}", y.rc, ny);
    t.test("T3pre", y.rc == 0 && ny == WORDS, "positive control: the device reaches a mapped page before the attempts");
    let (pop, frames, untyped_r) = inventory(w, &mut ctx.root_slots, ID_C1, "before-attack", true)?;
    let r = w.step(ID_C1, STEP_CSPACE_ATTACK, [0; 4])?;
    let (r0, r1) = (rep(&r, 0)?, rep(&r, 1)?);
    uprintln!("K3 obs id=T3a1 kind=cspace attacker=C1 populated={} frames={} untyped_ok={} tcb_ok={} revoke_failed={} root_populated={} root_frames={} root_untyped={}", r0[1], r0[2], r0[3], r1[1], r1[2], pop, frames, untyped_r);
    t.test("T3a1", r0[1] == pop && r0[2] == frames && r0[3] == 0 && untyped_r == 0 && r1[1] == 0 && r1[2] == 0, "C1 holds exactly the capabilities the root task gave it, no untyped and no TCB, and an Untyped_Retype or TCB call on any slot fails, and a Revoke on every slot succeeds");
    let r = w.step(ID_C1, STEP_TRY_ADMIN, [0; 4])?;
    let r = rep(&r, 0)?;
    uprintln!("K3 obs id=T3a2 kind=admin ping_rc={} events_rc={} rebadge_rc={}", r[1], r[2], r[3]);
    t.test("T3a2", r[1] == RC_ADMIN_ONLY && r[2] == RC_ADMIN_ONLY && r[3] != 0, "C1 cannot use the admin operations or re-badge its endpoint capability");
    let r = w.step(ID_C1, STEP_REMAP, [4, 0, 0, 0])?;
    let r = rep(&r, 0)?;
    uprintln!("K3 obs id=T3a3 kind=remap unmap_rc={} map_rc={}", r[1], r[2]);
    t.test("T3a3", r[1] == 0 && r[2] == 0, "C1 can unmap and map its own frame (a legitimate self-operation)");
    let r = w.step(ID_C1, STEP_DROP_FRAME, [4, 0, 0, 0])?;
    let r = rep(&r, 0)?;
    let dropped = (r[1], r[2]);
    fill(w, ID_C1, 1, B)?;
    devop(w, ID_C1, 0, y.iova)?;
    devop(w, ID_C1, 1, b.iova)?;
    let (ny2, _) = count(w, ID_C1, 1, Y, B)?;
    let info = w.admin(OP_ADMIN_PAGEINFO, [y.handle, 0, 0, 0]).1;
    uprintln!("K3 obs id=T3a4 kind=drop-frame revoke_rc={} delete_rc={} words_from_source={} mapped={} owner={}", dropped.0, dropped.1, ny2, info[0], info[1]);
    t.test("T3a4", dropped == (0, 0) && ny2 == WORDS && info[0] == 1 && info[1] == ID_C1, "after C1 revoked and deleted its capability, the page is still the pool's and still mapped: the device reaches it");
    let probe = w.admin(OP_ADMIN_PROBE, [y.handle, 0, 0, 0]).1;
    uprintln!("K3 obs id=T3a7 kind=kernel-probe handle={} frame_pa={:#x} retype_rc={}", y.handle, probe[0], probe[1]);
    t.test("T3a7", probe[0] == y.pa && probe[1] == NOT_ENOUGH_MEMORY, "the kernel still answers for the frame the server holds, and refuses to retype its untyped, after C1 revoked and deleted its own capability");
    // The rest of the pool is taken: the mapped page must never be handed out again.
    let r = w.step(ID_C2, STEP_ALLOC_MANY, [8, 0, 0, 0])?;
    let r = rep(&r, 0)?;
    let (got, last, mask) = (r[1], r[2], r[3]);
    let mut owners: Vec<(u64, u64, u64)> = Vec::new();
    for h in 0..POOL_PAGES as u64 {
        let i = w.admin(OP_ADMIN_PAGEINFO, [h, 0, 0, 0]).1;
        owners.push((i[0], i[1], i[2]));
    }
    let distinct = owners.iter().enumerate().all(|(i, o)| owners.iter().skip(i + 1).all(|p| p.2 != o.2));
    let y_once = owners.iter().filter(|o| o.2 == y.pa).count() == 1 && owners.get(y.handle as usize).map(|o| o.1) == Some(ID_C1);
    uprintln!("K3 obs id=T3a5 kind=exhaustion obtained={} last_rc={} handles_mask={:#x} mapped={} distinct_pas={} y_pa_once_with_C1={}", got, last, mask, owners.iter().filter(|o| o.0 == 1).count(), distinct, y_once);
    t.test("T3a5", last == RC_NO_MEMORY && distinct && y_once && owners.iter().all(|o| o.0 == 1), "when the pool is used up no page is handed out twice, and the page whose capability C1 dropped is still C1's");
    for h in 0..POOL_PAGES as u64 {
        if mask & (1 << h) != 0 {
            w.step(ID_C2, STEP_FREE, [h, 0, 0, 0])?;
        }
    }
    // Control for the probe: a page that was freed has no frame and its untyped can be retyped.
    if let Some(h) = (0..POOL_PAGES as u64).find(|h| mask & (1 << h) != 0) {
        let free_probe = w.admin(OP_ADMIN_PROBE, [h, 0, 0, 0]).1;
        uprintln!("K3 obs id=T3a8 kind=kernel-probe-free handle={} frame_pa={:#x} retype_rc={}", h, free_probe[0], free_probe[1]);
        t.test("T3a8", free_probe[0] == 0 && free_probe[1] == 0, "control for the probe: for a freed page the kernel has no frame to answer for and accepts a retype of its untyped");
    } else {
        t.void("T3a8", "no page was freed to probe");
    }
    let r = w.step(ID_M, STEP_CSPACE_ATTACK, [0; 4])?;
    let (m0, m1) = (rep(&r, 0)?, rep(&r, 1)?);
    uprintln!("K3 obs id=T3a6 kind=cspace attacker=M untyped_ok={} tcb_ok={}", m0[3], m1[1]);
    t.test("T3a6", m0[3] == 1 && m1[1] == 0, "M holds one untyped (its own) and no TCB; it cannot retype or suspend through any other slot");

    // (c) the control and the design on the same actions: M offers memory it owns; the memory manager takes it back and
    // hands it to C2; C1's device then tries the donated memory's address.
    let (rc, d) = w.step(ID_M, STEP_M_DONATE, [0, ID_C1, 0, 0]).and_then(|r| rep(&r, 0)).map(|r| (r[1], r[2]))?;
    uprintln!("K3 obs id=T3c0 kind=donation mode={} rc={} detail={}", MODE, rc, d);
    let donated_iova = if naive { d } else { UNMAPPED };
    if naive {
        t.test("T3c0", rc == RC_OK, "control: the naive server accepts a donated frame and maps it for C1's stream");
        fill(w, ID_M, 0, DM)?;
        let pos = leak(w, ID_C1, 1, b.iova, donated_iova, DM, "T3c1")?;
        t.test("T3c1", pos.outcome() == "REACHED", "control, positive: C1's device reads the donated memory before it is reclaimed");
    } else {
        t.test("T3c0", rc == RC_NO_DONATIONS && d == 0, "design: the server refuses a donation and keeps no capability that was sent with it");
    }
    // The memory manager (the root task) reclaims M's memory, and hands the same memory to C2.
    let root = sel4::init_thread::slot::CNODE.cap();
    let revoke_rc = root.absolute_cptr(ctx.mm_untyped.cptr()).revoke();
    uprintln!("K3 obs id=T3c2 kind=reclaim rc={:?}", revoke_rc.err());
    let g_index = ctx.root_slots.take()?;
    let g = sel4::init_thread::Slot::<sel4::cap_type::Granule>::from_index(g_index);
    let blueprint = <sel4::cap_type::Granule as sel4::CapTypeForObjectOfFixedSize>::object_blueprint();
    ctx.mm_untyped.untyped_retype(&blueprint, &root.absolute_cptr_for_self(), g_index, 1)?;
    let g_pa = g.cap().frame_get_address()? as u64;
    let to_c2 = w.domain(ID_C2)?.cnode.absolute_cptr_from_bits_with_depth(SLOT_G, CNODE_BITS);
    to_c2.copy(&root.absolute_cptr(g.cptr()), sel4::CapRights::all())?;
    uprintln!("K3 pages M_frame_pa={:#x} reused_frame_pa={:#x}", m_pa, g_pa);
    if g_pa != m_pa {
        t.void("T3c3", "the reclaimed memory was not reused at the same physical address");
    } else {
        let r = w.step(ID_C2, STEP_MAP_RECEIVED, [2, SLOT_G, 0, 0])?;
        let r = rep(&r, 0)?;
        fill(w, ID_C2, 2, SG)?;
        let mapped = r[1] == 0;
        let l = leak(w, ID_C1, 1, b.iova, donated_iova, SG, "T3c3")?;
        let l_pa = leak(w, ID_C1, 1, b.iova, g_pa, SG, "T3c4")?;
        fill(w, ID_C2, 2, SG)?;
        let cl = clobber(w, ID_C1, 1, b.iova, donated_iova, ID_C2, 2, SG, "T3c5")?;
        if naive {
            t.test("T3c3", mapped && l.outcome() == "REACHED" && cl.outcome() == "REACHED", "control (the falsifier of A5 step 2, across protection domains): after the reclaim, C1's device reads and overwrites C2's secret through the stale mapping");
        } else {
            t.test("T3c3", mapped && l.outcome() == "REFUSED" && l_pa.outcome() == "REFUSED" && cl.outcome() == "INTACT", "design: the same actions leave C1's device with nothing of C2's secret");
        }
    }

    // ---- T4: the driver is killed with a transfer in flight ---------------------------------------------------------------
    let z = alloc(w, ID_C1, 5)?;
    fill(w, ID_C1, 5, Z)?;
    devop(w, ID_C1, 0, z.iova)?;
    // Control for the root task's own start of a programmed transfer: with the mapping alive it lands in the page.
    fill(w, ID_C1, 5, W)?;
    devop(w, ID_C1, 2, z.iova)?;
    let ok0 = late_trigger(ctx.late[0]);
    let (nz, nw) = count(w, ID_C1, 5, Z, W)?;
    uprintln!("K3 obs id=T4pre kind=late-trigger finished={} words_from_device={} words_old={}", ok0, nz, nw);
    t.test("T4pre", ok0 && nz == WORDS && nw == 0, "control: the root task's start of a programmed transfer lands in the live page");
    fill(w, ID_C1, 5, W)?;
    let owned: u64 = (0..POOL_PAGES as u64).filter(|h| w.admin(OP_ADMIN_PAGEINFO, [*h, 0, 0, 0]).1[..2] == [1, ID_C1]).count() as u64;
    // The driver starts the transfer (edu runs it about 100 ms later by a timer) and is killed at once.
    devop(w, ID_C1, 3, z.iova)?;
    let armed0 = ctx.late[0].r32(0x98) & 1 == 1;
    w.domain(ID_C1)?.tcb.tcb_suspend()?;
    let (rc, dm) = w.admin(OP_ADMIN_DEAD, [ID_C1, 0, 0, 0]);
    let armed1 = ctx.late[0].r32(0x98) & 1 == 1;
    let still: u64 = (0..POOL_PAGES as u64).filter(|h| w.admin(OP_ADMIN_PAGEINFO, [*h, 0, 0, 0]).1[..2] == [1, ID_C1]).count() as u64;
    uprintln!("K3 obs id=T4a kind=kill dom=C1 pages_owned={} dead_rc={} freed={} owned_after={} transfer_running_at_kill={} transfer_running_after_teardown={}", owned, rc, dm[0], still, armed0, armed1);
    t.test("T4a", rc == RC_OK && dm[0] == owned && still == 0, "the server freed every page of the dead client");
    let mut got_z = None;
    for k in 3..7u64 {
        let p = alloc(w, ID_C2, k)?;
        if p.rc != 0 {
            break;
        }
        if p.pa == z.pa {
            got_z = Some(k);
            break;
        }
    }
    match got_z {
        None => t.void("T4b", "C2 did not receive the physical page of the dead driver"),
        Some(k) => {
            fill(w, ID_C2, k, S4)?;
            let armed2 = ctx.late[0].r32(0x98) & 1 == 1;
            let _ = events(w);
            // Wait for the device's timer to run the transfer.
            let mut finished = false;
            for _ in 0..400_000_000u64 {
                if ctx.late[0].r32(0x98) & 1 == 0 {
                    finished = true;
                    break;
                }
            }
            let faults = events(w)[0];
            let (intact, from_dead) = count(w, ID_C2, k, S4, Z)?;
            uprintln!("K3 obs id=T4b kind=in-flight-dma armed_at_kill={} armed_after_teardown={} armed_when_c2_owned_page={} finished={} faults={} intact_words={} words_of_dead_drivers_buffer={}", armed0, armed1, armed2, finished, faults, intact, from_dead);
            if !(armed0 && armed1 && armed2) {
                t.void("T4b", "the transfer had already run before the page was reassigned (the 100 ms timer elapsed)");
            } else {
                t.test("T4b", finished && faults >= 1 && intact == WORDS && from_dead == 0, "the transfer running when the driver was killed faults after the teardown, and the page now owned by C2 is unchanged");
            }
            // The same again, started by the root task after everything is settled.
            fill(w, ID_C2, k, S4)?;
            let _ = events(w);
            let f2 = late_trigger(ctx.late[0]);
            let faults2 = events(w)[0];
            let (intact2, from_dead2) = count(w, ID_C2, k, S4, Z)?;
            uprintln!("K3 obs id=T4c kind=late-dma finished={} faults={} intact_words={} words_of_dead_drivers_buffer={}", f2, faults2, intact2, from_dead2);
            t.test("T4c", f2 && faults2 >= 1 && intact2 == WORDS && from_dead2 == 0, "the dead driver's device, started again later, still faults");
        }
    }
    let _ = (WALL, B);
    let stats = w.admin(OP_ADMIN_STATS, [0; 4]).1;
    uprintln!("K3 cost total commands={} syncs={} revokes={} allocs={}", stats[0], stats[1], stats[2], stats[3]);
    Ok((t.passed, t.failed, t.void))
}
