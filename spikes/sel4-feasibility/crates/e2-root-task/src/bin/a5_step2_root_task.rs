//
// SPDX-License-Identifier: BSD-2-Clause
//

//! A5 step 2: revoke while mapped. An exploratory falsification experiment, designed and reviewed before it was run
//! (results/A5-step2.md, section 1). With the SMMU of step 1 enabled and one device stream given a stage-1 mapping of
//! a frame, the frame's untyped is revoked and its memory handed out again, as a frame or as a kernel object, and the
//! device is asked to read and write through the mapping that is still there. Control: the same with the mapping
//! torn down first.
//!
//! One root task plays the server, the donor and the victim; what it shows is what the kernel and the SMMU model do,
//! not what separate protection domains could do to each other. Emulator only. Every line starts with `A5S2`; a
//! result is printed as `A5S2 finding=<name> observed=<value>`; the last line is `A5S2_DONE`, or `A5S2_VOID` when a
//! positive control failed or the set-up did not complete. `A5S2_MUTANT=teardown-without-invalidation` at build time
//! leaves the invalidation command out of the teardown of scenario B.

#![no_std]
#![no_main]
#![allow(clippy::useless_conversion)]

extern crate alloc;

use sel4_root_task::{Never, root_task};

#[allow(dead_code)] // a helper shared by several binaries; not every one uses every item
#[path = "../a5_mmio.rs"]
mod a5_mmio;
#[path = "../a5_step2_tests.rs"]
mod a5_step2_tests;
#[allow(dead_code)]
#[path = "../edu.rs"]
mod edu;
#[allow(dead_code)]
#[path = "../object_allocator.rs"]
mod object_allocator;
#[allow(dead_code)]
#[path = "../pl011.rs"]
mod pl011;
#[path = "../slots.rs"]
mod slots;
#[allow(dead_code)]
#[path = "../smmuv3.rs"]
mod smmuv3;

use a5_mmio::DeviceMapper;
use edu::Edu;
use object_allocator::ObjectAllocator;
use slots::SlotWindow;
use smmuv3::{Ram, Smmu};

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

/// The mutation this image was built with, if any.
pub(crate) const MUTANT: Option<&str> = option_env!("A5S2_MUTANT");

/// Routes the runtime's panic messages to the user-level console (see `relk_root_task.rs`).
// SAFETY: the symbol name and the signature are the ones `sel4_panicking_env` declares for its output hook, so every
// caller agrees on the ABI; the function only calls the safe `put_byte`.
#[unsafe(no_mangle)]
#[allow(non_snake_case)]
fn __sel4_panicking_env__debug_put_char(c: u8) {
    pl011::put_byte(c);
}

/// What the scenarios share.
pub(crate) struct World {
    pub(crate) allocator: ObjectAllocator,
    pub(crate) mapper: DeviceMapper,
    pub(crate) slots: SlotWindow,
    pub(crate) smmu: Smmu,
    pub(crate) edu: Edu,
    /// The server's own page, permanently mapped for the device, through which the device's buffer can be seen and set.
    pub(crate) o: Ram,
    /// Scenarios whose positive control failed.
    pub(crate) void: u32,
    /// Device transfers that the device did not report finished.
    pub(crate) unfinished: u32,
}

#[root_task(heap_size = 256 * 1024)]
fn main(bootinfo: &sel4::BootInfoPtr) -> sel4::Result<Never> {
    match run(bootinfo) {
        Ok(0) => uprintln!("A5S2_DONE"),
        Ok(void) => {
            uprintln!("A5S2 void: {} positive control(s) failed or transfer(s) did not finish", void);
            uprintln!("A5S2_VOID");
        }
        Err(fail) => {
            uprintln!("A5S2 stopped: {:?}", fail);
            uprintln!("A5S2_VOID");
        }
    }
    sel4::init_thread::suspend_self()
}

fn run(bootinfo: &sel4::BootInfoPtr) -> Result<u32, Fail> {
    let mut allocator = ObjectAllocator::new(bootinfo)?;
    let mut mapper = DeviceMapper::new(bootinfo, &mut allocator)?;
    // The UART comes first: it and the SMMU are in one device untyped, which is retyped in ascending order.
    pl011::init(mapper.map_device(bootinfo, pl011::UART_PADDR)?);
    uprintln!(
        "A5S2 start: built-for PRINTING={} MAX_NUM_NODES={} ARM_HYPERVISOR_SUPPORT={} mutant={}",
        sel4::sel4_cfg_bool!(PRINTING),
        sel4::sel4_cfg_usize!(MAX_NUM_NODES),
        sel4::sel4_cfg_bool!(ARM_HYPERVISOR_SUPPORT),
        MUTANT.unwrap_or("none"),
    );
    let mut smmu = Smmu::new(bootinfo, &mut mapper, &mut allocator)?;
    let Some(edu) = edu::discover(bootinfo, &mut mapper)?.into_iter().next() else {
        return Err(Fail::Check("the machine has no edu device"));
    };
    let cd = Ram::new(&mut mapper, &mut allocator)?;
    let o = Ram::new(&mut mapper, &mut allocator)?;
    smmu.enable()?;
    let slots = SlotWindow::new(bootinfo)?;
    let mut world = World { allocator, mapper, slots, smmu, edu, o, void: 0, unfinished: 0 };
    a5_step2_tests::configure(&mut world, cd)?;
    a5_step2_tests::run_all(&mut world)?;
    uprintln!("A5S2 smmu at the end [IDR0, IDR1, IDR5, CR0, CR0ACK, GBPA, GERROR^GERRORN] = {:x?}", world.smmu.state());
    uprintln!("A5S2 at the end: device transfers not reported finished={} console_bytes_dropped={} mmio_range_errors={}", world.unfinished, pl011::dropped(), a5_mmio::range_errors());
    // An unfinished transfer makes whatever followed it meaningless: the run is void.
    Ok(world.void + world.unfinished)
}
