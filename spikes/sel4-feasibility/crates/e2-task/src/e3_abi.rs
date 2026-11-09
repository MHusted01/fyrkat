//
// SPDX-License-Identifier: BSD-2-Clause
//

//! E3 contract between the root task and the two identical E3 tasks (ids 1 and 2): which capability sits in which
//! slot of a task's own CNode, the badges, and the message codes. Spike code, not product code.
//!
//! Capability derivation, all rooted in the root task's own capability `P` to the endpoint (retyped from an untyped):
//! `P` -> `SLOT_DERIVED` (a mint with a badge) -> `SLOT_COPY` (a copy of that mint), in each task's CNode; after the
//! revoke, `P` -> `SLOT_FRESH` (a new mint). `Q` is a second endpoint that `P` does not govern: `SLOT_CONTROL`.

/// Each task's CNode has 2^CNODE_BITS slots.
pub const CNODE_BITS: usize = 4;

/// A badged mint of `P` (write and grant-reply): the capability the revoke must remove.
pub const SLOT_DERIVED: u64 = 1;
/// A copy of `SLOT_DERIVED` (same badge): a descendant that is not a mint, to show the revoke reaches copies too.
pub const SLOT_COPY: u64 = 2;
/// A badged mint of the unrelated endpoint `Q`: the control that the revoke must not touch.
pub const SLOT_CONTROL: u64 = 3;
/// The task's go-signal: a read-only capability to a notification that the root task signals.
pub const SLOT_GO: u64 = 4;
/// The task's event signal to the root task: a write-only badged capability to the notification bound to the root.
pub const SLOT_EVENT: u64 = 5;
/// Never populated at any time (negative control for the error a call on an empty slot returns).
pub const SLOT_EMPTY: u64 = 6;
/// Empty until after the revoke, when the root task mints a new child of `P` into it.
pub const SLOT_FRESH: u64 = 7;

/// Badge bases; the task id (1 or 2) is added. They are all below `EVENT_MASK`.
pub const BADGE_DERIVED: u64 = 0xB300;
pub const BADGE_CONTROL: u64 = 0xD300;
pub const BADGE_FRESH: u64 = 0xF300;
/// Event badge of task `id`: bit `15 + id`, so the root task can tell a signal from an IPC badge.
pub const fn event_badge(id: u64) -> u64 {
    1 << (15 + id)
}
/// Every bit any event badge can use (ids 1 and 2).
pub const EVENT_MASK: u64 = event_badge(1) | event_badge(2);

/// What a task asks in the first message register; the root task answers `code + 1` and the task id.
pub const CODE_DERIVED_BEFORE: u64 = 0x100;
pub const CODE_COPY_BEFORE: u64 = 0x200;
pub const CODE_CONTROL_BEFORE: u64 = 0x300;
pub const CODE_DERIVED_AFTER: u64 = 0x400;
pub const CODE_COPY_AFTER: u64 = 0x500;
pub const CODE_EMPTY_AFTER: u64 = 0x600;
pub const CODE_CONTROL_AFTER: u64 = 0x700;
pub const CODE_FRESH_AFTER: u64 = 0x800;
