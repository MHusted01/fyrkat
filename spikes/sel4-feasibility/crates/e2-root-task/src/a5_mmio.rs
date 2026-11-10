//
// SPDX-License-Identifier: BSD-2-Clause
//
// Reaching device memory from a root task (written for A5 step 0; included by every binary that drives a device). It retypes device frames
// out of the device untypeds of the boot information and maps them, one page at a time, into the root task's own address
// space, and gives volatile access to the mapped words. It also maps ordinary frames (for memory a device reaches by DMA). The page-table creation follows `child_vspace.rs` (copied, not shared,
// because that file's helper is private and E2's sources are not touched).
//

use core::ptr;
use core::sync::atomic::{AtomicBool, AtomicUsize, Ordering};

use sel4::CapTypeForObjectOfFixedSize;

use crate::{Fail, ObjectAllocator};

pub(crate) const PAGE: usize = 4096;
/// The root task's own free virtual range for device pages: 2 MiB from 1 GiB, under one page table.
const VA_BASE: usize = 0x4000_0000;
const VA_PAGES: usize = 512;

pub(crate) struct DeviceMapper {
    /// Next free slot, counting down from the end of the root CNode's empty range (the allocator counts up from its start).
    slot_cursor: usize,
    /// Per device untyped (index into the boot information): how many bytes of it have been retyped so far.
    consumed: alloc::vec::Vec<(usize, usize)>,
    next_va: usize,
}

/// A page mapped read-write in this task by `DeviceMapper`, which is the only code that creates one from a mapping. The
/// accessors are safe for every argument: the offset is reduced to an aligned offset inside the page, so no call can reach
/// outside the mapping. Call sites pass aligned in-page offsets, for which the reduction changes nothing.
#[derive(Clone, Copy)]
pub(crate) struct Page {
    va: usize,
}

/// A page mapped read-only in this task by `DeviceMapper`. It offers no write.
#[derive(Clone, Copy)]
pub(crate) struct ReadOnlyPage {
    va: usize,
}

/// Set by the first `DeviceMapper::new`: there may be only one mapper, because a second would hand out the same addresses.
static MAPPER_EXISTS: AtomicBool = AtomicBool::new(false);
/// How many accesses were asked for at an offset that was not an aligned offset inside the page. Such an access is still
/// made inside the page (so it is harmless to memory), but it is a bug of the caller: every program that uses this module
/// prints this count at its end, and its evidence requires it to be 0.
static RANGE_ERRORS: AtomicUsize = AtomicUsize::new(0);

pub(crate) fn range_errors() -> usize {
    RANGE_ERRORS.load(Ordering::Relaxed)
}

/// Reduces `off` to a multiple of `width` (4 or 8) that leaves room for one access of that width inside the page, and
/// counts the call if that changed anything.
fn in_page(off: usize, width: usize) -> usize {
    let reduced = off & (PAGE - width);
    if reduced != off {
        RANGE_ERRORS.fetch_add(1, Ordering::Relaxed);
    }
    reduced
}

impl Page {
    /// The virtual address of the page, for handing to code that cannot hold a `Page` (a worker thread's argument, a static).
    pub(crate) fn addr(self) -> usize {
        self.va
    }

    /// Rebuilds a `Page` from an address.
    ///
    /// # Safety
    ///
    /// `addr` must be the value `Page::addr` returned for a page that is still mapped read-write in this address space.
    pub(crate) unsafe fn from_addr(addr: usize) -> Self {
        Self { va: addr }
    }

    /// Reads the 32-bit word at byte offset `off` of the page (reduced to a 4-aligned offset inside the page).
    pub(crate) fn r32(self, off: usize) -> u32 {
        // SAFETY: a `Page` exists only for a page that the one `DeviceMapper` mapped readable and writable at `va`,
        // page-aligned, at an address it never reuses (or, through `from_addr`, one whose caller vouches for the
        // same); `in_page` keeps the 4-byte access inside that page and 4-aligned; a volatile read is the required way
        // to read device registers. That the page is still mapped and that no Rust reference covers its memory are
        // the obligations of whoever created it: `map_device` maps frames it has itself retyped from device untypeds
        // and keeps, and `map_ram` is an `unsafe fn` whose caller takes both obligations for an ordinary frame.
        unsafe { ptr::read_volatile((self.va + in_page(off, 4)) as *const u32) }
    }

    pub(crate) fn w32(self, off: usize, value: u32) {
        // SAFETY: as `r32`; the page is mapped writable.
        unsafe { ptr::write_volatile((self.va + in_page(off, 4)) as *mut u32, value) }
    }

    /// Reads the 64-bit word at byte offset `off` (reduced to an 8-aligned offset inside the page).
    pub(crate) fn r64(self, off: usize) -> u64 {
        // SAFETY: as `r32`, with an 8-byte access that `in_page` keeps inside the page and 8-aligned.
        unsafe { ptr::read_volatile((self.va + in_page(off, 8)) as *const u64) }
    }

    pub(crate) fn w64(self, off: usize, value: u64) {
        // SAFETY: as `r64`; the page is mapped writable.
        unsafe { ptr::write_volatile((self.va + in_page(off, 8)) as *mut u64, value) }
    }
}

impl ReadOnlyPage {
    pub(crate) fn addr(self) -> usize {
        self.va
    }
}

/// Completes every earlier memory access of this thread before the next instruction (`dsb sy`). Used between writing data a
/// device will read by DMA and telling the device to start, and between the device's completion and reading what it wrote.
/// Under QEMU it changes nothing; it is here so that the sequence is the one hardware needs.
pub(crate) fn barrier() {
    // SAFETY: `dsb sy` is a barrier instruction available at EL0; it reads and writes no register and no memory.
    unsafe { core::arch::asm!("dsb sy", options(nostack, preserves_flags)) }
}

impl DeviceMapper {
    pub(crate) fn new(bootinfo: &sel4::BootInfo, allocator: &mut ObjectAllocator) -> Result<Self, Fail> {
        if MAPPER_EXISTS.swap(true, Ordering::AcqRel) {
            return Err(Fail::Check("a device mapper already exists"));
        }
        let vspace = sel4::init_thread::slot::VSPACE.cap();
        for level in 1..sel4::vspace_levels::NUM_LEVELS {
            let span = 1usize << sel4::vspace_levels::span_bits(level);
            let ty = sel4::TranslationTableObjectType::from_level(level).ok_or(Fail::Layout)?;
            let mut addr = VA_BASE & !(span - 1);
            while addr < VA_BASE + VA_PAGES * PAGE {
                let result = allocator
                    .allocate(ty.blueprint())?
                    .cast::<sel4::cap_type::UnspecifiedIntermediateTranslationTable>()
                    .generic_intermediate_translation_table_map(ty, vspace, addr, sel4::VmAttributes::default());
                match result {
                    // A table for this range already exists (the image's): fine.
                    Ok(()) | Err(sel4::Error::DeleteFirst) => {}
                    Err(e) => return Err(Fail::Sel4(e)),
                }
                addr += span;
            }
        }
        Ok(Self { slot_cursor: bootinfo.empty().range().end - 1, consumed: alloc::vec::Vec::new(), next_va: VA_BASE })
    }

    /// The device untyped that contains `paddr`, as (index in the boot information, its physical address, its size in bytes).
    pub(crate) fn device_untyped_for(bootinfo: &sel4::BootInfo, paddr: usize) -> Option<(usize, usize, usize)> {
        bootinfo.untyped_list().iter().enumerate().find_map(|(i, d)| {
            let (base, size) = (d.paddr(), 1usize << d.size_bits());
            (d.is_device() && paddr >= base && paddr < base + size).then_some((i, base, size))
        })
    }

    /// Maps the 4 KiB device page at physical address `paddr` read-write into this task. Pages of one untyped must be asked
    /// for in ascending order, because an untyped can only be retyped forwards.
    pub(crate) fn map_device(&mut self, bootinfo: &sel4::BootInfo, paddr: usize) -> Result<Page, Fail> {
        let (index, base, _size) = Self::device_untyped_for(bootinfo, paddr).ok_or(Fail::Check("no device untyped covers the address"))?;
        let offset = paddr - base;
        let mut done = self.consumed.iter().find(|(i, _)| *i == index).map_or(0, |(_, c)| *c);
        if offset < done {
            return Err(Fail::Check("the untyped is already retyped past the address"));
        }
        let ut = bootinfo.untyped().index(index).cap();
        let cnode = sel4::init_thread::slot::CNODE.cap().absolute_cptr_for_self();
        // A long way to go (a big untyped such as 0x20000000 + 0x20000000 holds the ECAM near its end): carve it into aligned
        // power-of-two child untypeds, which moves its watermark without one slot per page. The children are not kept.
        while offset - done >= 256 * PAGE {
            let mut bits = 47usize;
            while bits > 12 && (done % (1usize << bits) != 0 || done + (1usize << bits) > offset) {
                bits -= 1;
            }
            if self.slot_cursor < bootinfo.empty().range().start + 1024 {
                return Err(Fail::OutOfSlots);
            }
            ut.untyped_retype(&sel4::ObjectBlueprint::Untyped { size_bits: bits }, &cnode, self.slot_cursor, 1)?;
            self.slot_cursor -= 1;
            done += 1usize << bits;
        }
        let count = (offset - done) / PAGE + 1;
        if self.slot_cursor < bootinfo.empty().range().start + count + 1024 {
            return Err(Fail::OutOfSlots);
        }
        let first = self.slot_cursor + 1 - count;
        self.slot_cursor = first - 1;
        let blueprint = sel4::cap_type::Granule::object_blueprint();
        ut.untyped_retype(&blueprint, &cnode, first, count)?;
        match self.consumed.iter_mut().find(|(i, _)| *i == index) {
            Some(entry) => entry.1 = offset + PAGE,
            None => self.consumed.push((index, offset + PAGE)),
        }
        let frame = sel4::init_thread::Slot::<sel4::cap_type::Granule>::from_index(first + count - 1).cap();
        // Device registers are mapped without the cacheable attribute, which makes the kernel use a device memory type
        // (`src/arch/arm/64/kernel/vspace.c`, `makeUserPagePTE`); the default attributes would map them as cacheable
        // ordinary memory. QEMU does not model the difference, so this is not validated by any run here.
        let va = self.map_with(frame, sel4::CapRights::read_write(), sel4::VmAttributes::NONE)?;
        Ok(Page { va })
    }

    /// Maps an ordinary frame read-write, and returns its page and its physical address.
    ///
    /// # Safety
    ///
    /// `frame` must be a frame whose memory no Rust reference or object covers (a frame freshly retyped from an untyped,
    /// or a copy of the capability of such a frame; never a frame of this task's own image). The returned `Page` must not
    /// be used after the frame's capability has been revoked or deleted, or the frame unmapped: the mapping is then gone.
    pub(crate) unsafe fn map_ram(&mut self, frame: sel4::cap::Granule) -> Result<(Page, usize), Fail> {
        let va = self.map_with(frame, sel4::CapRights::read_write(), sel4::VmAttributes::default())?;
        Ok((Page { va }, frame.frame_get_address()?))
    }

    /// Maps a frame capability read-only at the next free page of the window. Used with a copy of a capability whose
    /// original is mapped read-write, to give a second, read-only view of the same memory.
    pub(crate) fn map_read_only(&mut self, frame: sel4::cap::Granule) -> Result<ReadOnlyPage, Fail> {
        let va = self.map_with(frame, sel4::CapRights::read_only(), sel4::VmAttributes::default())?;
        Ok(ReadOnlyPage { va })
    }

    fn map_with(&mut self, frame: sel4::cap::Granule, rights: sel4::CapRights, attributes: sel4::VmAttributes) -> Result<usize, Fail> {
        if self.next_va >= VA_BASE + VA_PAGES * PAGE {
            return Err(Fail::OutOfSlots);
        }
        let va = self.next_va;
        self.next_va += PAGE;
        frame.frame_map(sel4::init_thread::slot::VSPACE.cap(), va, rights, attributes)?;
        Ok(va)
    }
}
