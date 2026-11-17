//
// SPDX-License-Identifier: BSD-2-Clause
//

//! K3: the SMMUv3 driver of the server task. Adapted from the root task's `smmuv3.rs` (A5 step 1; formats checked against Arm
//! IHI 0070 and QEMU 11.1.3's definitions, never run against hardware), with three changes that K3 needs: **one address
//! space per client** (its own three translation tables, context descriptor and ASID, so the same I/O address names different
//! pages for different streams), no heap (the event queue is drained into a caller's array), and the memory it uses is handed
//! in by the caller (the server obtains it from its own untyped). One linear stream table, polled event queue, no interrupts,
//! no stage 2, no error recovery. QEMU-specific limits are marked "QEMU:".
//!
//! As in the original, changing a structure and telling the SMMU about it are separate calls.

use crate::k3_mmio::{PAGE, Page, barrier};

pub type Result<T> = core::result::Result<T, &'static str>;

const IDR0: usize = 0x00;
const IDR5: usize = 0x14;
const CR0: usize = 0x20;
const CR0ACK: usize = 0x24;
const CR1: usize = 0x28;
const CR2: usize = 0x2c;
const GERROR: usize = 0x60;
const GERRORN: usize = 0x64;
const STRTAB_BASE: usize = 0x80;
const STRTAB_BASE_CFG: usize = 0x88;
const CMDQ_BASE: usize = 0x90;
const CMDQ_PROD: usize = 0x98;
const CMDQ_CONS: usize = 0x9c;
const EVENTQ_BASE: usize = 0xa0;
const EVENTQ_PROD: usize = 0xa8;
const EVENTQ_CONS: usize = 0xac;
const PAGE1_OFFSET: usize = 0x1_0000;

const CR0_SMMUEN: u32 = 1;
const CR0_EVENTQEN: u32 = 1 << 2;
const CR0_CMDQEN: u32 = 1 << 3;
pub const CR0_ALL: u32 = CR0_SMMUEN | CR0_EVENTQEN | CR0_CMDQEN;
const IDR0_S1P: u32 = 1 << 1;
const IDR0_COHACC: u32 = 1 << 4;
const IDR5_GRAN4K: u32 = 1 << 4;
const BASE_RA: u64 = 1 << 62;

const STRTAB_LOG2: u32 = 6;
const STE_BYTES: usize = 64;
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

pub const EVT_C_BAD_STE: u8 = 0x04;
pub const EVT_F_TRANSLATION: u8 = 0x10;
pub const EVT_F_PERMISSION: u8 = 0x13;

/// The one window of I/O virtual addresses an address space can map: 2 MiB from 4 GiB, one level-3 table. Nothing on the
/// machine (`virt`, `highmem=off`, 1 GiB of RAM) has a physical address there, so a transfer that was not translated lands on
/// nothing. A device needs a 33-bit DMA mask to use it.
pub const IOVA_BASE: u64 = 0x1_0000_0000;
pub const IOVA_PAGES: usize = 512;
const T0SZ: u32 = 25;
const POLL_LIMIT: u32 = 1_000_000;

/// A page of ordinary memory the SMMU reads or writes by itself, mapped in this task, with its physical address.
#[derive(Clone, Copy)]
pub struct Ram {
    pub page: Page,
    pub pa: u64,
}

/// One client's stage-1 address space: three translation tables and a context descriptor.
#[derive(Clone, Copy)]
pub struct AddrSpace {
    tables: [Ram; 3],
    cd: Ram,
    pub asid: u16,
}

#[derive(Clone, Copy, Default)]
pub struct Event {
    pub kind: u8,
    pub sid: u32,
    pub write: bool,
    pub addr: u64,
}

/// What the experiment's cost accounting reads.
#[derive(Clone, Copy, Default)]
pub struct Stats {
    pub commands: u64,
    pub syncs: u64,
}

pub struct Smmu {
    regs: Page,
    regs1: Page,
    strtab: Ram,
    cmdq: Ram,
    eventq: Ram,
    cmd_prod: u32,
    event_cons: u32,
    pub stats: Stats,
}

impl AddrSpace {
    /// Takes four pages: three tables and a context descriptor. Links the tables (the window's level-1 entry to level 2, its
    /// entry there to level 3) and writes the context descriptor. Tells the SMMU nothing.
    pub fn new(tables: [Ram; 3], cd: Ram, asid: u16) -> Self {
        let as_ = Self { tables, cd, asid };
        let l2_index = ((IOVA_BASE >> 21) & 0x1ff) as usize;
        as_.tables[0].page.w64(((IOVA_BASE >> 30) & 0x1ff) as usize * 8, as_.tables[1].pa | 0b11);
        as_.tables[1].page.w64(l2_index * 8, as_.tables[2].pa | 0b11);
        // Word 0: T0SZ, TG0 = 4 KiB, inner and outer write-back cacheable walks, inner shareable, EPD1, V.
        let w0 = T0SZ | (1 << 8) | (1 << 10) | (3 << 12) | (1 << 30) | (1 << 31);
        // Word 1: IPS 0b100, AA64, R, A, ASET, ASID. QEMU: A must be 1 and S, HA, HD 0, or the descriptor is rejected.
        let w1 = 0b100 | (1 << 9) | (1 << 13) | (1 << 14) | (1 << 15) | (u32::from(asid) << 16);
        let ttb = as_.tables[0].pa;
        cd.page.w32(0x08, (ttb as u32) & 0xffff_fff0);
        cd.page.w32(0x0c, ((ttb >> 32) as u32) & 0x000f_ffff);
        cd.page.w32(0x18, 0xff);
        cd.page.w32(0x04, w1);
        cd.page.w32(0x00, w0);
        barrier();
        as_
    }

    pub fn cd_pa(&self) -> u64 {
        self.cd.pa
    }

    fn entry_offset(iova: u64) -> Result<usize> {
        if !(IOVA_BASE..IOVA_BASE + (IOVA_PAGES * PAGE) as u64).contains(&iova) || iova % PAGE as u64 != 0 {
            return Err("the I/O virtual address is outside the window or not page-aligned");
        }
        Ok(((iova >> 12) & 0x1ff) as usize * 8)
    }

    /// Writes the level-3 entry mapping the page `iova` to `pa`, readable and, if `writable`, writable. Tells the SMMU nothing
    /// (an entry that was invalid is not cached).
    pub fn map(&self, iova: u64, pa: u64, writable: bool) -> Result<()> {
        let at = Self::entry_offset(iova)?;
        let attributes = (1 << 10) | (3 << 8) | (1 << 6) | (u64::from(!writable) << 7) | (1 << 11) | (1 << 53) | (1 << 54);
        self.tables[2].page.w64(at, (pa & 0x0000_ffff_ffff_f000) | attributes | 0b11);
        barrier();
        Ok(())
    }

    /// Clears the entry of `iova`. Tells the SMMU nothing: until `Smmu::invalidate_page` and `Smmu::sync`, the SMMU may keep
    /// translating through what it has cached.
    pub fn unmap(&self, iova: u64) -> Result<()> {
        let at = Self::entry_offset(iova)?;
        self.tables[2].page.w64(at, 0);
        barrier();
        Ok(())
    }

    /// Whether the table entry of `iova` is currently valid (what the server believes it has mapped).
    pub fn is_mapped(&self, iova: u64) -> bool {
        Self::entry_offset(iova).map(|at| self.tables[2].page.r64(at) & 1 != 0).unwrap_or(false)
    }
}

impl Smmu {
    pub fn new(regs: Page, regs1: Page, strtab: Ram, cmdq: Ram, eventq: Ram) -> Self {
        Self { regs, regs1, strtab, cmdq, eventq, cmd_prod: 0, event_cons: 0, stats: Stats::default() }
    }

    pub fn reg(&self, offset: usize) -> u32 {
        self.regs.r32(offset)
    }

    /// Programs the table and queue registers and enables translation, in the order of the specification: command queue,
    /// invalidate everything, event queue, translation. Every stream table entry is invalid, so every stream is refused.
    pub fn enable(&mut self) -> Result<()> {
        if self.reg(IDR0) & IDR0_S1P == 0 || self.reg(IDR5) & IDR5_GRAN4K == 0 {
            return Err("the SMMU lacks stage 1 or the 4 KiB granule");
        }
        if self.reg(IDR0) & IDR0_COHACC == 0 {
            return Err("the SMMU's table and queue accesses are not cache-coherent");
        }
        if self.reg(CR0) != 0 {
            return Err("the SMMU is not in its reset state");
        }
        self.regs.w32(CR1, (3 << 10) | (1 << 8) | (1 << 6) | (3 << 4) | (1 << 2) | 1);
        self.regs.w32(CR2, 0);
        self.regs.w64(STRTAB_BASE, self.strtab.pa | BASE_RA);
        self.regs.w32(STRTAB_BASE_CFG, STRTAB_LOG2);
        self.regs.w64(CMDQ_BASE, self.cmdq.pa | BASE_RA | u64::from(CMDQ_LOG2));
        self.regs.w32(CMDQ_PROD, 0);
        self.regs.w32(CMDQ_CONS, 0);
        self.regs.w64(EVENTQ_BASE, self.eventq.pa | BASE_RA | u64::from(EVENTQ_LOG2));
        self.regs1.w32(EVENTQ_PROD, 0);
        self.regs1.w32(EVENTQ_CONS, 0);
        self.set_cr0(CR0_CMDQEN)?;
        self.command([CMD_CFGI_STE_RANGE, 0, 31, 0])?;
        self.command([CMD_TLBI_NSNH_ALL, 0, 0, 0])?;
        self.sync()?;
        self.set_cr0(CR0_CMDQEN | CR0_EVENTQEN)?;
        self.set_cr0(CR0_ALL)
    }

    fn set_cr0(&mut self, value: u32) -> Result<()> {
        self.regs.w32(CR0, value);
        for _ in 0..POLL_LIMIT {
            if self.reg(CR0ACK) & CR0_ALL == value {
                return Ok(());
            }
        }
        Err("CR0 was not acknowledged")
    }

    fn command(&mut self, words: [u32; 4]) -> Result<()> {
        let wrap = 1u32 << CMDQ_LOG2;
        for _ in 0..POLL_LIMIT {
            if (self.reg(CMDQ_CONS) ^ self.cmd_prod) & (2 * wrap - 1) != wrap {
                let at = (self.cmd_prod & (wrap - 1)) as usize * CMD_BYTES;
                for (i, word) in words.iter().enumerate() {
                    self.cmdq.page.w32(at + i * 4, *word);
                }
                barrier();
                self.cmd_prod = (self.cmd_prod + 1) & (2 * wrap - 1);
                self.regs.w32(CMDQ_PROD, self.cmd_prod);
                self.stats.commands += 1;
                return Ok(());
            }
        }
        Err("the command queue stayed full")
    }

    /// CMD_SYNC, then waits until the SMMU has consumed everything up to it. An error the SMMU reports is returned.
    pub fn sync(&mut self) -> Result<()> {
        self.command([CMD_SYNC, 0, 0, 0])?;
        self.stats.syncs += 1;
        let mask = 2 * (1u32 << CMDQ_LOG2) - 1;
        for _ in 0..POLL_LIMIT {
            let cons = self.reg(CMDQ_CONS);
            if (cons >> 24) & 0x7f != 0 || (self.reg(GERROR) ^ self.reg(GERRORN)) & 1 != 0 {
                return Err("the SMMU reported a command error");
            }
            if cons & mask == self.cmd_prod {
                return Ok(());
            }
        }
        Err("CMD_SYNC did not complete")
    }

    fn stream_offset(sid: u32) -> Result<usize> {
        if sid >= 1 << STRTAB_LOG2 {
            return Err("the stream id is outside the stream table");
        }
        Ok(sid as usize * STE_BYTES)
    }

    /// Writes a valid stream table entry for `sid`: stage 1 only, the context descriptor of `as_`. Valid with the last write.
    /// QEMU: S1STALLD and S1CDMax must be 0, or the entry is rejected.
    pub fn write_stream(&self, sid: u32, as_: &AddrSpace) -> Result<()> {
        let at = Self::stream_offset(sid)?;
        let cd = as_.cd_pa();
        self.strtab.page.w32(at + 8, (1 << 2) | (1 << 4) | (3 << 6));
        self.strtab.page.w32(at + 12, 1 << 12);
        self.strtab.page.w32(at + 4, ((cd >> 32) as u32) & 0x00ff_ffff);
        barrier();
        self.strtab.page.w32(at, 1 | (0b101 << 1) | ((cd as u32) & 0xffff_ffc0));
        barrier();
        Ok(())
    }

    /// Configures `sid` for `as_` and tells the SMMU (entry, context descriptor, sync).
    pub fn bind_stream(&mut self, sid: u32, as_: &AddrSpace) -> Result<()> {
        self.write_stream(sid, as_)?;
        self.command([CMD_CFGI_STE, sid, 1, 0])?;
        self.command([CMD_CFGI_CD, sid, 1, 0])?;
        self.sync()
    }

    /// CMD_TLBI_NH_VA for one page of `asid` (leaf, VMID 0).
    pub fn invalidate_page(&mut self, asid: u16, iova: u64) -> Result<()> {
        self.command([CMD_TLBI_NH_VA, u32::from(asid) << 16, 1 | (iova as u32 & 0xffff_f000), (iova >> 32) as u32])
    }

    /// Takes every record out of the event queue into `out`; returns how many were stored and whether the SMMU says it
    /// dropped records because the queue was full.
    pub fn drain_events(&mut self, out: &mut [Event]) -> (usize, bool) {
        let wrap = 1u32 << EVENTQ_LOG2;
        let prod = self.regs1.r32(EVENTQ_PROD);
        let overflowed = (prod ^ self.regs1.r32(EVENTQ_CONS)) >> 31 != 0;
        let mut n = 0;
        barrier();
        while (self.event_cons ^ prod) & (2 * wrap - 1) != 0 {
            let at = (self.event_cons & (wrap - 1)) as usize * EVENT_BYTES;
            let word = |i: usize| self.eventq.page.r32(at + i * 4);
            if n < out.len() {
                out[n] = Event {
                    kind: word(0) as u8,
                    sid: word(1),
                    write: (word(3) >> 3) & 1 == 0,
                    addr: u64::from(word(4)) | (u64::from(word(5)) << 32),
                };
                n += 1;
            }
            self.event_cons = (self.event_cons + 1) & (2 * wrap - 1);
        }
        self.regs1.w32(EVENTQ_CONS, self.event_cons | (prod & (1 << 31)));
        (n, overflowed)
    }
}
