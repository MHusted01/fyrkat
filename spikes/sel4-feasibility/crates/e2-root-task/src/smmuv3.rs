//
// SPDX-License-Identifier: BSD-2-Clause
//
// A5 step 1: a minimal user-level SMMUv3 driver, enough to give one PCI function a stage-1 address space of 4 KiB pages
// and to take it away again. One linear stream table, one context descriptor per configured stream (no substreams), one
// translation table of three levels that covers a single 2 MiB window of I/O virtual addresses, a command queue and a
// polled event queue. No interrupts, no stage 2, no two-level stream table, no error recovery.
//
// Formats: Arm IHI 0070 (SMMUv3 architecture specification), the chapters on commands, data structure formats, the
// register map and event records. Every field position used here was also read in QEMU 11.1.3's own definitions
// (`include/hw/arm/smmuv3-common.h`, `hw/arm/smmuv3-internal.h`), because QEMU's model is what this code has been run
// against; it has never driven hardware. QEMU-specific limits it has to respect are marked "QEMU:".
//
// The driver never invalidates on its own: changing a structure and telling the SMMU about it are separate calls, so
// that an experiment can leave the second one out and observe the difference.
//

use alloc::vec::Vec;

use crate::a5_mmio::{DeviceMapper, PAGE, Page, barrier};
use crate::{Fail, ObjectAllocator};

/// SMMUv3 register frame on QEMU `virt`: page 0 at 0x09050000, page 1 (the event queue indices) 64 KiB above it.
pub(crate) const SMMU_PADDR: usize = 0x0905_0000;
const PAGE1_OFFSET: usize = 0x1_0000;

const IDR0: usize = 0x00;
const IDR1: usize = 0x04;
const IDR5: usize = 0x14;
const CR0: usize = 0x20;
const CR0ACK: usize = 0x24;
const CR1: usize = 0x28;
const CR2: usize = 0x2c;
const GBPA: usize = 0x44;
const GERROR: usize = 0x60;
const GERRORN: usize = 0x64;
const STRTAB_BASE: usize = 0x80;
const STRTAB_BASE_CFG: usize = 0x88;
const CMDQ_BASE: usize = 0x90;
const CMDQ_PROD: usize = 0x98;
const CMDQ_CONS: usize = 0x9c;
const EVENTQ_BASE: usize = 0xa0;
/// In page 1.
const EVENTQ_PROD: usize = 0xa8;
const EVENTQ_CONS: usize = 0xac;

const CR0_SMMUEN: u32 = 1 << 0;
const CR0_EVENTQEN: u32 = 1 << 2;
const CR0_CMDQEN: u32 = 1 << 3;
pub(crate) const CR0_ALL: u32 = CR0_SMMUEN | CR0_EVENTQEN | CR0_CMDQEN;
pub(crate) const GBPA_ABORT: u32 = 1 << 20;
const IDR0_S1P: u32 = 1 << 1;
/// The SMMU's own accesses to its tables and queues are coherent with the processor's caches.
const IDR0_COHACC: u32 = 1 << 4;
const IDR5_GRAN4K: u32 = 1 << 4;
/// Read-allocate hint of the table and queue base registers (bit 62).
const BASE_RA: u64 = 1 << 62;

/// The stream table has 2^6 entries of 64 bytes: one page, stream ids 0 to 63.
const STRTAB_LOG2: u32 = 6;
const STE_BYTES: usize = 64;
/// The command queue has 2^8 entries of 16 bytes and the event queue 2^7 entries of 32 bytes: one page each.
const CMDQ_LOG2: u32 = 8;
const CMD_BYTES: usize = 16;
const EVENTQ_LOG2: u32 = 7;
const EVENT_BYTES: usize = 32;

const CMD_CFGI_STE: u32 = 0x03;
const CMD_CFGI_STE_RANGE: u32 = 0x04;
const CMD_CFGI_CD: u32 = 0x05;
const CMD_TLBI_NH_VA: u32 = 0x12;
const CMD_TLBI_NSNH_ALL: u32 = 0x30;
const CMD_SYNC: u32 = 0x46;

/// Event record types (the low byte of an event).
pub(crate) const EVT_C_BAD_STE: u8 = 0x04;
pub(crate) const EVT_F_TRANSLATION: u8 = 0x10;
pub(crate) const EVT_F_PERMISSION: u8 = 0x13;

/// The one window of I/O virtual addresses this driver can map: 2 MiB from 4 GiB (one level-3 table). On the machine
/// these experiments run on (QEMU `virt` with `highmem=off` and 1 GiB of RAM) nothing has a physical address there:
/// devices are below 1 GiB and RAM ends at 2 GiB. So an I/O virtual address of the window is never also the physical
/// address of RAM or of a device, and a transfer that was not translated cannot land on anything. A device must be
/// able to name 33-bit addresses to use it (edu's default 28-bit mask is not enough).
pub(crate) const IOVA_BASE: u64 = 0x1_0000_0000;
const IOVA_SPAN: u64 = 512 * PAGE as u64;
/// Stage-1 input size: 39 bits (T0SZ 25), so a walk starts at level 1 and has three levels.
const T0SZ: u32 = 25;

const POLL_LIMIT: u32 = 1_000_000;

/// One page of ordinary memory the SMMU reads or writes by itself, with its physical address.
#[derive(Clone, Copy)]
pub(crate) struct Ram {
    pub(crate) page: Page,
    pub(crate) pa: u64,
}

impl Ram {
    /// A new frame from the allocator, mapped for this task. Its capability stays in the root CNode, and neither it nor
    /// an ancestor of it is ever revoked or deleted, so the page stays valid.
    pub(crate) fn new(mapper: &mut DeviceMapper, allocator: &mut ObjectAllocator) -> Result<Self, Fail> {
        let frame = allocator.allocate_fixed_sized::<sel4::cap_type::Granule>()?;
        // SAFETY: the frame was retyped just now, so nothing refers to its memory. No program here revokes or deletes
        // this capability or an ancestor of it: the frame comes straight from the allocator's large untyped, which is
        // never revoked. (The A5 step 2 experiment does revoke, but only small untypeds and a notification that it
        // allocates for that purpose, and the frames it makes from those untypeds are mapped by its own code, not here.)
        let (page, pa) = unsafe { mapper.map_ram(frame) }?;
        Ok(Self { page, pa: pa as u64 })
    }
}

/// One record of the event queue, reduced to what the experiments look at.
#[derive(Clone, Copy, Debug)]
pub(crate) struct Event {
    pub(crate) kind: u8,
    pub(crate) sid: u32,
    /// The faulting access was a write (the record's RnW bit is 0). Meaningful for translation-related events only.
    pub(crate) write: bool,
    /// The input address of the faulting access. Meaningful for translation-related events only.
    pub(crate) addr: u64,
}

pub(crate) struct Smmu {
    regs: Page,
    regs1: Page,
    strtab: Ram,
    cmdq: Ram,
    eventq: Ram,
    /// Translation tables of the single address space: level 1, level 2, level 3.
    tables: [Ram; 3],
    cmd_prod: u32,
    event_cons: u32,
}

impl Smmu {
    /// Maps the two register pages and allocates the memory the SMMU will read. Changes nothing in the SMMU.
    pub(crate) fn new(bootinfo: &sel4::BootInfo, mapper: &mut DeviceMapper, allocator: &mut ObjectAllocator) -> Result<Self, Fail> {
        let regs = mapper.map_device(bootinfo, SMMU_PADDR)?;
        let regs1 = mapper.map_device(bootinfo, SMMU_PADDR + PAGE1_OFFSET)?;
        let mut ram = || Ram::new(mapper, allocator);
        let (strtab, cmdq, eventq) = (ram()?, ram()?, ram()?);
        let tables = [ram()?, ram()?, ram()?];
        Ok(Self { regs, regs1, strtab, cmdq, eventq, tables, cmd_prod: 0, event_cons: 0 })
    }

    pub(crate) fn reg(&self, offset: usize) -> u32 {
        self.regs.r32(offset)
    }

    /// (IDR0, IDR1, IDR5, CR0, CR0ACK, GBPA, GERROR xor GERRORN): what the log records before and after.
    pub(crate) fn state(&self) -> [u32; 7] {
        [self.reg(IDR0), self.reg(IDR1), self.reg(IDR5), self.reg(CR0), self.reg(CR0ACK), self.reg(GBPA), self.reg(GERROR) ^ self.reg(GERRORN)]
    }

    /// Programs the table and queue registers and enables, in the order the specification gives for initialisation:
    /// the command queue, then an invalidation of all cached configuration and translations, then the event queue,
    /// then translation. Every stream table entry is invalid at this point, so every stream is refused.
    pub(crate) fn enable(&mut self) -> Result<(), Fail> {
        if self.reg(IDR0) & IDR0_S1P == 0 || self.reg(IDR5) & IDR5_GRAN4K == 0 {
            return Err(Fail::Check("the SMMU lacks stage 1 or the 4 KiB granule"));
        }
        // The tables and queues are ordinary cacheable memory and this driver does no cache maintenance on them, which
        // is right only for an SMMU that reads and writes them coherently.
        if self.reg(IDR0) & IDR0_COHACC == 0 {
            return Err(Fail::Check("the SMMU's table and queue accesses are not cache-coherent"));
        }
        if self.reg(CR0) != 0 {
            return Err(Fail::Check("the SMMU is not in its reset state"));
        }
        // Link the three translation tables once: the window's level 1 entry -> level 2, its entry there -> level 3.
        let l2_index = ((IOVA_BASE >> 21) & 0x1ff) as usize;
        self.tables[0].page.w64(((IOVA_BASE >> 30) & 0x1ff) as usize * 8, self.tables[1].pa | 0b11);
        self.tables[1].page.w64(l2_index * 8, self.tables[2].pa | 0b11);
        barrier();
        // CR1: tables and queues in inner-shareable, write-back cacheable memory. CR2: nothing.
        self.regs.w32(CR1, (3 << 10) | (1 << 8) | (1 << 6) | (3 << 4) | (1 << 2) | 1);
        self.regs.w32(CR2, 0);
        self.regs.w64(STRTAB_BASE, self.strtab.pa | BASE_RA);
        self.regs.w32(STRTAB_BASE_CFG, STRTAB_LOG2); // format 0: linear
        self.regs.w64(CMDQ_BASE, self.cmdq.pa | BASE_RA | u64::from(CMDQ_LOG2));
        self.regs.w32(CMDQ_PROD, 0);
        self.regs.w32(CMDQ_CONS, 0);
        self.regs.w64(EVENTQ_BASE, self.eventq.pa | BASE_RA | u64::from(EVENTQ_LOG2));
        self.regs1.w32(EVENTQ_PROD, 0);
        self.regs1.w32(EVENTQ_CONS, 0);
        self.set_cr0(CR0_CMDQEN)?;
        self.command([CMD_CFGI_STE_RANGE, 0, 31, 0])?; // range 31: every stream (CMD_CFGI_ALL)
        self.command([CMD_TLBI_NSNH_ALL, 0, 0, 0])?;
        self.sync()?;
        self.set_cr0(CR0_CMDQEN | CR0_EVENTQEN)?;
        self.set_cr0(CR0_ALL)
    }

    fn set_cr0(&mut self, value: u32) -> Result<(), Fail> {
        self.regs.w32(CR0, value);
        for _ in 0..POLL_LIMIT {
            if self.reg(CR0ACK) & CR0_ALL == value {
                return Ok(());
            }
        }
        Err(Fail::Check("CR0 was not acknowledged"))
    }

    /// Appends one command to the queue and tells the SMMU. Does not wait for it: `sync` does.
    pub(crate) fn command(&mut self, words: [u32; 4]) -> Result<(), Fail> {
        let wrap = 1u32 << CMDQ_LOG2;
        for _ in 0..POLL_LIMIT {
            // Full when the indices are equal and the wrap bits differ.
            if (self.reg(CMDQ_CONS) ^ self.cmd_prod) & (2 * wrap - 1) != wrap {
                let at = (self.cmd_prod & (wrap - 1)) as usize * CMD_BYTES;
                for (i, word) in words.iter().enumerate() {
                    self.cmdq.page.w32(at + i * 4, *word);
                }
                barrier();
                self.cmd_prod = (self.cmd_prod + 1) & (2 * wrap - 1);
                self.regs.w32(CMDQ_PROD, self.cmd_prod);
                return Ok(());
            }
        }
        Err(Fail::Check("the command queue stayed full"))
    }

    /// Issues CMD_SYNC and waits until the SMMU has consumed everything up to it. An error the SMMU reports for any
    /// command (the queue's error field, or the global error register) is returned as a failure.
    pub(crate) fn sync(&mut self) -> Result<(), Fail> {
        self.command([CMD_SYNC, 0, 0, 0])?; // CS 0: no interrupt, completion is seen in CMDQ_CONS
        let mask = 2 * (1u32 << CMDQ_LOG2) - 1;
        for _ in 0..POLL_LIMIT {
            let cons = self.reg(CMDQ_CONS);
            if (cons >> 24) & 0x7f != 0 || (self.reg(GERROR) ^ self.reg(GERRORN)) & 1 != 0 {
                return Err(Fail::Check("the SMMU reported a command error"));
            }
            if cons & mask == self.cmd_prod {
                return Ok(());
            }
        }
        Err(Fail::Check("CMD_SYNC did not complete"))
    }

    /// Writes the context descriptor in `cd`: one 39-bit stage-1 address space over this driver's tables, tagged
    /// `asid`, with faults recorded (R) and terminated by abort (A). Tells the SMMU nothing.
    pub(crate) fn write_context(&self, cd: Ram, asid: u16) {
        let ttb = self.tables[0].pa;
        // Word 0: T0SZ, TG0 = 4 KiB, inner and outer write-back cacheable walks, inner shareable, EPD1 (no TTB1), V.
        let w0 = T0SZ | (1 << 8) | (1 << 10) | (3 << 12) | (1 << 30) | (1 << 31);
        // Word 1: IPS 0b100 (44 bits, the model's output size), AA64, R, A, ASET, ASID.
        // QEMU: A must be 1 and S, HA and HD must be 0, or the descriptor is rejected (C_BAD_CD).
        let w1 = 0b100 | (1 << 9) | (1 << 13) | (1 << 14) | (1 << 15) | (u32::from(asid) << 16);
        cd.page.w32(0x08, (ttb as u32) & 0xffff_fff0);
        cd.page.w32(0x0c, ((ttb >> 32) as u32) & 0x000f_ffff);
        cd.page.w32(0x18, 0xff); // MAIR attribute 0: write-back cacheable memory
        cd.page.w32(0x04, w1);
        cd.page.w32(0x00, w0);
        barrier();
    }

    /// Writes a valid stream table entry for `sid`: stage 1 only (Config 0b101), one context descriptor at `cd`.
    /// The entry becomes valid with the last write. Tells the SMMU nothing.
    /// QEMU: S1STALLD and S1CDMax must be 0, or the entry is rejected (C_BAD_STE).
    pub(crate) fn write_stream(&self, sid: u32, cd: Ram) -> Result<(), Fail> {
        let at = self.stream_offset(sid)?;
        // Words 2 and 3: context descriptor fetches in inner-shareable write-back memory; SHCFG "use incoming".
        self.strtab.page.w32(at + 8, (1 << 2) | (1 << 4) | (3 << 6));
        self.strtab.page.w32(at + 12, 1 << 12);
        self.strtab.page.w32(at + 4, ((cd.pa >> 32) as u32) & 0x00ff_ffff);
        barrier();
        self.strtab.page.w32(at, 1 | (0b101 << 1) | ((cd.pa as u32) & 0xffff_ffc0));
        barrier();
        Ok(())
    }

    /// Clears the valid bit of the stream table entry of `sid`. Tells the SMMU nothing.
    pub(crate) fn clear_stream(&self, sid: u32) -> Result<(), Fail> {
        let at = self.stream_offset(sid)?;
        self.strtab.page.w32(at, 0);
        barrier();
        Ok(())
    }

    fn stream_offset(&self, sid: u32) -> Result<usize, Fail> {
        if sid >= 1 << STRTAB_LOG2 {
            return Err(Fail::Check("the stream id is outside the stream table"));
        }
        Ok(sid as usize * STE_BYTES)
    }

    /// CMD_CFGI_STE for `sid` (leaf): forget the cached configuration of that stream.
    pub(crate) fn invalidate_stream(&mut self, sid: u32) -> Result<(), Fail> {
        self.command([CMD_CFGI_STE, sid, 1, 0])
    }

    /// CMD_CFGI_CD for `sid`, substream 0 (leaf): forget the cached context descriptor of that stream.
    pub(crate) fn invalidate_context(&mut self, sid: u32) -> Result<(), Fail> {
        self.command([CMD_CFGI_CD, sid, 1, 0])
    }

    /// CMD_TLBI_NH_VA for one page of `asid` (leaf, VMID 0): forget the cached translation of `iova`.
    pub(crate) fn invalidate_page(&mut self, asid: u16, iova: u64) -> Result<(), Fail> {
        self.command([CMD_TLBI_NH_VA, u32::from(asid) << 16, 1 | (iova as u32 & 0xffff_f000), (iova >> 32) as u32])
    }

    fn entry_offset(iova: u64) -> Result<usize, Fail> {
        if !(IOVA_BASE..IOVA_BASE + IOVA_SPAN).contains(&iova) || iova % PAGE as u64 != 0 {
            return Err(Fail::Check("the I/O virtual address is outside the window or not page-aligned"));
        }
        Ok(((iova >> 12) & 0x1ff) as usize * 8)
    }

    /// Writes the level-3 entry that maps the page `iova` to the physical page `pa`, readable and, if `writable`,
    /// writable. Tells the SMMU nothing (an entry that was invalid is not cached, so a new mapping needs no command).
    pub(crate) fn map(&self, iova: u64, pa: u64, writable: bool) -> Result<(), Fail> {
        let at = Self::entry_offset(iova)?;
        // Page descriptor: access flag, inner shareable, AP[1] (unprivileged access allowed), AP[2] when read-only,
        // not global (the entry belongs to its ASID), never executable.
        let attributes = (1 << 10) | (3 << 8) | (1 << 6) | (u64::from(!writable) << 7) | (1 << 11) | (1 << 53) | (1 << 54);
        self.tables[2].page.w64(at, (pa & 0x0000_ffff_ffff_f000) | attributes | 0b11);
        barrier();
        Ok(())
    }

    /// Clears the level-3 entry of `iova`. Tells the SMMU nothing: until `invalidate_page` and `sync`, the SMMU may
    /// keep translating through what it has cached.
    pub(crate) fn unmap(&self, iova: u64) -> Result<(), Fail> {
        let at = Self::entry_offset(iova)?;
        self.tables[2].page.w64(at, 0);
        barrier();
        Ok(())
    }

    /// Takes every record out of the event queue. The second value is true if the SMMU reports that it dropped
    /// records because the queue was full (its overflow flag differs from the one last acknowledged).
    pub(crate) fn drain_events(&mut self) -> (Vec<Event>, bool) {
        let wrap = 1u32 << EVENTQ_LOG2;
        let prod = self.regs1.r32(EVENTQ_PROD);
        let overflowed = (prod ^ self.regs1.r32(EVENTQ_CONS)) >> 31 != 0;
        let mut events = Vec::new();
        barrier();
        while (self.event_cons ^ prod) & (2 * wrap - 1) != 0 && events.len() < 2 * wrap as usize {
            let at = (self.event_cons & (wrap - 1)) as usize * EVENT_BYTES;
            let word = |i: usize| self.eventq.page.r32(at + i * 4);
            events.push(Event {
                kind: word(0) as u8,
                sid: word(1),
                write: (word(3) >> 3) & 1 == 0,
                addr: u64::from(word(4)) | (u64::from(word(5)) << 32),
            });
            self.event_cons = (self.event_cons + 1) & (2 * wrap - 1);
        }
        // Acknowledge what was read, and the overflow flag (bit 31) by copying it.
        self.regs1.w32(EVENTQ_CONS, self.event_cons | (prod & (1 << 31)));
        (events, overflowed)
    }
}
