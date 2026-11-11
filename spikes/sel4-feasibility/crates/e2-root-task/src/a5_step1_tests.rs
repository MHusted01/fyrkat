//
// SPDX-License-Identifier: BSD-2-Clause
//
// A5 step 1: the tests. Each has the device attempt transfers of 64 bytes between its internal buffer and an address,
// and then looks at two things the device cannot fake: the content of the pages involved, read by the root task
// through its own mappings, and the records the SMMU put in its event queue.
//

use alloc::vec::Vec;

use crate::smmuv3::{CR0_ALL, EVT_C_BAD_STE, EVT_F_PERMISSION, EVT_F_TRANSLATION, Event, GBPA_ABORT, IOVA_BASE, Ram};
use crate::{Fail, MUTANT, World, uprintln};

const WORDS: usize = 16;
const BYTES: u64 = 64;
/// Address-space tag of the one stage-1 address space.
const ASID: u16 = 7;
/// I/O virtual addresses of the experiment: mapped read-write to page P, mapped read-only to page R, and never mapped.
const IOVA_RW: u64 = IOVA_BASE;
const IOVA_RO: u64 = IOVA_BASE + 0x1000;
const IOVA_UNMAPPED: u64 = IOVA_BASE + 0x2000;

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

/// How many of the first sixteen words of the page hold the pattern of `seed`.
fn holds(ram: Ram, seed: u32) -> usize {
    (0..WORDS).filter(|&i| ram.page.r32(i * 4) == seed.wrapping_add(i as u32)).count()
}

fn zeros(ram: Ram) -> usize {
    (0..WORDS).filter(|&i| ram.page.r32(i * 4) == 0).count()
}

/// Empties the event queue and prints one line per distinct (type, stream, direction, page) with its count.
fn events(w: &mut World, after: &str) -> Vec<Event> {
    let (list, overflowed) = w.smmu.drain_events();
    if list.is_empty() {
        uprintln!("A5S1   events after {}: none", after);
    }
    let mut seen: Vec<(u8, u32, bool, u64)> = Vec::new();
    for event in &list {
        let key = (event.kind, event.sid, event.write, event.addr & !0xfff);
        if !seen.contains(&key) {
            seen.push(key);
            let count = list.iter().filter(|e| (e.kind, e.sid, e.write, e.addr & !0xfff) == key).count();
            uprintln!("A5S1   events after {}: n={} type={:#04x} sid={:#x} write={} page={:#x}", after, count, key.0, key.1, key.2, key.3);
        }
    }
    if overflowed {
        uprintln!("A5S1   the event queue overflowed");
    }
    list
}

/// There is at least one event and every one is a configuration event of `kind` for stream `sid`.
fn only_kind(list: &[Event], kind: u8, sid: u32) -> bool {
    !list.is_empty() && list.iter().all(|e| e.kind == kind && e.sid == sid)
}

/// There is at least one event and every one is a fault of `kind` for stream `sid`, in the given direction, in `page`.
fn only_fault(list: &[Event], kind: u8, sid: u32, write: bool, page: u64) -> bool {
    !list.is_empty() && list.iter().all(|e| e.kind == kind && e.sid == sid && e.write == write && e.addr & !0xfff == page)
}

/// Page P -> the device's buffer -> page P, through the read-write mapping. Returns how many words came back.
fn roundtrip(w: &World, seed: u32) -> usize {
    fill(w.p, seed);
    w.edu.read_from(IOVA_RW, BYTES);
    zero(w.p);
    w.edu.write_to(IOVA_RW, BYTES);
    holds(w.p, seed)
}

pub(crate) fn run_all(w: &mut World) -> Result<(), Fail> {
    let ok = unconfigured(w);
    w.verdict("unconfigured-stream-denied", ok);
    configure(w)?;
    let ok = mapped(w);
    w.verdict("mapped-iova-translated", ok);
    let ok = unmapped(w);
    w.verdict("unmapped-iova-denied", ok);
    let ok = physical(w);
    w.verdict("physical-address-denied", ok);
    let ok = no_read(w);
    w.verdict("unmapped-memory-not-readable", ok);
    let ok = read_only(w);
    w.verdict("read-only-mapping-enforced", ok);
    let ok = other_stream(w);
    w.verdict("other-stream-denied", ok);
    let ok = unmap(w)?;
    w.verdict("unmap-effective-after-invalidation", ok);
    let ok = stream_removal(w)?;
    w.verdict("stream-removal-effective-after-invalidation", ok);
    let ok = global_state(w);
    w.verdict("global-state-unchanged", ok);
    Ok(())
}

/// The SMMU is enabled and no stream is configured: the device must reach nothing, by I/O virtual or physical address.
fn unconfigured(w: &mut World) -> bool {
    fill(w.p, 0x1100_0000);
    let done_a = w.edu.write_to(IOVA_RW, BYTES);
    let first = events(w, "a write to the future read-write address");
    let done_b = w.edu.write_to(w.p.pa, BYTES);
    let second = events(w, "a write to page P's physical address");
    let intact = holds(w.p, 0x1100_0000);
    uprintln!("A5S1 unconfigured: transfers finished={} page P intact={}/16", done_a && done_b, intact);
    done_a && done_b && intact == WORDS && only_kind(&first, EVT_C_BAD_STE, w.edu.sid) && only_kind(&second, EVT_C_BAD_STE, w.edu.sid)
}

/// Gives the device's stream its address space, and tells the SMMU (stream entry, context descriptor, then a sync).
fn configure(w: &mut World) -> Result<(), Fail> {
    w.smmu.write_context(w.cd, ASID);
    w.smmu.map(IOVA_RW, w.p.pa, true)?;
    w.smmu.map(IOVA_RO, w.r.pa, MUTANT == Some("rw-readonly"))?;
    if MUTANT == Some("map-unmapped") {
        w.smmu.map(IOVA_UNMAPPED, w.q.pa, true)?;
    }
    w.smmu.write_stream(w.edu.sid, w.cd)?;
    w.smmu.invalidate_stream(w.edu.sid)?;
    w.smmu.invalidate_context(w.edu.sid)?;
    if MUTANT == Some("second-stream-configured") {
        uprintln!("A5S1 configure: MUTANT second-stream-configured, stream {:#x} gets the same address space", w.other.sid);
        w.smmu.write_stream(w.other.sid, w.cd)?;
        w.smmu.invalidate_stream(w.other.sid)?;
    }
    w.smmu.sync()?;
    uprintln!(
        "A5S1 configured: stream {:#x} stage 1, asid {}; {:#x} -> P at physical {:#x} read-write; {:#x} -> R at physical {:#x} read-only; {:#x} unmapped; guard Q at physical {:#x}",
        w.edu.sid, ASID, IOVA_RW, w.p.pa, IOVA_RO, w.r.pa, IOVA_UNMAPPED, w.q.pa
    );
    Ok(())
}

/// A transfer through the mapped address reaches page P in both directions. The I/O virtual address is not P's
/// physical address, so the data can only have arrived by translation.
fn mapped(w: &mut World) -> bool {
    let back = roundtrip(w, 0x2200_0000);
    let list = events(w, "the round trip through the read-write mapping");
    uprintln!("A5S1 mapped: {}/16 words made the round trip; the address used ({:#x}) differs from P's physical address ({:#x})={}", back, IOVA_RW, w.p.pa, IOVA_RW != w.p.pa);
    back == WORDS && list.is_empty() && IOVA_RW != w.p.pa
}

/// A write to an address of the window that has no mapping lands nowhere and is reported as a translation fault.
fn unmapped(w: &mut World) -> bool {
    fill(w.q, 0x3300_0000);
    zero(w.p);
    let done = w.edu.write_to(IOVA_UNMAPPED, BYTES);
    let list = events(w, "a write to the unmapped address");
    let (guard, target) = (holds(w.q, 0x3300_0000), zeros(w.p));
    uprintln!("A5S1 unmapped: transfer finished={} guard page Q intact={}/16 page P still zero={}/16", done, guard, target);
    done && guard == WORDS && target == WORDS && only_fault(&list, EVT_F_TRANSLATION, w.edu.sid, true, IOVA_UNMAPPED)
}

/// A write that names the guard page by its physical address lands nowhere: the device has no identity path.
fn physical(w: &mut World) -> bool {
    fill(w.q, 0x3300_0000);
    let done = w.edu.write_to(w.q.pa, BYTES);
    let list = events(w, "a write to guard page Q's physical address");
    let guard = holds(w.q, 0x3300_0000);
    uprintln!("A5S1 physical: transfer finished={} guard page Q intact={}/16", done, guard);
    done && guard == WORDS && only_fault(&list, EVT_F_TRANSLATION, w.edu.sid, true, w.q.pa & !0xfff)
}

/// The device cannot read the guard page either: after an attempt, what it can write back into P is not Q's content.
fn no_read(w: &mut World) -> bool {
    fill(w.q, 0x4400_0000);
    let done = w.edu.read_from(w.q.pa, BYTES);
    let list = events(w, "a read of guard page Q's physical address");
    zero(w.p);
    w.edu.write_to(IOVA_RW, BYTES);
    let extra = events(w, "writing the device's buffer back to P");
    let (leaked, kept, zeroed) = (holds(w.p, 0x4400_0000), holds(w.p, 0x2200_0000), zeros(w.p));
    uprintln!("A5S1 no-read: transfer finished={} words of Q's content that reached P={}/16 (the buffer held: earlier pattern {}/16, zero {}/16)", done, leaked, kept, zeroed);
    done && leaked == 0 && extra.is_empty() && only_fault(&list, EVT_F_TRANSLATION, w.edu.sid, false, w.q.pa & !0xfff)
}

/// Through the read-only mapping the device can read page R and cannot write it; the refusal is a permission fault.
fn read_only(w: &mut World) -> bool {
    fill(w.r, 0x5500_0000);
    w.edu.read_from(IOVA_RO, BYTES);
    zero(w.p);
    w.edu.write_to(IOVA_RW, BYTES);
    let quiet = events(w, "a read through the read-only mapping");
    let read = holds(w.p, 0x5500_0000);
    fill(w.p, 0x6600_0000);
    w.edu.read_from(IOVA_RW, BYTES);
    let done = w.edu.write_to(IOVA_RO, BYTES);
    let list = events(w, "a write through the read-only mapping");
    let unchanged = holds(w.r, 0x5500_0000);
    uprintln!("A5S1 read-only: read through it delivered={}/16 write finished={} page R unchanged={}/16", read, done, unchanged);
    read == WORDS && quiet.is_empty() && done && unchanged == WORDS && only_fault(&list, EVT_F_PERMISSION, w.edu.sid, true, IOVA_RO)
}

/// The second device uses the address that works for the first and reaches nothing, while the first still does: the
/// decision is made per stream, not for the whole SMMU.
fn other_stream(w: &mut World) -> bool {
    fill(w.p, 0x7700_0000);
    let done = w.other.write_to(IOVA_RW, BYTES);
    let list = events(w, "the unconfigured device's write to the read-write address");
    let intact = holds(w.p, 0x7700_0000);
    let back = roundtrip(w, 0x8800_0000);
    let quiet = events(w, "the configured device's round trip straight after");
    uprintln!("A5S1 other-stream: transfer finished={} page P intact={}/16; the configured device's round trip={}/16", done, intact, back);
    done && intact == WORDS && only_kind(&list, EVT_C_BAD_STE, w.other.sid) && back == WORDS && quiet.is_empty()
}

/// Removing the mapping. Between clearing the table entry and the invalidation command the SMMU may still translate
/// from its cache (recorded, not judged); after the command and its sync the transfer must be refused.
fn unmap(w: &mut World) -> Result<bool, Fail> {
    // The device's buffer holds the pattern 0x88000000 from the round trip above.
    zero(w.p);
    w.smmu.unmap(IOVA_RW)?;
    w.edu.write_to(IOVA_RW, BYTES);
    let stale = holds(w.p, 0x8800_0000);
    events(w, "a write after the entry was cleared, before any invalidation");
    uprintln!("A5S1 unmap: entry cleared, no invalidation yet: the write still landed={}/16 words", stale);
    zero(w.p);
    if MUTANT == Some("skip-tlbi") {
        uprintln!("A5S1 unmap: MUTANT skip-tlbi, CMD_TLBI_NH_VA is not issued");
    } else {
        w.smmu.invalidate_page(ASID, IOVA_RW)?;
    }
    w.smmu.sync()?;
    let done = w.edu.write_to(IOVA_RW, BYTES);
    let list = events(w, "a write after the invalidation and its sync");
    let (landed, clean) = (holds(w.p, 0x8800_0000), zeros(w.p));
    uprintln!("A5S1 unmap: after the invalidation: transfer finished={} words landed={}/16 page P still zero={}/16", done, landed, clean);
    Ok(done && landed == 0 && clean == WORDS && only_fault(&list, EVT_F_TRANSLATION, w.edu.sid, true, IOVA_RW))
}

/// Removing the stream. The mapping is restored and shown to work, then the stream table entry is made invalid; as
/// above, the transfer must be refused once CMD_CFGI_STE and its sync have completed.
fn stream_removal(w: &mut World) -> Result<bool, Fail> {
    w.smmu.map(IOVA_RW, w.p.pa, true)?;
    let back = roundtrip(w, 0x9900_0000);
    events(w, "the round trip through the restored mapping");
    zero(w.p);
    w.smmu.clear_stream(w.edu.sid)?;
    w.edu.write_to(IOVA_RW, BYTES);
    let stale = holds(w.p, 0x9900_0000);
    events(w, "a write after the stream entry was cleared, before any invalidation");
    uprintln!("A5S1 stream-removal: restored mapping round trip={}/16; entry cleared, no invalidation yet: the write still landed={}/16 words", back, stale);
    zero(w.p);
    if MUTANT == Some("skip-cfgi") {
        uprintln!("A5S1 stream-removal: MUTANT skip-cfgi, CMD_CFGI_STE is not issued");
    } else {
        w.smmu.invalidate_stream(w.edu.sid)?;
    }
    w.smmu.sync()?;
    let done = w.edu.write_to(IOVA_RW, BYTES);
    let list = events(w, "a write after the stream invalidation and its sync");
    let (landed, clean) = (holds(w.p, 0x9900_0000), zeros(w.p));
    uprintln!("A5S1 stream-removal: after the invalidation: transfer finished={} words landed={}/16 page P still zero={}/16", done, landed, clean);
    Ok(back == WORDS && done && landed == 0 && clean == WORDS && only_kind(&list, EVT_C_BAD_STE, w.edu.sid))
}

/// Nothing above was decided by the SMMU's global controls: it is still enabled, its global abort bit was never set,
/// and it reports no global error.
fn global_state(w: &mut World) -> bool {
    let state = w.smmu.state();
    uprintln!("A5S1 global: CR0={:#x} CR0ACK={:#x} GBPA={:#x} (abort bit set={}) GERROR^GERRORN={:#x}", state[3], state[4], state[5], state[5] & GBPA_ABORT != 0, state[6]);
    state[3] == CR0_ALL && state[4] == CR0_ALL && state[5] & GBPA_ABORT == 0 && state[6] == 0
}
