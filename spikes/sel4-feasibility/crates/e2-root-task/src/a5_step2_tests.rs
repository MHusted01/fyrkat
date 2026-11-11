//
// SPDX-License-Identifier: BSD-2-Clause
//
// A5 step 2: the scenarios (results/A5-step2.md, section 1). Every observation is a page content read by the root task
// through its own mapping, a record of the SMMU's event queue, or an answer of the kernel to a capability operation.
//
// A `Ram` whose frame capability has been revoked must not be read or written again: its mapping is gone, and an
// access would stop the root task with a fault. The scenarios keep only the physical address of such a page.
//

use alloc::vec::Vec;

use sel4::CapTypeForObjectOfFixedSize;

use crate::smmuv3::{EVT_F_TRANSLATION, Event, IOVA_BASE, Ram};
use crate::{Fail, MUTANT, World, uprintln};

const WORDS: usize = 16;
const BYTES: u64 = 64;
const ASID: u16 = 7;
/// The I/O virtual address the frame under test is mapped at, and the one of the server's own page O.
const IOVA_DMA: u64 = IOVA_BASE;
const IOVA_OUT: u64 = IOVA_BASE + 0x3000;
/// What the kernel answers a copy out of an empty slot with.
const EMPTY_SLOT: sel4::Error = sel4::Error::FailedLookup;
/// A 4 KiB untyped: the donor's whole holding.
const UNTYPED_BITS: usize = 12;
/// A CNode of 2^7 slots of 32 bytes fills the same 4 KiB.
const CNODE_BITS: usize = 7;
const SLOT_BYTES: u64 = 32;
const BADGE: u64 = 0x5eed_c0de;

fn fill(ram: Ram, seed: u32) {
    for i in 0..WORDS {
        ram.page.w32(i * 4, seed.wrapping_add(i as u32));
    }
}

fn zero(ram: Ram) {
    for i in 0..WORDS {
        ram.page.w32(i * 4, 0);
    }
}

fn holds(ram: Ram, seed: u32) -> usize {
    (0..WORDS).filter(|&i| ram.page.r32(i * 4) == seed.wrapping_add(i as u32)).count()
}

fn zeros(ram: Ram) -> usize {
    (0..WORDS).filter(|&i| ram.page.r32(i * 4) == 0).count()
}

/// The device copies `count` bytes from `addr` into its buffer. A transfer the device does not report finished is counted.
fn dev_read(w: &mut World, addr: u64, count: u64) {
    if !w.edu.read_from(addr, count) {
        w.unfinished += 1;
    }
}

/// The device copies `count` bytes from its buffer to `addr`.
fn dev_write(w: &mut World, addr: u64, count: u64) {
    if !w.edu.write_to(addr, count) {
        w.unfinished += 1;
    }
}

fn root() -> sel4::cap::CNode {
    sel4::init_thread::slot::CNODE.cap()
}

/// Empties the event queue and prints one line per distinct (type, stream, direction, page) with its count.
fn events(w: &mut World, after: &str) -> Vec<Event> {
    let (list, overflowed) = w.smmu.drain_events();
    if list.is_empty() {
        uprintln!("A5S2   events after {}: none", after);
    }
    let mut seen: Vec<(u8, u32, bool, u64)> = Vec::new();
    for event in &list {
        let key = (event.kind, event.sid, event.write, event.addr & !0xfff);
        if !seen.contains(&key) {
            seen.push(key);
            let count = list.iter().filter(|e| (e.kind, e.sid, e.write, e.addr & !0xfff) == key).count();
            uprintln!("A5S2   events after {}: n={} type={:#04x} sid={:#x} write={} page={:#x}", after, count, key.0, key.1, key.2, key.3);
        }
    }
    if overflowed {
        uprintln!("A5S2   the event queue overflowed");
    }
    list
}

fn only_fault(list: &[Event], sid: u32, write: bool) -> bool {
    !list.is_empty() && list.iter().all(|e| e.kind == EVT_F_TRANSLATION && e.sid == sid && e.write == write && e.addr & !0xfff == IOVA_DMA)
}

/// Gives the device's stream its address space, with the server's page O mapped permanently.
pub(crate) fn configure(w: &mut World, cd: Ram) -> Result<(), Fail> {
    w.smmu.write_context(cd, ASID);
    w.smmu.map(IOVA_OUT, w.o.pa, true)?;
    w.smmu.write_stream(w.edu.sid, cd)?;
    w.smmu.invalidate_stream(w.edu.sid)?;
    w.smmu.invalidate_context(w.edu.sid)?;
    w.smmu.sync()?;
    uprintln!("A5S2 configured: stream {:#x} stage 1, asid {}; the frame under test goes at {:#x}; {:#x} -> the server's page O at physical {:#x}", w.edu.sid, ASID, IOVA_DMA, IOVA_OUT, w.o.pa);
    Ok(())
}

/// A fresh 4 KiB untyped.
fn new_untyped(w: &mut World) -> Result<sel4::cap::Untyped, Fail> {
    Ok(w.allocator.allocate(sel4::ObjectBlueprint::Untyped { size_bits: UNTYPED_BITS })?.cast())
}

/// Retypes `untyped` into one frame, maps it for the root task and returns the capability and the page.
///
/// # Safety
///
/// `untyped` must have no object in it (fresh, or just revoked), so that the frame's memory is referred to by nothing
/// else. The returned `Ram` must not be read or written after `untyped` or the frame's capability has been revoked or
/// deleted: the kernel removes the mapping with it.
unsafe fn frame_from(w: &mut World, untyped: sel4::cap::Untyped) -> Result<(sel4::cap::Granule, Ram), Fail> {
    let slot = w.slots.take()?;
    untyped.untyped_retype(&sel4::cap_type::Granule::object_blueprint(), &root().absolute_cptr_for_self(), slot, 1)?;
    let cap = sel4::init_thread::Slot::<sel4::cap_type::Granule>::from_index(slot).cap();
    // SAFETY: the frame was retyped from the untyped just now, so nothing refers to its memory; that the page is not
    // used after a revoke is this function's own contract, passed on to its caller.
    let (page, pa) = unsafe { w.mapper.map_ram(cap) }?;
    Ok((cap, Ram { page, pa: pa as u64 }))
}

/// The kernel's answer to copying the capability at `src` into a fresh slot. `Err(FailedLookup)` means the slot is
/// empty, which is what a revoked capability leaves behind.
fn try_copy(w: &mut World, src: &sel4::AbsoluteCPtr) -> Result<sel4::Result<()>, Fail> {
    let dst = sel4::init_thread::Slot::<sel4::cap_type::Null>::from_index(w.slots.take()?);
    Ok(root().absolute_cptr(dst.cptr()).copy(src, sel4::CapRights::all()))
}

/// Positive control: `page` -> the device's buffer -> `page` through the mapping under test.
fn roundtrip(w: &mut World, page: Ram, seed: u32) -> usize {
    fill(page, seed);
    dev_read(w, IOVA_DMA, BYTES);
    zero(page);
    dev_write(w, IOVA_DMA, BYTES);
    holds(page, seed)
}

/// What the two device transfers of a scenario found.
struct Probe {
    /// Words of the victim's secret that the device brought out to page O.
    leaked: usize,
    /// Words of the victim's page that the device replaced with its own pattern.
    overwritten: usize,
    /// Neither transfer through the mapping under test left an event record.
    quiet: bool,
    /// Both transfers through the mapping under test left only translation-fault records of the right stream, direction and page.
    refused: bool,
    /// The two transfers through page O, which only move the device's buffer, left no event record.
    moves_clean: bool,
}

/// The device reads the mapping under test and writes what it got to O; then it loads a pattern from O and writes it
/// to the mapping under test. `victim` is the page the reused memory now is, holding `secret`.
fn probe(w: &mut World, victim: Ram, secret: u32, attack: u32, what: &str) -> Probe {
    zero(w.o);
    dev_read(w, IOVA_DMA, BYTES);
    let read_events = events(w, "the device's read of the mapping under test");
    dev_write(w, IOVA_OUT, BYTES);
    let out_events = events(w, "the device's write of its buffer to page O");
    let leaked = holds(w.o, secret);
    fill(w.o, attack);
    dev_read(w, IOVA_OUT, BYTES);
    let in_events = events(w, "the device's read of the attack pattern from page O");
    dev_write(w, IOVA_DMA, BYTES);
    let write_events = events(w, "the device's write to the mapping under test");
    let overwritten = holds(victim, attack);
    let intact = holds(victim, secret);
    let found = Probe {
        leaked,
        overwritten,
        quiet: read_events.is_empty() && write_events.is_empty(),
        refused: only_fault(&read_events, w.edu.sid, false) && only_fault(&write_events, w.edu.sid, true),
        moves_clean: out_events.is_empty() && in_events.is_empty(),
    };
    uprintln!(
        "A5S2 {}: secret words the device read out={}/16; victim words the device overwrote={}/16 (victim still intact={}/16); transfers through the mapping left no event={}, only translation faults={}; transfers through page O left no event={}",
        what, leaked, overwritten, intact, found.quiet, found.refused, found.moves_clean
    );
    found
}

/// REACHED: the device read all of the secret and overwrote all of the page, with no event. REFUSED: it read none
/// and overwrote none, and both transfers left translation faults. Anything else is MIXED and needs explaining.
fn outcome(probe: &Probe) -> &'static str {
    match (probe.leaked, probe.overwritten) {
        (WORDS, WORDS) if probe.quiet && probe.moves_clean => "REACHED",
        (0, 0) if probe.refused && probe.moves_clean => "REFUSED",
        _ => "MIXED",
    }
}

/// The server's teardown of the mapping under test: clear the entry, invalidate, wait.
fn teardown(w: &mut World, invalidate: bool) -> Result<(), Fail> {
    w.smmu.unmap(IOVA_DMA)?;
    if invalidate {
        w.smmu.invalidate_page(ASID, IOVA_DMA)?;
    }
    w.smmu.sync()?;
    uprintln!("A5S2   teardown: table entry cleared, CMD_TLBI_NH_VA issued={}, CMD_SYNC complete", invalidate);
    Ok(())
}

pub(crate) fn run_all(w: &mut World) -> Result<(), Fail> {
    naive_frame(w)?;
    teardown_first(w)?;
    naive_kernel_object(w)
}

fn void(w: &mut World, scenario: &str, control: usize) {
    w.void += 1;
    uprintln!("A5S2 {}: VOID, the positive control moved {}/16 words", scenario, control);
}

/// Scenario A: the donor revokes its untyped while the frame is mapped for the device; the memory comes back as a
/// frame of the victim.
fn naive_frame(w: &mut World) -> Result<(), Fail> {
    let untyped = new_untyped(w)?;
    // SAFETY: the untyped is fresh. `f` is last read in the positive control, before the revoke below.
    let (frame, f) = unsafe { frame_from(w, untyped) }?;
    w.smmu.map(IOVA_DMA, f.pa, true)?;
    let control = roundtrip(w, f, 0xa100_0000);
    events(w, "scenario A's positive control");
    if control != WORDS {
        void(w, "A", control);
        return teardown(w, true);
    }
    // The server keeps a copy of the frame capability: does a copy keep the memory from being taken back?
    let copy = sel4::init_thread::Slot::<sel4::cap_type::Granule>::from_index(w.slots.take()?);
    root().absolute_cptr(copy.cptr()).copy(&root().absolute_cptr(frame.cptr()), sel4::CapRights::all())?;
    root().absolute_cptr(untyped.cptr()).revoke()?;
    // From here `f` is unmapped and must not be touched; only its physical address is used.
    let frame_after = try_copy(w, &root().absolute_cptr(frame.cptr()))?;
    let copy_after = try_copy(w, &root().absolute_cptr(copy.cptr()))?;
    // SAFETY: the untyped was revoked just above, so it is empty. `g` is last read in the probe, before the revoke
    // that ends the scenario.
    let (_reused, g) = unsafe { frame_from(w, untyped) }?;
    let cleared = zeros(g);
    uprintln!(
        "A5S2 A: positive control={}/16; after the donor's revoke: copying the frame capability: {:?}; copying the server's copy of it: {:?}; reused frame at physical {:#x}, the old frame was at {:#x} (same={}); reused frame reads as zero={}/16",
        control, frame_after, copy_after, g.pa, f.pa, g.pa == f.pa, cleared
    );
    fill(g, 0xa200_0000);
    let found = probe(w, g, 0xa200_0000, 0xa300_0000, "A");
    let valid = frame_after == Err(EMPTY_SLOT) && copy_after == Err(EMPTY_SLOT) && g.pa == f.pa && cleared == WORDS;
    uprintln!("A5S2 finding=naive-frame-reuse observed={}", if valid { outcome(&found) } else { "INVALID-SETUP" });
    teardown(w, true)?;
    root().absolute_cptr(untyped.cptr()).revoke()?;
    Ok(())
}

/// Scenario B: as A, but the server tears the mapping down before the donor revokes. The control that can come out
/// the other way. The mutant leaves the invalidation command out of the teardown.
fn teardown_first(w: &mut World) -> Result<(), Fail> {
    let untyped = new_untyped(w)?;
    // SAFETY: the untyped is fresh. `f` is last read in the positive control, before the revoke below.
    let (_frame, f) = unsafe { frame_from(w, untyped) }?;
    w.smmu.map(IOVA_DMA, f.pa, true)?;
    let control = roundtrip(w, f, 0xb100_0000);
    events(w, "scenario B's positive control");
    if control != WORDS {
        void(w, "B", control);
        return teardown(w, true);
    }
    // A kernel rule, noted on the way: while a capability to an object made from the untyped exists, the kernel does
    // not hand the untyped's memory out again. This says nothing about who should hold which capability.
    let spare = w.slots.take()?;
    let early = untyped.untyped_retype(&sel4::cap_type::Granule::object_blueprint(), &root().absolute_cptr_for_self(), spare, 1);
    uprintln!("A5S2 B: a retype of the untyped while its frame capability exists: {:?}", early);
    uprintln!("A5S2 finding=retype-while-child-exists observed={}", if early.is_err() { "REFUSED" } else { "ACCEPTED" });
    let mutant = MUTANT == Some("teardown-without-invalidation");
    if mutant {
        uprintln!("A5S2 B: MUTANT teardown-without-invalidation, CMD_TLBI_NH_VA is not issued");
    }
    teardown(w, !mutant)?;
    root().absolute_cptr(untyped.cptr()).revoke()?;
    // SAFETY: the untyped was revoked just above, so it is empty. `g` is last read in the probe, before the revoke
    // that ends the scenario.
    let (_reused, g) = unsafe { frame_from(w, untyped) }?;
    uprintln!("A5S2 B: positive control={}/16; mapping torn down, then revoked; reused frame at physical {:#x} (same as the old={})", control, g.pa, g.pa == f.pa);
    fill(g, 0xb200_0000);
    let found = probe(w, g, 0xb200_0000, 0xb300_0000, "B");
    uprintln!("A5S2 finding=teardown-then-reuse observed={}", if g.pa == f.pa { outcome(&found) } else { "INVALID-SETUP" });
    teardown(w, true)?;
    root().absolute_cptr(untyped.cptr()).revoke()?;
    Ok(())
}

/// Scenario C: as A, but the memory comes back as a kernel object, a CNode, with a capability in it. Runs last: the
/// capability the device duplicates is only half linked into the kernel's derivation list, and nothing here may delete
/// the CNode, slot 2 or the copy afterwards (a deletion would unlink through those stale links and corrupt the list).
/// No authority is created that the root task did not have: the duplicate names the same object with the same badge
/// and rights. What is shown is that it exists outside the kernel's bookkeeping.
fn naive_kernel_object(w: &mut World) -> Result<(), Fail> {
    let untyped = new_untyped(w)?;
    // SAFETY: the untyped is fresh. `f` is last read in the positive control, before the revoke below.
    let (_frame, f) = unsafe { frame_from(w, untyped) }?;
    w.smmu.map(IOVA_DMA, f.pa, true)?;
    let control = roundtrip(w, f, 0xc100_0000);
    events(w, "scenario C's positive control");
    if control != WORDS {
        void(w, "C", control);
        return teardown(w, true);
    }
    root().absolute_cptr(untyped.cptr()).revoke()?;
    // From here `f` is unmapped and must not be touched.
    let cnode_slot = w.slots.take()?;
    untyped.untyped_retype(&sel4::ObjectBlueprint::CNode { size_bits: CNODE_BITS }, &root().absolute_cptr_for_self(), cnode_slot, 1)?;
    let cnode = sel4::init_thread::Slot::<sel4::cap_type::CNode>::from_index(cnode_slot).cap();
    let notification = w.allocator.allocate_fixed_sized::<sel4::cap_type::Notification>()?;
    let inner = |slot: u64| cnode.absolute_cptr_from_bits_with_depth(slot, CNODE_BITS);
    inner(1).mint(&root().absolute_cptr(notification.cptr()), sel4::CapRights::all(), BADGE)?;
    uprintln!("A5S2 C: positive control={}/16; revoked; the untyped is now a CNode of {} slots with a notification capability (badge {:#x}) in slot 1", control, 1 << CNODE_BITS, BADGE);

    // (1) Disclosure: the device copies the first two slots out to page O.
    zero(w.o);
    dev_read(w, IOVA_DMA, BYTES);
    let read_events = events(w, "the device's read of the kernel object");
    dev_write(w, IOVA_OUT, BYTES);
    events(w, "the device's write of its buffer to page O");
    let raw: [u64; 8] = core::array::from_fn(|i| w.o.page.r64(i * 8));
    let slot0_zero = raw[..4].iter().all(|&x| x == 0);
    let slot1_words = raw[4..].iter().filter(|&&x| x != 0).count();
    let badge_seen = raw[4..].contains(&BADGE);
    uprintln!("A5S2 C: bytes of the kernel object the device read out: slot 0 = {:x?}, slot 1 = {:x?}", &raw[..4], &raw[4..]);
    uprintln!("A5S2 finding=kernel-object-disclosed read-left-no-event={} slot0-empty={} slot1-nonzero-words={}/4 badge-visible={}", read_events.is_empty(), slot0_zero, slot1_words, badge_seen);

    // (2) Duplication. Control first: slot 2 is empty, so the kernel copies nothing out of it.
    let out = sel4::init_thread::Slot::<sel4::cap_type::Notification>::from_index(w.slots.take()?);
    let before = root().absolute_cptr(out.cptr()).copy(&inner(2), sel4::CapRights::all());
    // The device copies the 32 bytes of slot 1 onto slot 2.
    dev_read(w, IOVA_DMA + SLOT_BYTES, SLOT_BYTES);
    dev_write(w, IOVA_DMA + 2 * SLOT_BYTES, SLOT_BYTES);
    let copy_events = events(w, "the device's copy of slot 1 onto slot 2");
    let after = root().absolute_cptr(out.cptr()).copy(&inner(2), sel4::CapRights::all());
    let mut delivered = 0;
    if after.is_ok() {
        out.cap().signal();
        delivered = notification.poll().1;
    }
    uprintln!("A5S2 C: copying a capability out of slot 2 before the device wrote it: {:?}; after: {:?}; a signal through that copy arrived with badge {:#x}", before, after, delivered);
    uprintln!(
        "A5S2 finding=capability-duplicated-by-dma device-copy-left-no-event={} copy-out-refused-before={} copy-out-accepted-after={} signal-arrived-with-the-badge={}",
        copy_events.is_empty(), before == Err(EMPTY_SLOT), after.is_ok(), delivered == BADGE
    );

    // (3) Revocation of the origin. Control: a copy of slot 1 that the kernel made itself, which the revoke must remove.
    let kernel_copy = sel4::init_thread::Slot::<sel4::cap_type::Notification>::from_index(w.slots.take()?);
    root().absolute_cptr(kernel_copy.cptr()).copy(&inner(1), sel4::CapRights::all())?;
    kernel_copy.cap().signal();
    let kernel_copy_worked = notification.poll().1;
    root().absolute_cptr(notification.cptr()).revoke()?;
    let minted_after = try_copy(w, &inner(1))?;
    let kernel_copy_after = try_copy(w, &root().absolute_cptr(kernel_copy.cptr()))?;
    let mut survived = 0;
    if after.is_ok() {
        out.cap().signal();
        survived = notification.poll().1;
    }
    uprintln!(
        "A5S2 C: a copy of slot 1 made by the kernel delivered a signal with badge {:#x} before the revoke; after revoking the notification's original capability: copying the minted capability in slot 1: {:?}; copying the kernel-made copy: {:?}; a signal through the device-made duplicate arrived with badge {:#x}",
        kernel_copy_worked, minted_after, kernel_copy_after, survived
    );
    uprintln!(
        "A5S2 finding=dma-duplicate-survives-revocation kernel-made-copy-worked-before={} minted-capability-removed={} kernel-made-copy-removed={} dma-duplicate-still-works={}",
        kernel_copy_worked == BADGE, minted_after == Err(EMPTY_SLOT), kernel_copy_after == Err(EMPTY_SLOT), survived == BADGE
    );
    Ok(())
}
