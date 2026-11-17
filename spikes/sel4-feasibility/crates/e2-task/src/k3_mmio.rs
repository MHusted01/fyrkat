//
// SPDX-License-Identifier: BSD-2-Clause
//

//! Volatile access to pages a K3 task has mapped, and the memory barrier the DMA sequences need. Adapted from the root
//! task's `a5_mmio.rs` (which is an input of earlier evidence and is not shared). A `Page` is constructed only by `Page::at`,
//! an `unsafe fn`: the caller vouches that the page is mapped read-write at that address and stays mapped while the `Page`
//! is used. The accessors reduce every offset to an aligned offset inside the page, so no call reaches outside it.

use core::ptr;

pub const PAGE: usize = 4096;

#[derive(Clone, Copy)]
pub struct Page {
    va: usize,
}

fn in_page(off: usize, width: usize) -> usize {
    off & (PAGE - width)
}

impl Page {
    /// # Safety
    ///
    /// `va` must be page-aligned and mapped readable and writable in this address space, and must stay mapped (and not be
    /// covered by a Rust reference) for as long as the returned `Page` is used.
    pub unsafe fn at(va: usize) -> Self {
        Self { va }
    }

    pub fn addr(self) -> usize {
        self.va
    }

    pub fn r32(self, off: usize) -> u32 {
        // SAFETY: `Page::at`'s contract; `in_page` keeps the aligned 4-byte access inside the page; volatile is required
        // for device registers and for memory a device writes.
        unsafe { ptr::read_volatile((self.va + in_page(off, 4)) as *const u32) }
    }

    pub fn w32(self, off: usize, value: u32) {
        // SAFETY: as `r32`.
        unsafe { ptr::write_volatile((self.va + in_page(off, 4)) as *mut u32, value) }
    }

    pub fn r64(self, off: usize) -> u64 {
        // SAFETY: as `r32`, with an 8-byte access.
        unsafe { ptr::read_volatile((self.va + in_page(off, 8)) as *const u64) }
    }

    pub fn w64(self, off: usize, value: u64) {
        // SAFETY: as `r32`, with an 8-byte access.
        unsafe { ptr::write_volatile((self.va + in_page(off, 8)) as *mut u64, value) }
    }
}

/// `dsb sy`: completes every earlier memory access of this thread before the next instruction.
pub fn barrier() {
    // SAFETY: a barrier instruction available at EL0; it touches no register and no memory.
    unsafe { core::arch::asm!("dsb sy", options(nostack, preserves_flags)) }
}
