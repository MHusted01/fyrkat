//
// SPDX-License-Identifier: BSD-2-Clause
//
// Free capability slots for code that needs a slot without an object: copies, mints, and retypes from an untyped of its own.
//

use crate::Fail;

/// The window starts this many slots into the root CNode's empty range and has this many slots. The object allocator
/// counts up from the start of the range, and the device mapper counts down from its end and never comes within 1024
/// slots of the start, so the window `[512, 1024)` belongs to neither as long as fewer than 512 objects are allocated;
/// `SlotWindow::new` refuses an empty range too small for that arrangement.
const WINDOW_START: usize = 512;
const WINDOW_SLOTS: usize = 512;
const MAPPER_MARGIN: usize = 1024;

pub(crate) struct SlotWindow {
    next: usize,
    end: usize,
}

impl SlotWindow {
    pub(crate) fn new(bootinfo: &sel4::BootInfo) -> Result<Self, Fail> {
        let empty = bootinfo.empty().range();
        if empty.end - empty.start < WINDOW_START + WINDOW_SLOTS + MAPPER_MARGIN {
            return Err(Fail::OutOfSlots);
        }
        let next = empty.start + WINDOW_START;
        Ok(Self { next, end: next + WINDOW_SLOTS })
    }

    /// The next free slot of the window, as an index into the root CNode.
    pub(crate) fn take(&mut self) -> Result<usize, Fail> {
        if self.next >= self.end {
            return Err(Fail::OutOfSlots);
        }
        self.next += 1;
        Ok(self.next - 1)
    }
}
