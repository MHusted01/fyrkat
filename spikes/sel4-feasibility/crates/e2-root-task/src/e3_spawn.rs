//
// Copyright 2024, Colias Group, LLC (adapted from seL4/rust-sel4 spawn-task, tag v6.0.0)
//
// SPDX-License-Identifier: BSD-2-Clause
//
// E3: building a task's CNode and starting it, as two steps (E2's `spawn` does both at once). Included by
// `bin/e3_root_task.rs` only; the E2 root task does not use this file.
//

use core::ptr;

use e2_task::e3_abi::CNODE_BITS;
use object::Object;

use crate::child_vspace::ChildVSpace;
use crate::{Fail, ObjectAllocator};

const GRANULE_SIZE: usize = sel4::FrameObjectType::GRANULE.bytes();

/// One capability to place in a task's CNode: a mint of `src` (a slot of the root task's CNode) with `rights` and
/// `badge`, in `slot`.
pub(crate) struct Seed {
    pub(crate) slot: u64,
    pub(crate) src: sel4::CPtr,
    pub(crate) rights: sel4::CapRights,
    pub(crate) badge: u64,
}

/// Allocates a CNode of 2^`CNODE_BITS` slots and mints each seed into it.
pub(crate) fn make_cnode(
    allocator: &mut ObjectAllocator,
    seeds: &[Seed],
) -> Result<sel4::cap::CNode, Fail> {
    let root_cnode = sel4::init_thread::slot::CNODE.cap();
    let cnode = allocator.allocate_variable_sized::<sel4::cap_type::CNode>(CNODE_BITS)?;
    for seed in seeds {
        cnode
            .absolute_cptr_from_bits_with_depth(seed.slot, CNODE_BITS)
            .mint(&root_cnode.absolute_cptr(seed.src), seed.rights.clone(), seed.badge)?;
    }
    Ok(cnode)
}

/// Gives the task a TCB with `cnode` as its CSpace and no fault handler (so nothing it does can reach the root
/// task through a fault), and starts it at the image's entry point.
pub(crate) fn start<'a>(
    allocator: &mut ObjectAllocator,
    child: &ChildVSpace,
    image: &'a impl Object<'a>,
    cnode: sel4::cap::CNode,
) -> Result<(), Fail> {
    let tcb = allocator.allocate_fixed_sized::<sel4::cap_type::Tcb>()?;
    tcb.tcb_configure(
        sel4::CPtr::from_bits(0),
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

#[repr(C, align(4096))]
struct FreePagePlaceholder(#[allow(dead_code)] [u8; GRANULE_SIZE]);

// SAFETY (of every use of this `static mut`): it is zero-initialized, so it is valid before any write; it is never
// read or written, and no reference to it is made: only its address is taken, with `addr_of!`. The root task is a
// single thread, so there is no concurrent access either. It exists only to reserve one page-aligned page of this
// task's own image, which `init_free_page_addr` then unmaps and uses as a window.
static mut FREE_PAGE_PLACEHOLDER: FreePagePlaceholder = FreePagePlaceholder([0; GRANULE_SIZE]);

/// Frees one page-aligned granule of this task's own image to use as a temporary window for copying ELF
/// segments into the new tasks' frames. Same as E2's.
pub(crate) fn init_free_page_addr(bootinfo: &sel4::BootInfo) -> Result<usize, Fail> {
    let addr = ptr::addr_of!(FREE_PAGE_PLACEHOLDER) as usize;
    user_image_frame_slot(bootinfo, addr).cap().frame_unmap()?;
    Ok(addr)
}

fn user_image_frame_slot(
    bootinfo: &sel4::BootInfo,
    addr: usize,
) -> sel4::init_thread::Slot<sel4::cap_type::Granule> {
    // SAFETY: the linker defines `__executable_start` (the first byte of this root task's image), so the declaration
    // resolves. Only its address is taken, never its value (it is not read), and it is declared as a byte so that
    // no wider type is claimed for what lies there.
    unsafe extern "C" {
        static __executable_start: u8;
    }
    let user_image_addr = ptr::addr_of!(__executable_start) as usize;
    bootinfo
        .user_image_frames()
        .index(addr / GRANULE_SIZE - user_image_addr / GRANULE_SIZE)
}
