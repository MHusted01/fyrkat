//
// SPDX-License-Identifier: BSD-2-Clause
//
// K3: building a protection domain (a VSpace with the task's image and a window of page tables, a CNode with exactly the
// capabilities listed for it, a TCB with a fault endpoint), and starting it. Adapted from `e3_spawn.rs` (E3 evidence input,
// not shared): the CNode here has 2^8 slots, is given a capability to itself and to its VSpace, and the TCB's fault
// endpoint is a slot of the task's own CNode. Included by `bin/k3_root_task.rs` only.
//

use alloc::vec::Vec;

use object::Object;

use crate::child_vspace::{ChildVSpace, create_child_vspace, map_secret};
use crate::k3_abi::{CNODE_BITS, PAGE, SLOT_FAULT, SLOT_SELF_CNODE, SLOT_SELF_VSPACE, WINDOW_BASE};
use crate::{Fail, ObjectAllocator};

/// One capability to put in a task's CNode.
#[derive(Clone)]
pub(crate) enum Seed {
    /// A copy of the root task's capability in `src`.
    Copy { slot: u64, src: sel4::CPtr, what: &'static str },
    /// A mint of the root task's capability in `src`, with rights and a badge.
    Mint { slot: u64, src: sel4::CPtr, rights: sel4::CapRights, badge: u64, what: &'static str },
    /// A move: the capability leaves the root task's CNode. Used for the authority that must not stay with the root task.
    Move { slot: u64, src: sel4::CPtr, what: &'static str },
}

impl Seed {
    pub(crate) fn slot(&self) -> u64 {
        match self {
            Seed::Copy { slot, .. } | Seed::Mint { slot, .. } | Seed::Move { slot, .. } => *slot,
        }
    }

    pub(crate) fn describe(&self) -> (&'static str, &'static str, u64) {
        match self {
            Seed::Copy { what, slot, .. } => ("copy", what, *slot),
            Seed::Mint { what, slot, .. } => ("mint", what, *slot),
            Seed::Move { what, slot, .. } => ("move", what, *slot),
        }
    }
}

/// A started domain, as the root task keeps it: the capabilities it needs to supervise it.
pub(crate) struct Domain {
    pub(crate) id: u64,
    pub(crate) name: &'static str,
    pub(crate) cnode: sel4::cap::CNode,
    pub(crate) tcb: sel4::cap::Tcb,
    pub(crate) vspace: sel4::cap::VSpace,
}

fn root() -> sel4::cap::CNode {
    sel4::init_thread::slot::CNODE.cap()
}

/// Everything in a task's CNode is placed by the root task: the seeds, and the capabilities to the CNode and VSpace themselves.
fn make_cnode(allocator: &mut ObjectAllocator, vspace: sel4::cap::VSpace, seeds: &[Seed]) -> Result<sel4::cap::CNode, Fail> {
    let cnode = allocator.allocate_variable_sized::<sel4::cap_type::CNode>(CNODE_BITS)?;
    let at = |slot: u64| cnode.absolute_cptr_from_bits_with_depth(slot, CNODE_BITS);
    at(SLOT_SELF_CNODE).copy(&root().absolute_cptr(cnode.cptr()), sel4::CapRights::all())?;
    at(SLOT_SELF_VSPACE).copy(&root().absolute_cptr(vspace.cptr()), sel4::CapRights::all())?;
    for seed in seeds {
        let dst = at(seed.slot());
        match seed {
            Seed::Copy { src, .. } => dst.copy(&root().absolute_cptr(*src), sel4::CapRights::all())?,
            Seed::Mint { src, rights, badge, .. } => dst.mint(&root().absolute_cptr(*src), rights.clone(), *badge)?,
            Seed::Move { src, .. } => dst.move_(&root().absolute_cptr(*src))?,
        }
    }
    Ok(cnode)
}

/// Creates a domain from `image` with the given seeds and starts it. `fault` is the slot (in the task's CNode) of its fault
/// endpoint capability; it must be among the seeds.
pub(crate) fn spawn<'a>(
    allocator: &mut ObjectAllocator,
    image: &'a impl Object<'a>,
    free_page_addr: usize,
    id: u64,
    name: &'static str,
    seeds: &[Seed],
) -> Result<Domain, Fail> {
    if !seeds.iter().any(|s| s.slot() == SLOT_FAULT) {
        return Err(Fail::Check("a domain needs a fault endpoint seed"));
    }
    let child: ChildVSpace = create_child_vspace(
        allocator,
        image,
        sel4::init_thread::slot::VSPACE.cap(),
        free_page_addr,
        sel4::init_thread::slot::ASID_POOL.cap(),
    )?;
    // The window's page tables: `map_secret` installs the tables for the page it maps, and the window is exactly the 2 MiB
    // one level-3 table covers, so mapping its last page installs them for all of it. That page (a fresh frame nothing else
    // refers to) stays mapped and is never used by any program.
    map_secret(allocator, child.vspace, WINDOW_BASE + 511 * PAGE)?;
    let cnode = make_cnode(allocator, child.vspace, seeds)?;
    let tcb = allocator.allocate_fixed_sized::<sel4::cap_type::Tcb>()?;
    tcb.tcb_configure(
        sel4::CPtr::from_bits(SLOT_FAULT),
        cnode,
        sel4::CNodeCapData::new(0, sel4::WORD_SIZE - CNODE_BITS),
        child.vspace,
        child.ipc_buffer_addr as sel4::Word,
        child.ipc_buffer_cap,
    )?;
    let mut ctx = sel4::UserContext::default();
    *ctx.pc_mut() = image.entry();
    tcb.tcb_write_all_registers(true, &mut ctx)?;
    Ok(Domain { id, name, cnode, tcb, vspace: child.vspace })
}

const GRANULE_SIZE: usize = sel4::FrameObjectType::GRANULE.bytes();

#[repr(C, align(4096))]
struct FreePagePlaceholder(#[allow(dead_code)] [u8; GRANULE_SIZE]);

// SAFETY (of every use of this `static mut`): zero-initialized, so valid before any write; never read or written and no
// reference is made to it, only its address is taken with `addr_of!`. The root task is single-threaded. It exists only to
// reserve one page-aligned page of the root task's own image, which `init_free_page_addr` unmaps and then uses as a window.
static mut FREE_PAGE_PLACEHOLDER: FreePagePlaceholder = FreePagePlaceholder([0; GRANULE_SIZE]);

/// Frees one page-aligned granule of the root task's own image to use as a temporary window for copying ELF segments into the
/// new tasks' frames. As E2's and E3's.
pub(crate) fn init_free_page_addr(bootinfo: &sel4::BootInfo) -> Result<usize, Fail> {
    let addr = core::ptr::addr_of!(FREE_PAGE_PLACEHOLDER) as usize;
    // SAFETY: the linker defines `__executable_start` (the first byte of this image), so the declaration resolves; only its
    // address is taken, never its value, and it is declared as a byte so that no wider type is claimed for what lies there.
    unsafe extern "C" {
        static __executable_start: u8;
    }
    let image_start = core::ptr::addr_of!(__executable_start) as usize;
    bootinfo
        .user_image_frames()
        .index(addr / GRANULE_SIZE - image_start / GRANULE_SIZE)
        .cap()
        .frame_unmap()?;
    Ok(addr)
}

/// Installs the page tables that cover `[base, base + len)` in `vspace`, skipping any level that already has one.
pub(crate) fn ensure_tables(allocator: &mut ObjectAllocator, vspace: sel4::cap::VSpace, base: usize, len: usize) -> Result<(), Fail> {
    for level in 1..sel4::vspace_levels::NUM_LEVELS {
        let span = 1usize << sel4::vspace_levels::span_bits(level);
        let ty = sel4::TranslationTableObjectType::from_level(level).ok_or(Fail::Layout)?;
        let mut addr = base & !(span - 1);
        while addr < base + len {
            let result = allocator
                .allocate(ty.blueprint())?
                .cast::<sel4::cap_type::UnspecifiedIntermediateTranslationTable>()
                .generic_intermediate_translation_table_map(ty, vspace, addr, sel4::VmAttributes::default());
            match result {
                Ok(()) | Err(sel4::Error::DeleteFirst) => {}
                Err(e) => return Err(Fail::Sel4(e)),
            }
            addr += span;
        }
    }
    Ok(())
}

/// Lists a domain's seeds as log lines' data.
pub(crate) fn seed_table(seeds: &[Seed]) -> Vec<(&'static str, &'static str, u64)> {
    seeds.iter().map(Seed::describe).collect()
}
