//
// Copyright 2024, Colias Group, LLC
//
// SPDX-License-Identifier: BSD-2-Clause
//
// Adapted from seL4/rust-sel4 v6.0.0 spawn-task/src/child_vspace.rs. Changed: errors are returned (`Fail`)
// instead of unwrapped, and `map_secret` is new.
//

use alloc::vec::Vec;
use core::ops::Range;

use object::{
    Object, ObjectSegment, SegmentFlags,
    elf::{PF_R, PF_W, PF_X},
};

use crate::{Fail, ObjectAllocator};

const GRANULE_SIZE: usize = sel4::FrameObjectType::GRANULE.bytes();

pub(crate) struct ChildVSpace {
    pub(crate) vspace: sel4::cap::VSpace,
    pub(crate) ipc_buffer_addr: usize,
    pub(crate) ipc_buffer_cap: sel4::cap::Granule,
}

pub(crate) fn create_child_vspace<'a>(
    allocator: &mut ObjectAllocator,
    image: &'a impl Object<'a>,
    caller_vspace: sel4::cap::VSpace,
    free_page_addr: usize,
    asid_pool: sel4::cap::AsidPool,
) -> Result<ChildVSpace, Fail> {
    let vspace = allocator.allocate_fixed_sized::<sel4::cap_type::VSpace>()?;
    asid_pool.asid_pool_assign(vspace)?;

    let image_footprint = footprint(image)?;

    map_intermediate_translation_tables(
        allocator,
        vspace,
        image_footprint.start..(image_footprint.end + GRANULE_SIZE),
    )?;

    map_image(allocator, vspace, image_footprint.clone(), image, caller_vspace, free_page_addr)?;

    let ipc_buffer_addr = image_footprint.end;
    let ipc_buffer_cap = allocator.allocate_fixed_sized::<sel4::cap_type::Granule>()?;
    ipc_buffer_cap.frame_map(
        vspace,
        ipc_buffer_addr,
        sel4::CapRights::read_write(),
        sel4::VmAttributes::default(),
    )?;

    Ok(ChildVSpace {
        vspace,
        ipc_buffer_addr,
        ipc_buffer_cap,
    })
}

/// Maps one fresh, zeroed, writable granule at `addr` in `vspace`. Nothing else holds a capability to it.
pub(crate) fn map_secret(
    allocator: &mut ObjectAllocator,
    vspace: sel4::cap::VSpace,
    addr: usize,
) -> Result<(), Fail> {
    map_intermediate_translation_tables(allocator, vspace, addr..(addr + GRANULE_SIZE))?;
    let frame = allocator.allocate_fixed_sized::<sel4::cap_type::Granule>()?;
    frame.frame_map(
        vspace,
        addr,
        sel4::CapRights::read_write(),
        sel4::VmAttributes::default(),
    )?;
    Ok(())
}

fn footprint<'a>(image: &'a impl Object<'a>) -> Result<Range<usize>, Fail> {
    let min = image.segments().map(|seg| seg.address()).min().ok_or(Fail::Elf)?;
    let max = image
        .segments()
        .map(|seg| seg.address() + seg.size())
        .max()
        .ok_or(Fail::Elf)?;
    let min: usize = min.try_into().map_err(|_| Fail::Elf)?;
    let max: usize = max.try_into().map_err(|_| Fail::Elf)?;
    Ok(coarsen_footprint(&(min..max), GRANULE_SIZE))
}

fn map_intermediate_translation_tables(
    allocator: &mut ObjectAllocator,
    vspace: sel4::cap::VSpace,
    footprint: Range<usize>,
) -> Result<(), Fail> {
    for level in 1..sel4::vspace_levels::NUM_LEVELS {
        let span_bytes = 1 << sel4::vspace_levels::span_bits(level);
        let footprint_at_level = coarsen_footprint(&footprint, span_bytes);
        for i in 0..(footprint_at_level.len() / span_bytes) {
            let ty = sel4::TranslationTableObjectType::from_level(level).ok_or(Fail::Layout)?;
            let addr = footprint_at_level.start + i * span_bytes;
            allocator
                .allocate(ty.blueprint())?
                .cast::<sel4::cap_type::UnspecifiedIntermediateTranslationTable>()
                .generic_intermediate_translation_table_map(
                    ty,
                    vspace,
                    addr,
                    sel4::VmAttributes::default(),
                )?;
        }
    }
    Ok(())
}

fn map_image<'a>(
    allocator: &mut ObjectAllocator,
    vspace: sel4::cap::VSpace,
    footprint: Range<usize>,
    image: &'a impl Object<'a>,
    caller_vspace: sel4::cap::VSpace,
    free_page_addr: usize,
) -> Result<(), Fail> {
    let num_pages = footprint.len() / GRANULE_SIZE;
    let mut pages = Vec::new();
    for _ in 0..num_pages {
        pages.push((
            allocator.allocate_fixed_sized::<sel4::cap_type::Granule>()?,
            sel4::CapRightsBuilder::none(),
        ));
    }

    for seg in image.segments() {
        let segment_addr = usize::try_from(seg.address()).map_err(|_| Fail::Elf)?;
        let segment_size = usize::try_from(seg.size()).map_err(|_| Fail::Elf)?;
        let segment_footprint =
            coarsen_footprint(&(segment_addr..(segment_addr + segment_size)), GRANULE_SIZE);
        let num_pages_spanned_by_segment = segment_footprint.len() / GRANULE_SIZE;
        let mut data = seg.data().map_err(|_| Fail::Elf)?;
        let segment_data_footprint = coarsen_footprint(
            &(segment_addr..(segment_addr + data.len())),
            GRANULE_SIZE,
        );
        let num_pages_spanned_by_segment_data = segment_data_footprint.len() / GRANULE_SIZE;
        let segment_page_index_offset = (segment_footprint.start - footprint.start) / GRANULE_SIZE;

        for (_, rights) in pages
            .get_mut(segment_page_index_offset..)
            .and_then(|p| p.get_mut(..num_pages_spanned_by_segment))
            .ok_or(Fail::Layout)?
        {
            add_rights(rights, seg.flags())?;
        }

        let mut offset_into_page = segment_addr % GRANULE_SIZE;
        for (page_cap, _) in pages
            .get(segment_page_index_offset..)
            .and_then(|p| p.get(..num_pages_spanned_by_segment_data))
            .ok_or(Fail::Layout)?
        {
            let data_len = (GRANULE_SIZE - offset_into_page).min(data.len());

            page_cap.frame_map(
                caller_vspace,
                free_page_addr,
                sel4::CapRights::read_write(),
                sel4::VmAttributes::default(),
            )?;
            // SAFETY: `free_page_addr` is a page-aligned, otherwise unused granule of this task's image
            // that was unmapped and has just been replaced by a mapping of `page_cap`; the destination
            // range `offset_into_page..offset_into_page + data_len` lies inside that one granule, and `data`
            // is a slice of the embedded ELF with at least `data_len` bytes.
            unsafe {
                ((free_page_addr + offset_into_page) as *mut u8).copy_from(data.as_ptr(), data_len);
            }
            page_cap.frame_unmap()?;

            data = data.get(data_len..).ok_or(Fail::Elf)?;
            offset_into_page = 0;
        }
    }

    for (i, (page_cap, rights)) in pages.into_iter().enumerate() {
        let addr = footprint.start + i * GRANULE_SIZE;
        page_cap.frame_map(vspace, addr, rights.build(), sel4::VmAttributes::default())?;
    }
    Ok(())
}

fn add_rights(rights: &mut sel4::CapRightsBuilder, flags: SegmentFlags) -> Result<(), Fail> {
    match flags {
        SegmentFlags::Elf { p_flags, .. } => {
            if p_flags.contains(PF_R) {
                *rights = rights.read(true);
            }
            if p_flags.contains(PF_W) {
                *rights = rights.write(true);
            }
            if p_flags.contains(PF_X) {
                *rights = rights.grant(true);
            }
            Ok(())
        }
        _ => Err(Fail::Elf),
    }
}

fn coarsen_footprint(footprint: &Range<usize>, granularity: usize) -> Range<usize> {
    round_down(footprint.start, granularity)..footprint.end.next_multiple_of(granularity)
}

const fn round_down(n: usize, b: usize) -> usize {
    n - n % b
}
