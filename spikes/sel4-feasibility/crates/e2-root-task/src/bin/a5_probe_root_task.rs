//
// SPDX-License-Identifier: BSD-2-Clause
//

//! A5 step 0: an environment and feasibility probe, not the A5 experiment. On the E1-H kernel (hypervisor-enabled, as in E1 to E3)
//! under QEMU with `iommu=smmuv3` and an `edu` PCI device, this root task finds out, and prints, whether it can
//! (1) identify the device untypeds that cover the SMMU registers, the PCIe configuration space and the PCI memory window,
//! (2) map them and read the SMMUv3 identification registers, (3) find the `edu` device through the ECAM and give it a BAR,
//! and (4) move data between two pages of RAM through the device's DMA engine under each global state of the SMMU
//! (reset default, global abort, global bypass flag), so that a change of the SMMU state is seen to change the data movement.
//!
//! It never enables the SMMU, never builds a stream table, and decides nothing about isolation. A successful read of a register,
//! or the creation of a device, shows nothing about DMA confinement.

#![no_std]
#![no_main]
#![allow(clippy::useless_conversion)]

extern crate alloc;

use sel4_root_task::{Never, root_task};

#[allow(dead_code)] // a helper shared by several binaries; not every one uses every item
#[path = "../a5_mmio.rs"]
mod a5_mmio;
#[path = "../object_allocator.rs"]
mod object_allocator;

use a5_mmio::{DeviceMapper, Page};
use object_allocator::ObjectAllocator;

/// SMMUv3 registers on QEMU `virt` (from the device tree QEMU generates: `smmuv3@9050000`, 0x20000 bytes).
const SMMU_BASE: usize = 0x0905_0000;
/// The PCIe ECAM window of QEMU `virt`: 0x3f000000 with `highmem=off`, 0x4010000000 with it on (the QEMU-generated tree). It is
/// chosen when the probe is built (`A5_ECAM_HIGH` set, see build-a5-probe.sh), because the root task cannot find it at run time: the device tree it receives is
/// the kernel's build-time one, with no PCI node, a device untyped covers all non-RAM address space whether or not anything is
/// there, and reading an address with no device is a fatal external abort for the root task.
const ECAM: usize = if option_env!("A5_ECAM_HIGH").is_some() { 0x40_1000_0000 } else { 0x3f00_0000 };
const ECAM_OTHER: usize = if option_env!("A5_ECAM_HIGH").is_some() { 0x3f00_0000 } else { 0x40_1000_0000 };
/// Where the root task puts edu's BAR0, inside the first 32-bit PCI memory window of the same tree (0x10000000 to 0x3eff0000).
const BAR_ADDR: u32 = 0x1000_0000;
const EDU_ID: u32 = 0x11e8_1234;
/// edu's internal DMA buffer starts at 0x40000 in the device's own address space.
const EDU_BUFFER: u64 = 0x4_0000;
const GBPA: usize = 0x44;
const GBPA_ABORT: u32 = 1 << 20;
const GBPA_UPDATE: u32 = 1 << 31;

#[derive(Debug)]
#[allow(dead_code)]
pub(crate) enum Fail {
    Sel4(sel4::Error),
    OutOfSlots,
    NoUntyped,
    Elf,
    Layout,
    Check(&'static str),
}

impl From<sel4::Error> for Fail {
    fn from(e: sel4::Error) -> Self {
        Fail::Sel4(e)
    }
}

#[root_task(heap_size = 1024 * 64)]
fn main(bootinfo: &sel4::BootInfoPtr) -> sel4::Result<Never> {
    match run(bootinfo) {
        Ok(()) => sel4::debug_println!("A5P_DONE"),
        Err(fail) => sel4::debug_println!("A5P_FAIL {:?}", fail),
    }
    sel4::init_thread::suspend_self()
}

fn run(bootinfo: &sel4::BootInfoPtr) -> Result<(), Fail> {
    sel4::debug_println!("A5P start");
    let mut allocator = ObjectAllocator::new(bootinfo)?;
    let mut mapper = DeviceMapper::new(bootinfo, &mut allocator)?;
    report_untypeds(bootinfo);

    let smmu = mapper.map_device(bootinfo, SMMU_BASE)?;
    report_smmu(smmu);

    let Some(edu_cfg) = find_edu(bootinfo, &mut mapper) else {
        return Err(Fail::Check("edu not found in the ECAM"));
    };
    let bar_before = edu_cfg.r32(0x10);
    edu_cfg.w32(0x10, 0xffff_ffff);
    let bar_mask = edu_cfg.r32(0x10);
    edu_cfg.w32(0x10, BAR_ADDR);
    let command = edu_cfg.r32(0x04) & 0xffff;
    edu_cfg.w32(0x04, command | 0x6);
    sel4::debug_println!(
        "A5P edu bar0 before={:#x} sizing_mask={:#x} (size {:#x}) set={:#x} readback={:#x} command {:#x} -> {:#x}",
        bar_before,
        bar_mask,
        (!(bar_mask & !0xf)).wrapping_add(1),
        BAR_ADDR,
        edu_cfg.r32(0x10),
        command,
        edu_cfg.r32(0x04) & 0xffff
    );

    let edu = mapper.map_device(bootinfo, BAR_ADDR as usize)?;
    edu.w32(0x04, 0x1234_5678);
    sel4::debug_println!("A5P edu id={:#x} liveness {:#x} (expect the complement of 0x12345678: 0xedcba987)", edu.r32(0x00), edu.r32(0x04));

    let (frame_a, frame_b) = (allocator.allocate_fixed_sized::<sel4::cap_type::Granule>()?, allocator.allocate_fixed_sized::<sel4::cap_type::Granule>()?);
    // SAFETY: frame A was retyped from an untyped just now, so nothing refers to its memory; its capability is never revoked.
    let (page_a, pa_a) = unsafe { mapper.map_ram(frame_a) }?;
    // SAFETY: as frame A.
    let (page_b, pa_b) = unsafe { mapper.map_ram(frame_b) }?;
    sel4::debug_println!("A5P ram pages pa_a={:#x} pa_b={:#x}; above edu's default 28-bit DMA mask: {}", pa_a, pa_b, pa_a > 0x0fff_ffff);

    roundtrip(edu, (page_a, pa_a), (page_b, pa_b), "reset-default", 0xa5a5_0001);
    set_abort(smmu, true);
    roundtrip(edu, (page_a, pa_a), (page_b, pa_b), "gbpa-abort", 0xa5a5_0002);
    set_abort(smmu, false);
    roundtrip(edu, (page_a, pa_a), (page_b, pa_b), "gbpa-abort-cleared", 0xa5a5_0003);
    sel4::debug_println!("A5P mmio range errors: {}", a5_mmio::range_errors());
    Ok(())
}

/// Prints the device untypeds that cover the places the probe needs, and the totals.
fn report_untypeds(bootinfo: &sel4::BootInfo) {
    let list = bootinfo.untyped_list();
    let device = list.iter().filter(|d| d.is_device()).count();
    sel4::debug_println!("A5P untypeds total={} device={} ram={}", list.len(), device, list.len() - device);
    sel4::debug_println!("A5P probe built for ECAM {:#x}", ECAM);
    let targets = [("smmu", SMMU_BASE), ("ecam", ECAM), ("ecam-other-layout", ECAM_OTHER), ("pci-mmio-window", BAR_ADDR as usize)];
    for (name, paddr) in targets {
        match DeviceMapper::device_untyped_for(bootinfo, paddr) {
            Some((_, base, size)) => sel4::debug_println!("A5P cover {} {:#x}: device untyped {:#x} + {:#x}", name, paddr, base, size),
            None => sel4::debug_println!("A5P cover {} {:#x}: no device untyped", name, paddr),
        }
    }
}

fn report_smmu(smmu: Page) {
    for (name, off) in [("IDR0", 0x0), ("IDR1", 0x4), ("IDR2", 0x8), ("IDR3", 0xc), ("IDR4", 0x10), ("IDR5", 0x14), ("IIDR", 0x18), ("AIDR", 0x1c), ("CR0", 0x20), ("CR0ACK", 0x24), ("CR1", 0x28), ("CR2", 0x2c), ("STATUSR", 0x40), ("GBPA", GBPA), ("IRQ_CTRL", 0x50), ("GERROR", 0x60), ("STRTAB_BASE_CFG", 0x88), ("CMDQ_PROD", 0x98), ("CMDQ_CONS", 0x9c)] {
        sel4::debug_println!("A5P smmu {} = {:#010x}", name, smmu.r32(off));
    }
    let (idr0, idr1, idr5, aidr) = (smmu.r32(0x0), smmu.r32(0x4), smmu.r32(0x14), smmu.r32(0x1c));
    sel4::debug_println!(
        "A5P smmu decoded: S1P={} S2P={} TTF={:#b} COHACC={} ASID16={} MSI={} ST_LEVEL={:#b} SIDSIZE={} OAS={:#b} GRAN4K={} AIDR major.minor={}.{} (0.1 is SMMUv3.1)",
        (idr0 >> 1) & 1, idr0 & 1, (idr0 >> 2) & 3, (idr0 >> 4) & 1, (idr0 >> 12) & 1, (idr0 >> 13) & 1, (idr0 >> 27) & 3,
        idr1 & 0x3f, idr5 & 7, (idr5 >> 4) & 1, (aidr >> 4) & 0xf, aidr & 0xf
    );
}

/// Looks for edu (1234:11e8) at devices 0 to 3 of bus 0 in the ECAM and returns its configuration page.
fn find_edu(bootinfo: &sel4::BootInfo, mapper: &mut DeviceMapper) -> Option<Page> {
    let mut found = None;
    for dev in 0..4usize {
        let page = match mapper.map_device(bootinfo, ECAM + dev * 0x8000) {
            Ok(p) => p,
            Err(e) => {
                sel4::debug_println!("A5P ecam {:#x} dev {} could not be mapped: {:?}", ECAM, dev, e);
                break;
            }
        };
        let id = page.r32(0);
        sel4::debug_println!("A5P ecam {:#x} 00:{:02x}.0 vendor:device = {:#06x}:{:#06x}", ECAM, dev, id & 0xffff, id >> 16);
        if id == EDU_ID {
            found = Some(page);
        }
    }
    found
}

/// Sets or clears the SMMU's global abort bit (GBPA.ABORT) with the UPDATE handshake the architecture defines.
fn set_abort(smmu: Page, abort: bool) {
    wait_clear(smmu, GBPA, GBPA_UPDATE);
    let old = smmu.r32(GBPA);
    smmu.w32(GBPA, (old & !GBPA_ABORT) | if abort { GBPA_ABORT } else { 0 } | GBPA_UPDATE);
    wait_clear(smmu, GBPA, GBPA_UPDATE);
    sel4::debug_println!("A5P smmu GBPA {:#x} -> {:#x} (abort {})", old, smmu.r32(GBPA), abort);
}

fn wait_clear(page: Page, off: usize, mask: u32) {
    for _ in 0..1_000_000 {
        if page.r32(off) & mask == 0 {
            return;
        }
    }
}

/// One edu DMA transfer; true when the device reports it finished (edu starts it from a timer, about 100 ms later).
fn edu_dma(edu: Page, src: u64, dst: u64, count: u64, cmd: u64) -> bool {
    edu.w64(0x80, src);
    edu.w64(0x88, dst);
    edu.w64(0x90, count);
    edu.w64(0x98, cmd);
    for _ in 0..20_000_000u32 {
        if edu.r32(0x98) & 1 == 0 {
            return true;
        }
    }
    false
}

/// RAM page A -> edu's buffer -> RAM page B, with the SMMU in the state the caller set. Reports what page B holds afterwards.
fn roundtrip(edu: Page, a: (Page, usize), b: (Page, usize), state: &str, pattern: u32) {
    for i in 0..16 {
        a.0.w32(i * 4, pattern.wrapping_add(i as u32));
        b.0.w32(i * 4, 0);
    }
    a5_mmio::barrier();
    let first = edu_dma(edu, a.1 as u64, EDU_BUFFER, 64, 0x1);
    let second = edu_dma(edu, EDU_BUFFER, b.1 as u64, 64, 0x3);
    a5_mmio::barrier();
    let copied = (0..16).filter(|&i| b.0.r32(i * 4) == pattern.wrapping_add(i as u32)).count();
    let untouched = (0..16).filter(|&i| b.0.r32(i * 4) == 0).count();
    sel4::debug_println!(
        "A5P roundtrip state={} dma1_done={} dma2_done={} words_copied={}/16 words_untouched={}/16 -> {}",
        state, first, second, copied, untouched,
        if copied == 16 { "DATA MOVED" } else if untouched == 16 { "NOTHING MOVED" } else { "PARTIAL" }
);
}
