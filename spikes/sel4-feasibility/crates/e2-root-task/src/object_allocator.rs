//
// Copyright 2024, Colias Group, LLC
//
// SPDX-License-Identifier: BSD-2-Clause
//
// Adapted from seL4/rust-sel4 v6.0.0 spawn-task/src/object_allocator.rs. Changed: errors are returned
// (`Fail`) instead of unwrapped.
//

use core::ops::Range;

use crate::Fail;

pub(crate) struct ObjectAllocator {
    empty_slots: Range<usize>,
    ut: sel4::cap::Untyped,
}

impl ObjectAllocator {
    pub(crate) fn new(bootinfo: &sel4::BootInfo) -> Result<Self, Fail> {
        Ok(Self {
            empty_slots: bootinfo.empty().range(),
            ut: find_largest_kernel_untyped(bootinfo)?,
        })
    }

    pub(crate) fn allocate(
        &mut self,
        blueprint: sel4::ObjectBlueprint,
    ) -> Result<sel4::cap::Unspecified, Fail> {
        let slot_index = self.empty_slots.next().ok_or(Fail::OutOfSlots)?;
        self.ut.untyped_retype(
            &blueprint,
            &sel4::init_thread::slot::CNODE
                .cap()
                .absolute_cptr_for_self(),
            slot_index,
            1,
        )?;
        Ok(sel4::init_thread::Slot::from_index(slot_index).cap())
    }

    pub(crate) fn allocate_fixed_sized<T: sel4::CapTypeForObjectOfFixedSize>(
        &mut self,
    ) -> Result<sel4::Cap<T>, Fail> {
        Ok(self.allocate(T::object_blueprint())?.cast())
    }

    pub(crate) fn allocate_variable_sized<T: sel4::CapTypeForObjectOfVariableSize>(
        &mut self,
        size_bits: usize,
    ) -> Result<sel4::Cap<T>, Fail> {
        Ok(self.allocate(T::object_blueprint(size_bits))?.cast())
    }
}

fn find_largest_kernel_untyped(bootinfo: &sel4::BootInfo) -> Result<sel4::cap::Untyped, Fail> {
    let (ut_ix, _desc) = bootinfo
        .untyped_list()
        .iter()
        .enumerate()
        .filter(|(_i, desc)| !desc.is_device())
        .max_by_key(|(_i, desc)| desc.size_bits())
        .ok_or(Fail::NoUntyped)?;

    Ok(bootinfo.untyped().index(ut_ix).cap())
}
