//
// Copyright 2024, Colias Group, LLC
//
// SPDX-License-Identifier: BSD-2-Clause
//
// Adapted from seL4/rust-sel4 v6.0.0 crates/examples/root-task/spawn-task/src/main.rs.
//

//! E2 root task: builds two isolated tasks (client A, server B), each with its own address space, CNode,
//! TCB and IPC buffer, one shared endpoint; the fault supervisor. `E2_PASS` needs a VM-fault-shaped message at the secret
//! address through the client's fault capability, which the client can send itself, so it does not prove a fault happened.

#![no_std]
#![no_main]
#![allow(clippy::useless_conversion)]

extern crate alloc;

use core::ptr;

use object::{File, Object};

use e2_task::abi::{
    CLIENT_BADGE, CNODE_BITS, FAULT_BADGE_CLIENT, FAULT_BADGE_SERVER, SECRET_ADDR, SLOT_CNODE,
    SLOT_ENDPOINT, SLOT_FAULT_EP,
};
use sel4_root_task::{Never, root_task};

mod child_vspace;
mod object_allocator;

use child_vspace::{ChildVSpace, create_child_vspace, map_secret};
use object_allocator::ObjectAllocator;

const SERVER_ELF: &[u8] = include_bytes!(env!("E2_SERVER_ELF"));
const CLIENT_ELF: &[u8] = include_bytes!(env!("E2_CLIENT_ELF"));

const GRANULE_SIZE: usize = sel4::FrameObjectType::GRANULE.bytes();

/// Why the root task could not finish building or checking the system. Only ever printed, through `Debug`.
#[derive(Debug)]
#[allow(dead_code)]
pub(crate) enum Fail {
    Sel4(sel4::Error),
    OutOfSlots,
    NoUntyped,
    Elf,
    Layout,
    UnexpectedFault,
}

impl From<sel4::Error> for Fail {
    fn from(e: sel4::Error) -> Self {
        Fail::Sel4(e)
    }
}

#[root_task(heap_size = 1024 * 64)]
fn main(bootinfo: &sel4::BootInfoPtr) -> sel4::Result<Never> {
    match run(bootinfo) {
        Ok(()) => sel4::debug_println!("E2_PASS"),
        Err(fail) => sel4::debug_println!("E2_FAIL root: {:?}", fail),
    }
    sel4::init_thread::suspend_self()
}

fn run(bootinfo: &sel4::BootInfoPtr) -> Result<(), Fail> {
    sel4::debug_println!("E2_ROOT start");
    let mut allocator = ObjectAllocator::new(bootinfo)?;
    let free_page_addr = init_free_page_addr(bootinfo)?;

    // The endpoint the two tasks share, and the endpoint on which this task receives their faults.
    let shared_ep = allocator.allocate_fixed_sized::<sel4::cap_type::Endpoint>()?;
    let fault_ep = allocator.allocate_fixed_sized::<sel4::cap_type::Endpoint>()?;

    let server_image = File::parse(SERVER_ELF).map_err(|_| Fail::Elf)?;
    let client_image = File::parse(CLIENT_ELF).map_err(|_| Fail::Elf)?;

    // Server first: unbadged endpoint with full rights, plus its secret in memory only it maps.
    let server = create_child_vspace(
        &mut allocator,
        &server_image,
        sel4::init_thread::slot::VSPACE.cap(),
        free_page_addr,
        sel4::init_thread::slot::ASID_POOL.cap(),
    )?;
    map_secret(&mut allocator, server.vspace, SECRET_ADDR)?;
    spawn(
        &mut allocator,
        &server,
        &server_image,
        &[
            (SLOT_ENDPOINT, shared_ep.cptr(), Rights::Full, 0),
            (SLOT_FAULT_EP, fault_ep.cptr(), Rights::SendOnly, FAULT_BADGE_SERVER),
        ],
        false,
    )?;

    // Client: a badged endpoint it can only send on, and a capability to its own CNode.
    let client = create_child_vspace(
        &mut allocator,
        &client_image,
        sel4::init_thread::slot::VSPACE.cap(),
        free_page_addr,
        sel4::init_thread::slot::ASID_POOL.cap(),
    )?;
    spawn(
        &mut allocator,
        &client,
        &client_image,
        &[
            (SLOT_ENDPOINT, shared_ep.cptr(), Rights::SendOnly, CLIENT_BADGE),
            (SLOT_FAULT_EP, fault_ep.cptr(), Rights::SendOnly, FAULT_BADGE_CLIENT),
        ],
        true,
    )?;

    // Supervise: the only fault this system should produce is the client reading the server's secret.
    let (info, badge) = fault_ep.recv(());
    let fault = sel4::with_ipc_buffer(|ib| sel4::Fault::new(ib, &info));
    match fault {
        sel4::Fault::VmFault(vm) if badge == FAULT_BADGE_CLIENT && vm.addr() == SECRET_ADDR as u64 => {
            sel4::debug_println!("E2_ROOT client vm fault at {:#x}, badge {}", vm.addr(), badge);
            Ok(())
        }
        other => {
            sel4::debug_println!("E2_ROOT unexpected fault from badge {}: {:?}", badge, other);
            Err(Fail::UnexpectedFault)
        }
    }
}

/// The only two rights sets E2 hands out.
#[derive(Clone, Copy)]
enum Rights {
    /// Everything: the server's receiving end of the shared endpoint.
    Full,
    /// Write and grant-reply: enough to `Call`, or for the kernel to deliver a fault, and nothing else.
    SendOnly,
}

impl Rights {
    fn build(self) -> sel4::CapRights {
        match self {
            Rights::Full => sel4::CapRights::all(),
            Rights::SendOnly => sel4::CapRightsBuilder::none().write(true).grant_reply(true).build(),
        }
    }
}

/// Gives a task a CNode holding `seeds` (slot, source capability in the root CNode, rights, badge) and, if
/// `with_cnode`, a capability to that CNode in `SLOT_CNODE`; then starts it.
fn spawn<'a>(
    allocator: &mut ObjectAllocator,
    child: &ChildVSpace,
    image: &'a impl Object<'a>,
    seeds: &[(u64, sel4::CPtr, Rights, u64)],
    with_cnode: bool,
) -> Result<(), Fail> {
    let root_cnode = sel4::init_thread::slot::CNODE.cap();
    let cnode = allocator.allocate_variable_sized::<sel4::cap_type::CNode>(CNODE_BITS)?;

    for &(slot, src, rights, badge) in seeds {
        cnode
            .absolute_cptr_from_bits_with_depth(slot, CNODE_BITS)
            .mint(&root_cnode.absolute_cptr(src), rights.build(), badge)?;
    }
    if with_cnode {
        cnode
            .absolute_cptr_from_bits_with_depth(SLOT_CNODE, CNODE_BITS)
            .mint(&root_cnode.absolute_cptr(cnode.cptr()), sel4::CapRights::all(), 0)?;
    }

    let tcb = allocator.allocate_fixed_sized::<sel4::cap_type::Tcb>()?;
    tcb.tcb_configure(
        sel4::CPtr::from_bits(SLOT_FAULT_EP),
        cnode,
        sel4::CNodeCapData::new(0, sel4::WORD_SIZE - CNODE_BITS),
        child.vspace,
        child.ipc_buffer_addr as sel4::Word,
        child.ipc_buffer_cap,
    )?;

    let mut ctx = sel4::UserContext::default();
    *ctx.pc_mut() = image.entry();
    tcb.tcb_write_all_registers(true, &mut ctx)?;
    Ok(())
}

// // //

#[repr(C, align(4096))]
struct FreePagePlaceholder(#[allow(dead_code)] [u8; GRANULE_SIZE]);

static mut FREE_PAGE_PLACEHOLDER: FreePagePlaceholder = FreePagePlaceholder([0; GRANULE_SIZE]);

/// Frees one page-aligned granule of this task's own image to use as a temporary window for copying ELF
/// segments into the new tasks' frames.
fn init_free_page_addr(bootinfo: &sel4::BootInfo) -> Result<usize, Fail> {
    let addr = ptr::addr_of!(FREE_PAGE_PLACEHOLDER) as usize;
    user_image_frame_slot(bootinfo, addr).cap().frame_unmap()?;
    Ok(addr)
}

fn user_image_frame_slot(
    bootinfo: &sel4::BootInfo,
    addr: usize,
) -> sel4::init_thread::Slot<sel4::cap_type::Granule> {
    unsafe extern "C" {
        static __executable_start: usize;
    }
    let user_image_addr = ptr::addr_of!(__executable_start) as usize;
    bootinfo
        .user_image_frames()
        .index(addr / GRANULE_SIZE - user_image_addr / GRANULE_SIZE)
}
