//
// SPDX-License-Identifier: BSD-2-Clause
//

//! Release-kernel execution test. A root task that needs nothing from the kernel's debug facilities: it prints
//! through its own PL011 driver (`pl011.rs`) and exercises the kernel through worker threads (`relk_workers.rs`).
//! The same source is built against each kernel it runs on (K1, K1R, K2, K2R); what it expects of the debug system
//! call and of the other cores follows from the configuration it was built against, and it prints that
//! configuration, so a log says both what was expected and what the kernel did.
//!
//! Every line it prints starts with `RELK`. A test prints `RELK test=<name> result=PASS` or `result=FAIL`, the last
//! line is `RELK_PASS` or `RELK_FAIL`. The tests are functional checks of kernel paths under one emulator; they are
//! not isolation claims (the workers share the root task's capability space) and not Stage B evidence.
//!
//! `RELK_MUTANT` at build time breaks one test on purpose, to show that the test can fail and that the failure is
//! visible on a kernel without debug output: `skip-revoke` (the revocation is not made), `rw-alias` (the second view
//! of the page is mapped writable).

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
#[path = "../pl011.rs"]
mod pl011;
#[path = "../rawsys.rs"]
mod rawsys;
#[path = "../relk_spawn.rs"]
mod relk_spawn;
#[path = "../slots.rs"]
mod slots;
#[path = "../relk_tests.rs"]
mod relk_tests;
#[path = "../relk_workers.rs"]
mod relk_workers;

use a5_mmio::DeviceMapper;
use object_allocator::ObjectAllocator;
use relk_spawn::Spawner;

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
pub(crate) const MUTANT: Option<&str> = option_env!("RELK_MUTANT");

/// Routes the runtime's panic messages to the user-level console. `sel4-root-task` defines this symbol weakly (as
/// `seL4_DebugPutChar`, or as nothing on a kernel without printing); this strong definition replaces it.
// SAFETY: the symbol name and the signature are the ones `sel4_panicking_env` declares for its output hook, so every
// caller agrees on the ABI; the function only calls the safe `put_byte`.
#[unsafe(no_mangle)]
#[allow(non_snake_case)]
fn __sel4_panicking_env__debug_put_char(c: u8) {
    pl011::put_byte(c);
}

/// What the tests share.
pub(crate) struct Ctx<'a> {
    pub(crate) bootinfo: &'a sel4::BootInfo,
    pub(crate) allocator: ObjectAllocator,
    pub(crate) mapper: DeviceMapper,
    pub(crate) spawner: Spawner,
    pub(crate) ep: sel4::cap::Endpoint,
    pub(crate) passed: u32,
    pub(crate) failed: u32,
}

impl Ctx<'_> {
    /// Records and prints one test's verdict.
    pub(crate) fn verdict(&mut self, name: &str, ok: bool) {
        if ok {
            self.passed += 1;
        } else {
            self.failed += 1;
        }
        uprintln!("RELK test={} result={}", name, if ok { "PASS" } else { "FAIL" });
    }
}

#[root_task(heap_size = 512 * 1024)]
fn main(bootinfo: &sel4::BootInfoPtr) -> sel4::Result<Never> {
    match run(bootinfo) {
        Ok((passed, 0)) => {
            uprintln!("RELK summary passed={} failed=0 console_bytes_dropped={} mmio_range_errors={}", passed, pl011::dropped(), a5_mmio::range_errors());
            uprintln!("RELK_PASS");
        }
        Ok((passed, failed)) => {
            uprintln!("RELK summary passed={} failed={} console_bytes_dropped={} mmio_range_errors={}", passed, failed, pl011::dropped(), a5_mmio::range_errors());
            uprintln!("RELK_FAIL");
        }
        Err(fail) => {
            uprintln!("RELK setup error: {:?}", fail);
            uprintln!("RELK_FAIL");
        }
    }
    sel4::init_thread::suspend_self()
}

fn run(bootinfo: &sel4::BootInfoPtr) -> Result<(u32, u32), Fail> {
    let mut allocator = ObjectAllocator::new(bootinfo)?;
    let mut mapper = DeviceMapper::new(bootinfo, &mut allocator)?;
    // Nothing can be printed before this succeeds: on a kernel without printing an earlier failure is silent.
    let uart = mapper.map_device(bootinfo, pl011::UART_PADDR)?;
    pl011::init(uart);
    report_configuration(bootinfo);

    let ep = allocator.allocate_fixed_sized::<sel4::cap_type::Endpoint>()?;
    let spawner = Spawner::new(bootinfo, ep)?;
    let mut ctx = Ctx { bootinfo, allocator, mapper, spawner, ep, passed: 0, failed: 0 };
    relk_tests::run_all(&mut ctx)?;
    Ok((ctx.passed, ctx.failed))
}

/// Prints what this image was built against and what the kernel reports about itself.
fn report_configuration(bootinfo: &sel4::BootInfo) {
    uprintln!("RELK start: user-level PL011 console at {:#x}, control register {:#x}", pl011::UART_PADDR, pl011::control().unwrap_or(0));
    uprintln!(
        "RELK built-for: PRINTING={} DEBUG_BUILD={} MAX_NUM_NODES={} ARM_HYPERVISOR_SUPPORT={} KERNEL_MCS={} mutant={}",
        sel4::sel4_cfg_bool!(PRINTING),
        sel4::sel4_cfg_bool!(DEBUG_BUILD),
        sel4::sel4_cfg_usize!(MAX_NUM_NODES),
        sel4::sel4_cfg_bool!(ARM_HYPERVISOR_SUPPORT),
        sel4::sel4_cfg_bool!(KERNEL_MCS),
        MUTANT.unwrap_or("none"),
    );
    let list = bootinfo.untyped_list();
    let device = list.iter().filter(|d| d.is_device()).count();
    let cover = DeviceMapper::device_untyped_for(bootinfo, pl011::UART_PADDR);
    uprintln!(
        "RELK kernel-reports: nodes={} node_id={} untypeds={} device={} uart_device_untyped={:x?}",
        bootinfo.inner().numNodes,
        bootinfo.inner().nodeID,
        list.len(),
        device,
        cover.map(|(_, base, size)| (base, size)),
    );
}
