//
// SPDX-License-Identifier: BSD-2-Clause
//

//! The contract between the root task and the two tasks: which capability sits in which slot of a task's
//! own CNode, the badges, and the one address the client must not be able to read.

/// Each task's CNode has 2^CNODE_BITS slots.
pub const CNODE_BITS: usize = 4;

/// Client and server: the endpoint the two tasks share. The server holds it unbadged with full rights,
/// the client holds a copy badged `CLIENT_BADGE` with write and grant-reply rights only.
pub const SLOT_ENDPOINT: u64 = 1;
/// Client only: a capability to the client's own CNode (for the badge-forging test and the wrong-type test).
pub const SLOT_CNODE: u64 = 3;
/// Both: the endpoint to the root task that the kernel uses to deliver this task's faults.
pub const SLOT_FAULT_EP: u64 = 4;
/// Client only: a slot that is never populated (the empty-slot test invokes it).
pub const SLOT_EMPTY: u64 = 5;
/// Client only: an empty destination slot for the badge-forging mint.
pub const SLOT_MINT_DEST: u64 = 6;

pub const CLIENT_BADGE: u64 = 0xA11CE;
pub const FAULT_BADGE_CLIENT: u64 = 1;
pub const FAULT_BADGE_SERVER: u64 = 2;

/// Mapped (with a secret in it) in the server's address space only. Nothing is mapped here for the client.
pub const SECRET_ADDR: usize = 0x5000_0000;
pub const SECRET_VALUE: u64 = 0x5EC2_E7;

/// libsel4 `seL4_Error` values (libsel4/include/sel4/errors.h): a failed invocation returns its code as the
/// reply label.
pub const SEL4_INVALID_CAPABILITY: u64 = 2;
pub const SEL4_ILLEGAL_OPERATION: u64 = 3;
