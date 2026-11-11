//
// SPDX-License-Identifier: BSD-2-Clause
//
// A5 step 1: QEMU's `edu` test device as a DMA master the experiment controls. Found through the PCIe configuration
// space (ECAM), given a BAR, and told to copy between its internal 4 KiB buffer and an address of its own choosing.
// Register layout: QEMU's `docs/specs/edu.rst` and `hw/misc/edu.c` (11.1.3). The device ignores DMA errors, so whether
// a transfer had an effect is seen only in memory.
//

use alloc::vec::Vec;

use crate::a5_mmio::{DeviceMapper, Page, barrier};
use crate::Fail;

/// The ECAM window of QEMU `virt` with `highmem=off`. The root task cannot discover it (results/A5-step0.md), and a
/// read at an address with no device is a fatal abort, so the machine must be started with that option.
const ECAM: usize = 0x3f00_0000;
/// Bus 0, devices 0 to 3, function 0: one ECAM page per function, 0x8000 apart.
const SCAN_DEVICES: usize = 4;
/// Where the BARs go: the start of the 32-bit PCI memory window, 1 MiB per device.
const BAR_BASE: u32 = 0x1000_0000;
const BAR_STEP: u32 = 0x10_0000;
const VENDOR_DEVICE: u32 = 0x11e8_1234;
const IDENTIFICATION: u32 = 0x0100_00ed;
/// The device's DMA buffer in its own address space, and its size.
const BUFFER: u64 = 0x4_0000;
pub(crate) const BUFFER_BYTES: u64 = 4096;
const POLL_LIMIT: u32 = 40_000_000;

pub(crate) struct Edu {
    regs: Page,
    /// The stream id the SMMU sees for this device: its PCI requester id (bus 0, so device << 3).
    pub(crate) sid: u32,
}

/// Finds every `edu` on bus 0 (devices 0 to 3), assigns and enables its BAR with bus mastering, and checks that the
/// device answers. Devices are returned in ascending device number.
pub(crate) fn discover(bootinfo: &sel4::BootInfo, mapper: &mut DeviceMapper) -> Result<Vec<Edu>, Fail> {
    let mut found = Vec::new();
    for device in 0..SCAN_DEVICES {
        let config = mapper.map_device(bootinfo, ECAM + device * 0x8000)?;
        if config.r32(0) == VENDOR_DEVICE {
            found.push((device as u32, config));
        }
    }
    let mut devices = Vec::new();
    for (index, (device, config)) in found.into_iter().enumerate() {
        let bar = BAR_BASE + index as u32 * BAR_STEP;
        config.w32(0x10, bar);
        config.w32(0x04, (config.r32(0x04) & 0xffff) | 0x6); // memory space and bus master
        let regs = mapper.map_device(bootinfo, bar as usize)?;
        regs.w32(0x04, 0x1234_5678);
        if regs.r32(0x00) != IDENTIFICATION || regs.r32(0x04) != !0x1234_5678 {
            return Err(Fail::Check("an edu device does not answer at its BAR"));
        }
        devices.push(Edu { regs, sid: device << 3 });
    }
    Ok(devices)
}

impl Edu {
    /// Asks the device to copy `count` bytes from the bus address `addr` into the start of its buffer. True when the
    /// device reports that it finished, which says nothing about whether the copy had any effect.
    pub(crate) fn read_from(&self, addr: u64, count: u64) -> bool {
        self.transfer(addr, BUFFER, count, 0x1)
    }

    /// Asks the device to copy `count` bytes from the start of its buffer to the bus address `addr`.
    pub(crate) fn write_to(&self, addr: u64, count: u64) -> bool {
        self.transfer(BUFFER, addr, count, 0x3)
    }

    fn transfer(&self, src: u64, dst: u64, count: u64, command: u64) -> bool {
        barrier();
        self.regs.w64(0x80, src);
        self.regs.w64(0x88, dst);
        self.regs.w64(0x90, count.min(BUFFER_BYTES));
        self.regs.w64(0x98, command);
        // The device starts the copy from a timer and clears the run bit when it is over.
        for _ in 0..POLL_LIMIT {
            if self.regs.r32(0x98) & 1 == 0 {
                barrier();
                return true;
            }
        }
        false
    }
}
