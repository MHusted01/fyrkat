//
// SPDX-License-Identifier: BSD-2-Clause
//

//! A5 step 1: does QEMU's SMMUv3, driven from a seL4 root task, translate and confine the DMA of one device stream?
//! The root task enables the SMMU (`smmuv3.rs`), gives the stream of one `edu` device (`edu.rs`) a stage-1 address
//! space with one read-write page and one read-only page, and then has the device attempt transfers that the
//! configuration allows and transfers it does not. A second `edu`, whose stream is never configured, is the control
//! that tells a per-stream decision from a global one. Each test says what it saw in memory and in the SMMU's event
//! queue; QEMU's own trace of the SMMU model is captured beside the console by the harness.
//!
//! It prints through the user-level UART (`pl011.rs`), so it does not depend on kernel debug output. Every line starts
//! with `A5S1`; a test prints `A5S1 test=<name> result=PASS|FAIL`; the last line is `A5S1_PASS` or `A5S1_FAIL`.
//!
//! This is an emulator experiment about one device model and one stream. It is not an A5 outcome, says nothing about
//! hardware, and its root task holds every capability, so it shows what the SMMU enforces against the device, not
//! what the system enforces against software. `A5S1_MUTANT` at build time breaks one thing on purpose: `skip-tlbi`,
//! `skip-cfgi` (an invalidation command is left out), `map-unmapped` (the "unmapped" address is mapped to the guard
//! page), `rw-readonly` (the "read-only" page is mapped writable), `second-stream-configured` (the second device's
//! stream is given the first one's address space).

#![no_std]
#![no_main]
#![allow(clippy::useless_conversion)]

extern crate alloc;

use sel4_root_task::{Never, root_task};

#[allow(dead_code)] // a helper shared by several binaries; not every one uses every item
#[path = "../a5_mmio.rs"]
mod a5_mmio;
#[path = "../a5_step1_tests.rs"]
mod a5_step1_tests;
#[path = "../edu.rs"]
mod edu;
#[allow(dead_code)]
#[path = "../object_allocator.rs"]
mod object_allocator;
#[allow(dead_code)]
#[path = "../pl011.rs"]
mod pl011;
#[path = "../smmuv3.rs"]
mod smmuv3;

use a5_mmio::DeviceMapper;
use edu::Edu;
use object_allocator::ObjectAllocator;
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
pub(crate) const MUTANT: Option<&str> = option_env!("A5S1_MUTANT");

/// Routes the runtime's panic messages to the user-level console (see `relk_root_task.rs`).
// SAFETY: the symbol name and the signature are the ones `sel4_panicking_env` declares for its output hook, so every
// caller agrees on the ABI; the function only calls the safe `put_byte`.
#[unsafe(no_mangle)]
#[allow(non_snake_case)]
fn __sel4_panicking_env__debug_put_char(c: u8) {
    pl011::put_byte(c);
}

/// What the tests share.
pub(crate) struct World {
    pub(crate) smmu: Smmu,
    /// The device whose stream is configured.
    pub(crate) edu: Edu,
    /// A second device whose stream is never configured.
    pub(crate) other: Edu,
    /// The context descriptor of the configured stream.
    pub(crate) cd: Ram,
    /// The page mapped read-write for the device.
    pub(crate) p: Ram,
    /// The guard page: never mapped for the device.
    pub(crate) q: Ram,
    /// The page mapped read-only for the device.
    pub(crate) r: Ram,
    pub(crate) passed: u32,
    pub(crate) failed: u32,
}

impl World {
    pub(crate) fn verdict(&mut self, name: &str, ok: bool) {
        if ok {
            self.passed += 1;
        } else {
            self.failed += 1;
        }
        uprintln!("A5S1 test={} result={}", name, if ok { "PASS" } else { "FAIL" });
    }
}

#[root_task(heap_size = 256 * 1024)]
fn main(bootinfo: &sel4::BootInfoPtr) -> sel4::Result<Never> {
    match run(bootinfo) {
        Ok((passed, failed)) => {
            uprintln!("A5S1 summary passed={} failed={} console_bytes_dropped={} mmio_range_errors={}", passed, failed, pl011::dropped(), a5_mmio::range_errors());
            uprintln!("{}", if failed == 0 { "A5S1_PASS" } else { "A5S1_FAIL" });
        }
        Err(fail) => {
            uprintln!("A5S1 setup error: {:?}", fail);
            uprintln!("A5S1_FAIL");
        }
    }
    sel4::init_thread::suspend_self()
}

fn run(bootinfo: &sel4::BootInfoPtr) -> Result<(u32, u32), Fail> {
    let mut allocator = ObjectAllocator::new(bootinfo)?;
    let mut mapper = DeviceMapper::new(bootinfo, &mut allocator)?;
    // The UART comes first: it and the SMMU are in one device untyped, which is retyped in ascending order.
    pl011::init(mapper.map_device(bootinfo, pl011::UART_PADDR)?);
    uprintln!(
        "A5S1 start: built-for PRINTING={} MAX_NUM_NODES={} ARM_HYPERVISOR_SUPPORT={} mutant={}",
        sel4::sel4_cfg_bool!(PRINTING),
        sel4::sel4_cfg_usize!(MAX_NUM_NODES),
        sel4::sel4_cfg_bool!(ARM_HYPERVISOR_SUPPORT),
        MUTANT.unwrap_or("none"),
    );
    let mut smmu = Smmu::new(bootinfo, &mut mapper, &mut allocator)?;
    let mut devices = edu::discover(bootinfo, &mut mapper)?;
    if devices.len() != 2 {
        return Err(Fail::Check("the machine must have exactly two edu devices"));
    }
    let (Some(other), Some(edu)) = (devices.pop(), devices.pop()) else {
        return Err(Fail::Check("the machine must have exactly two edu devices"));
    };
    let mut ram = || Ram::new(&mut mapper, &mut allocator);
    let (cd, p, q, r) = (ram()?, ram()?, ram()?, ram()?);
    uprintln!("A5S1 devices: configured stream sid={:#x}, unconfigured stream sid={:#x}", edu.sid, other.sid);
    uprintln!("A5S1 smmu before enabling [IDR0, IDR1, IDR5, CR0, CR0ACK, GBPA, GERROR^GERRORN] = {:x?}", smmu.state());
    smmu.enable()?;
    let state = smmu.state();
    uprintln!("A5S1 smmu after enabling  [IDR0, IDR1, IDR5, CR0, CR0ACK, GBPA, GERROR^GERRORN] = {:x?}", state);
    let mut world = World { smmu, edu, other, cd, p, q, r, passed: 0, failed: 0 };
    world.verdict("smmu-enabled", state[3] == smmuv3::CR0_ALL && state[4] == smmuv3::CR0_ALL && state[5] & smmuv3::GBPA_ABORT == 0 && state[6] == 0);
    a5_step1_tests::run_all(&mut world)?;
    Ok((world.passed, world.failed))
}
