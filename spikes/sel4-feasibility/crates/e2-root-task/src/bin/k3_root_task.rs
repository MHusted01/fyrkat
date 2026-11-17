//
// SPDX-License-Identifier: BSD-2-Clause
//

//! K3 root task (results/K3.md): builds four protection domains (the SMMU server S, two clients C1 and C2 each driving an
//! `edu` device, and a memory owner M), each with its own CNode and VSpace and exactly the capabilities the design lists, then
//! conducts the four P5 tests, their adversarial steps and the controls. It prints through the user-level UART, so it works
//! on kernels without printing. Every line starts with `K3`; the last is `K3_PASS` or `K3_FAIL`, then `K3_DONE`.
//!
//! It is the initial task, so it is in the trusted base (the document says so). It does **not** keep the pool's untyped: that
//! capability is moved into the server's CNode. `K3_MODE=naive` and `K3_MUTANT` (build-time) select the control and the
//! mutants; they are passed on to the server build by the build script and printed here.

#![no_std]
#![no_main]
#![allow(clippy::useless_conversion)]

extern crate alloc;

use alloc::vec::Vec;

use object::File;
use sel4::CapTypeForObjectOfFixedSize;
use sel4_root_task::{Never, root_task};

#[allow(dead_code)] // a helper shared by several binaries; not every one uses every item
#[path = "../a5_mmio.rs"]
mod a5_mmio;
#[allow(dead_code)]
#[path = "../child_vspace.rs"]
mod child_vspace;
#[path = "../edu.rs"]
mod edu;
#[allow(dead_code)]
#[path = "../../../e2-task/src/k3_abi.rs"]
mod k3_abi;
#[path = "../k3_script.rs"]
mod k3_script;
#[path = "../k3_spawn.rs"]
mod k3_spawn;
#[path = "../k3_world.rs"]
mod k3_world;
#[allow(dead_code)]
#[path = "../object_allocator.rs"]
mod object_allocator;
#[allow(dead_code)]
#[path = "../pl011.rs"]
mod pl011;
#[allow(dead_code)]
#[path = "../slots.rs"]
mod slots;

use a5_mmio::{DeviceMapper, Page};
use k3_abi::*;
use k3_spawn::{Seed, ensure_tables, init_free_page_addr, spawn};
use k3_world::World;
use object_allocator::ObjectAllocator;
use slots::SlotWindow;

const SERVER_ELF: &[u8] = include_bytes!(env!("K3_SERVER_ELF"));
const CLIENT_ELF: &[u8] = include_bytes!(env!("K3_CLIENT_ELF"));
pub(crate) const MODE: &str = match option_env!("K3_MODE") {
    Some(m) => m,
    None => "design",
};
pub(crate) const MUTANT: &str = match option_env!("K3_MUTANT") {
    Some(m) => m,
    None => "none",
};

const SMMU_PADDR: usize = 0x0905_0000;
/// The BARs `edu::discover` assigns: the start of the 32-bit PCI window, 1 MiB per device.
const BAR_BASE: usize = 0x1000_0000;
const BAR_STEP: usize = 0x10_0000;
/// The root task's own view of the devices' registers (for the late trigger of test T4): 2 MiB window from here.
const LATE_BASE: usize = 0x4200_0000;
/// How many of the top slots of the root CNode are searched for the frame capabilities the mapper made.
const SCAN_SLOTS: usize = 400;

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

/// Routes the runtime's panic messages to the user-level console.
// SAFETY: the symbol name and the signature are the ones `sel4_panicking_env` declares for its output hook, so every
// caller agrees on the ABI; the function only calls the safe `put_byte`.
#[unsafe(no_mangle)]
#[allow(non_snake_case)]
fn __sel4_panicking_env__debug_put_char(c: u8) {
    pl011::put_byte(c);
}

#[root_task(heap_size = 512 * 1024)]
fn main(bootinfo: &sel4::BootInfoPtr) -> sel4::Result<Never> {
    match run(bootinfo) {
        Ok((passed, failed, void)) => {
            uprintln!("K3 summary passed={} failed={} void={} console_bytes_dropped={} mmio_range_errors={}", passed, failed, void, pl011::dropped(), a5_mmio::range_errors());
            uprintln!("{}", if failed == 0 && void == 0 { "K3_PASS" } else { "K3_FAIL" });
        }
        Err(fail) => {
            uprintln!("K3 setup or run error: {:?}", fail);
            uprintln!("K3_FAIL");
        }
    }
    uprintln!("K3_DONE");
    sel4::init_thread::suspend_self()
}

/// The slot of a frame capability for `paddr` among the root CNode's top slots (where the device mapper puts its frames).
fn find_frame(bootinfo: &sel4::BootInfo, paddr: usize) -> Result<sel4::CPtr, Fail> {
    let end = bootinfo.empty().range().end;
    for index in (end - SCAN_SLOTS..end).rev() {
        let slot = sel4::init_thread::Slot::<sel4::cap_type::Granule>::from_index(index);
        if slot.cap().frame_get_address() == Ok(paddr) {
            return Ok(slot.cptr());
        }
    }
    Err(Fail::Check("no frame capability for a device page"))
}

/// Indices of the boot untypeds the pool and the server's own memory come from: the smallest RAM untypeds of at least
/// 2^15 and 2^16 bytes, other than the one the allocator uses. Boot untypeds have no parent.
fn pick_untypeds(bootinfo: &sel4::BootInfo, allocator_bits: usize) -> Result<(usize, usize), Fail> {
    let mut candidates: Vec<(usize, usize)> = bootinfo
        .untyped_list()
        .iter()
        .enumerate()
        .filter(|(_, d)| !d.is_device() && d.size_bits() < allocator_bits)
        .map(|(i, d)| (d.size_bits(), i))
        .collect();
    candidates.sort();
    let pool = candidates.iter().find(|(bits, _)| *bits >= 15).ok_or(Fail::NoUntyped)?.1;
    let srv = candidates.iter().find(|(bits, i)| *bits >= 16 && *i != pool).ok_or(Fail::NoUntyped)?.1;
    Ok((pool, srv))
}

fn run(bootinfo: &sel4::BootInfoPtr) -> Result<(u32, u32, u32), Fail> {
    let mut allocator = ObjectAllocator::new(bootinfo)?;
    let mut mapper = DeviceMapper::new(bootinfo, &mut allocator)?;
    // The UART first: it and the SMMU are in one device untyped, which is retyped in ascending order.
    pl011::init(mapper.map_device(bootinfo, pl011::UART_PADDR)?);
    uprintln!(
        "K3 start built-for PRINTING={} MAX_NUM_NODES={} ARM_HYPERVISOR_SUPPORT={} mode={} mutant={}",
        sel4::sel4_cfg_bool!(PRINTING),
        sel4::sel4_cfg_usize!(MAX_NUM_NODES),
        sel4::sel4_cfg_bool!(ARM_HYPERVISOR_SUPPORT),
        MODE,
        MUTANT
    );
    // The two SMMU register pages (the mapper retypes and maps them in this task as well; the server gets copies).
    mapper.map_device(bootinfo, SMMU_PADDR)?;
    mapper.map_device(bootinfo, SMMU_PADDR + 0x1_0000)?;
    let devices = edu::discover(bootinfo, &mut mapper)?;
    if devices.len() != 2 {
        return Err(Fail::Check("the machine must have exactly two edu devices"));
    }
    let smmu0 = find_frame(bootinfo, SMMU_PADDR)?;
    let smmu1 = find_frame(bootinfo, SMMU_PADDR + 0x1_0000)?;
    let bar = [find_frame(bootinfo, BAR_BASE)?, find_frame(bootinfo, BAR_BASE + BAR_STEP)?];
    let sids = [devices[0].sid, devices[1].sid];

    // The untypeds: the pool and the server's memory are boot untypeds (no parent); M's memory is a child of one the root
    // task keeps, as a memory manager would give a process.
    let largest_bits = bootinfo.untyped_list().iter().filter(|d| !d.is_device()).map(|d| d.size_bits()).max().ok_or(Fail::NoUntyped)?;
    let (pool_i, srv_i) = pick_untypeds(bootinfo, largest_bits)?;
    let pool = bootinfo.untyped().index(pool_i).cap();
    let srv = bootinfo.untyped().index(srv_i).cap();
    uprintln!(
        "K3 untypeds pool_bits={} pool_paddr={:#x} srv_bits={} srv_paddr={:#x} (boot untypeds, moved to the server)",
        bootinfo.untyped_list()[pool_i].size_bits(),
        bootinfo.untyped_list()[pool_i].paddr(),
        bootinfo.untyped_list()[srv_i].size_bits(),
        bootinfo.untyped_list()[srv_i].paddr()
    );
    let mm_untyped: sel4::cap::Untyped = allocator.allocate(sel4::ObjectBlueprint::Untyped { size_bits: 16 })?.cast();

    // Endpoints and notifications.
    let r_ep = allocator.allocate_fixed_sized::<sel4::cap_type::Endpoint>()?;
    let es = allocator.allocate_fixed_sized::<sel4::cap_type::Endpoint>()?;
    let mut go: [Option<sel4::cap::Notification>; 5] = [None; 5];
    for id in [ID_C1, ID_C2, ID_M, ID_S] {
        go[id as usize] = Some(allocator.allocate_fixed_sized::<sel4::cap_type::Notification>()?);
    }
    let mut slots = SlotWindow::new(bootinfo)?;
    let root = sel4::init_thread::slot::CNODE.cap();
    let mut mint_slot = |src: sel4::CPtr, rights: sel4::CapRights, badge: u64| -> Result<sel4::CPtr, Fail> {
        let index = slots.take()?;
        let dst = sel4::init_thread::Slot::<sel4::cap_type::Unspecified>::from_index(index);
        root.absolute_cptr(dst.cptr()).mint(&root.absolute_cptr(src), rights, badge)?;
        Ok(dst.cptr())
    };
    let call_rights = || sel4::CapRightsBuilder::none().write(true).grant_reply(true).build();
    let client_rights = || sel4::CapRightsBuilder::none().write(true).grant(true).build();
    let admin = mint_slot(es.cptr(), call_rights(), BADGE_ADMIN)?;
    let scratch = {
        let index = slots.take()?;
        sel4::init_thread::Slot::<sel4::cap_type::Unspecified>::from_index(index).cptr()
    };

    // The seeds of each domain.
    let image_server = File::parse(SERVER_ELF).map_err(|_| Fail::Elf)?;
    let image_client = File::parse(CLIENT_ELF).map_err(|_| Fail::Elf)?;
    let free_page_addr = init_free_page_addr(bootinfo)?;
    let go_of = |id: u64| go[id as usize].map(|n| n.cptr()).ok_or(Fail::Check("no notification"));
    let common = |id: u64| -> Result<Vec<Seed>, Fail> {
        Ok(alloc::vec![
            Seed::Mint { slot: SLOT_REPORT, src: r_ep.cptr(), rights: call_rights(), badge: id, what: "send to the conductor's endpoint, badged with the task id" },
            Seed::Mint { slot: SLOT_FAULT, src: r_ep.cptr(), rights: call_rights(), badge: id | FAULT_FLAG, what: "fault endpoint (the conductor's endpoint, fault badge)" },
            Seed::Mint { slot: SLOT_GO, src: go_of(id)?, rights: sel4::CapRights::read_only(), badge: 0, what: "step notification (wait only)" },
        ])
    };
    let mut seeds_by_id: Vec<(u64, &'static str, Vec<Seed>)> = Vec::new();
    let mut s_seeds = common(ID_S)?;
    s_seeds.extend([
        Seed::Copy { slot: SLOT_ES, src: es.cptr(), what: "the server's own endpoint (receive)" },
        Seed::Copy { slot: SLOT_DEVICE, src: smmu0, what: "SMMU registers, page 0 (device frame)" },
        Seed::Copy { slot: SLOT_DEVICE1, src: smmu1, what: "SMMU registers, page 1 (device frame)" },
        Seed::Move { slot: SLOT_UNTYPED_A, src: srv.cptr(), what: "U_srv: boot untyped for the SMMU's tables and queues (moved)" },
        Seed::Move { slot: SLOT_UNTYPED_B, src: pool.cptr(), what: "U_pool: the DMA pool, a boot untyped (moved: no ancestor anywhere)" },
    ]);
    seeds_by_id.push((ID_S, "S", s_seeds));
    for (id, name, bar_cap) in [(ID_C1, "C1", bar[0]), (ID_C2, "C2", bar[1])] {
        let mut seeds = common(id)?;
        seeds.extend([
            Seed::Mint { slot: SLOT_ES, src: es.cptr(), rights: client_rights(), badge: id, what: "send to the server, badged with the client id (write, grant)" },
            Seed::Copy { slot: SLOT_DEVICE, src: bar_cap, what: "BAR frame of its own edu device (device frame)" },
        ]);
        seeds_by_id.push((id, name, seeds));
    }
    let mut m_seeds = common(ID_M)?;
    m_seeds.extend([
        Seed::Mint { slot: SLOT_ES, src: es.cptr(), rights: client_rights(), badge: ID_M, what: "send to the server, badged with the client id (write, grant)" },
        Seed::Copy { slot: SLOT_UNTYPED_A, src: mm_untyped.cptr(), what: "U_M: a child of an untyped the root task (as memory manager) keeps" },
    ]);
    seeds_by_id.push((ID_M, "M", m_seeds));

    // Start the server first, then the others.
    let mut domains = Vec::new();
    for (id, name, seeds) in &seeds_by_id {
        for (kind, what, slot) in k3_spawn::seed_table(seeds) {
            uprintln!("K3 seed dom={} slot={} kind={} what=\"{}\"", name, slot, kind, what);
        }
        let image = if *id == ID_S { &image_server } else { &image_client };
        domains.push(spawn(&mut allocator, image, free_page_addr, *id, name, seeds)?);
        uprintln!("K3 domain name={} id={} started", name, id);
    }

    // The root task's own view of each device's registers, for the late trigger.
    ensure_tables(&mut allocator, sel4::init_thread::slot::VSPACE.cap(), LATE_BASE, 2 * a5_mmio::PAGE)?;
    let mut late = [None::<Page>; 2];
    for (i, cap) in bar.iter().enumerate() {
        let copy = slots.take()?;
        let copy_cptr = sel4::init_thread::Slot::<sel4::cap_type::Unspecified>::from_index(copy).cptr();
        root.absolute_cptr(copy_cptr).copy(&root.absolute_cptr(*cap), sel4::CapRights::all())?;
        let va = LATE_BASE + i * a5_mmio::PAGE;
        sel4::init_thread::Slot::<sel4::cap_type::Granule>::from_index(copy).cap().frame_map(
            sel4::init_thread::slot::VSPACE.cap(),
            va,
            sel4::CapRights::read_write(),
            sel4::VmAttributes::NONE,
        )?;
        // SAFETY: just mapped read-write at `va` in this task's address space; never unmapped.
        late[i] = Some(unsafe { Page::from_addr(va) });
    }
    let late = [late[0].ok_or(Fail::Layout)?, late[1].ok_or(Fail::Layout)?];

    let mut world = World { r_ep, es_admin: sel4::cap::Endpoint::from_bits(admin.bits()), scratch, go, domains };
    let ctx = k3_script::Context { sids, late, mm_untyped, root_slots: slots };
    k3_script::run(&mut world, ctx)
}
