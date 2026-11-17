//
// SPDX-License-Identifier: BSD-2-Clause
//

//! K3 contract between the root task (R), the SMMU server (S) and the tasks that use it. Shared by `#[path]`, not through
//! `lib.rs` (which is an input of the E3 evidence and must not change). Spike code, not product code.
//!
//! Every task has the same CNode layout (2^`CNODE_BITS` slots); which slots are populated depends on its role
//! (results/K3.md section 3). A cptr in a task's own CSpace is the slot number.

pub const CNODE_BITS: usize = 8;

// ---- slots common to every task ------------------------------------------------------------------------------------
/// A CNode capability to the task's own CNode (full rights): the task may copy, mint, move, revoke, delete and retype into it.
pub const SLOT_SELF_CNODE: u64 = 1;
/// A VSpace capability to the task's own address space.
pub const SLOT_SELF_VSPACE: u64 = 2;
/// Send end of R's endpoint, badged with the task's id: reports, parameter requests, and (as the fault endpoint) faults.
pub const SLOT_REPORT: u64 = 3;
/// R's step signal: the task waits here; the badge word it receives is the step to run.
pub const SLOT_GO: u64 = 4;
/// Clients and M: a badged send capability to S's endpoint. S: the receive end.
pub const SLOT_ES: u64 = 5;
/// Client: the BAR frame of its `edu`. S: page 0 of the SMMU's registers.
pub const SLOT_DEVICE: u64 = 6;
/// S: page 1 of the SMMU's registers.
pub const SLOT_DEVICE1: u64 = 7;
/// S: `U_srv`, the untyped for the SMMU's tables and queues. M: `U_M`, the untyped R (as memory manager) gave it.
pub const SLOT_UNTYPED_A: u64 = 8;
/// S: `U_pool`, the DMA pool (a boot untyped moved from R).
pub const SLOT_UNTYPED_B: u64 = 9;
/// Send end of R's endpoint with the fault badge: where this task's faults are delivered (and nowhere else).
pub const SLOT_FAULT: u64 = 10;
/// Slots whose capabilities are endpoints or notifications or the task's own CNode and VSpace: invoking one of them with an
/// operation meant for another type is an IPC (or a signal) and not an error, so type probes must skip them.
pub const fn is_communication_slot(s: u64) -> bool {
    matches!(s, SLOT_SELF_CNODE | SLOT_SELF_VSPACE | SLOT_REPORT | SLOT_GO | SLOT_ES | SLOT_FAULT)
}
/// First of `RECV_SLOTS` empty slots that capabilities received by IPC are placed in.
pub const SLOT_RECV_FIRST: u64 = 32;
pub const RECV_SLOTS: u64 = 16;
/// First slot a task may use for objects it creates itself (M's frames, S's objects).
pub const SLOT_OWN_FIRST: u64 = 64;
/// Last slot, used by tests as a destination for probing copies.
pub const SLOT_LAST: u64 = (1 << CNODE_BITS) - 1;

// ---- S's own layout ------------------------------------------------------------------------------------------------
pub const POOL_PAGES: usize = 8;
/// `U_i`, the 4 KiB untyped of pool page i, at `SLOT_POOL_UNTYPED + i`.
pub const SLOT_POOL_UNTYPED: u64 = 64;
/// `F_i`, the frame retyped from `U_i`, at `SLOT_POOL_FRAME + i`.
pub const SLOT_POOL_FRAME: u64 = 80;
/// The frames S keeps for the SMMU structures, from here on.
pub const SLOT_SMMU_RAM: u64 = 100;
/// Scratch slot the server's probe of a mapped page retypes into.
pub const SLOT_PROBE: u64 = 119;
/// A donated frame lands here in the naive build only.
pub const SLOT_DONATION: u64 = 120;
/// Frames of donated memory S keeps (naive build).
pub const SLOT_DONATED_FIRST: u64 = 121;

// ---- virtual addresses ---------------------------------------------------------------------------------------------
/// The window of 2 MiB in each task's address space that R prepares with page tables: 512 pages.
pub const WINDOW_BASE: usize = 0x5000_0000;
pub const PAGE: usize = 4096;
/// Client: the BAR page is mapped at page 0 of the window; buffers at pages 1 and up.
pub const WINDOW_BAR_PAGE: usize = 0;

// ---- identities ----------------------------------------------------------------------------------------------------
/// Task ids; also the badge of the task's capability to R's endpoint and the client id S sees.
pub const ID_C1: u64 = 1;
pub const ID_C2: u64 = 2;
pub const ID_M: u64 = 3;
pub const ID_S: u64 = 4;
/// Badge of R's capability to S's endpoint.
pub const BADGE_ADMIN: u64 = 0x100;
/// Added to a task id: the badge of its fault capability.
pub const FAULT_FLAG: u64 = 0x1000;

// ---- S's protocol (label of the call; replies carry a result code in the label) ------------------------------------
pub const OP_ALLOC: u64 = 1;
pub const OP_FREE: u64 = 2;
pub const OP_DONATE: u64 = 3;
pub const OP_ADMIN_PING: u64 = 10;
/// mr0 = client id, mr1 = stream id, mr2 = address space index.
pub const OP_ADMIN_BIND: u64 = 11;
/// mr0 = client id.
pub const OP_ADMIN_DEAD: u64 = 12;
/// Replies with the number of event records since the last call: mr0 = on C1's stream, mr1 = on C2's stream,
/// mr2 = on other streams, mr3 = how many times the SMMU reported that it dropped records (queue overflow) so far.
pub const OP_ADMIN_EVENTS: u64 = 13;
/// Replies with counters: mr0 = commands issued, mr1 = syncs, mr2 = revokes, mr3 = pages allocated.
pub const OP_ADMIN_STATS: u64 = 14;
/// mr0 = handle: replies mr0 = state (0 free, 1 mapped), mr1 = owner, mr2 = physical address.
pub const OP_ADMIN_PAGEINFO: u64 = 15;
/// mr0 = index of one of the server's SMMU structure pages (0 stream table, 1 command queue, 2 event queue, 3 to 5 the
/// first address space's tables, 6 its context descriptor, 7 to 9 and 10 the second's): replies mr0 = physical address.
pub const OP_ADMIN_SMMU_PA: u64 = 16;
/// mr0 = handle: the server asks the kernel about the page. Replies mr0 = physical address of the frame (0 if the frame
/// capability is not usable), mr1 = result of a retype of the page's untyped (0 if it succeeded and was undone, else 1 + the
/// kernel's error number).
pub const OP_ADMIN_PROBE: u64 = 17;

pub const RC_OK: u64 = 0;
pub const RC_BAD_OP: u64 = 1;
pub const RC_NOT_OWNER: u64 = 2;
pub const RC_NO_MEMORY: u64 = 3;
pub const RC_BAD_HANDLE: u64 = 4;
pub const RC_NO_DONATIONS: u64 = 5;
pub const RC_ADMIN_ONLY: u64 = 6;
pub const RC_SMMU: u64 = 7;
pub const RC_BAD_ARGS: u64 = 8;

// ---- R's protocol (label of the call from a task) ------------------------------------------------------------------
/// mr0 = step: the task asks for the parameters of the step it was signalled to run; R replies with four words.
pub const LBL_PARAMS: u64 = 1;
/// mr0 = tag, mr1..mr3 = values: one observation. R prints it and replies.
pub const LBL_REPORT: u64 = 2;
/// mr0 = step: the step is finished.
pub const LBL_DONE: u64 = 3;

// ---- steps (the badge R signals a task with); parameters come from R ------------------------------------------------
pub const STEP_INIT: u64 = 1;
/// params: local page index k. Reports [rc, iova, handle, physical address of the frame].
pub const STEP_ALLOC: u64 = 2;
/// params: k, base. Writes the pattern `base ^ j` into words 0..16 of page k.
pub const STEP_FILL: u64 = 3;
/// params: k, base_a, base_b. Reports [words equal to pattern a, words equal to pattern b].
pub const STEP_COUNT: u64 = 4;
/// params: kind, a, b. kind 0: device reads 64 bytes from bus address a into its buffer. 1: device writes 64 bytes of its
/// buffer to bus address a. 2: program the device to copy its buffer to bus address a without starting. 3: as 2, and start the
/// transfer without waiting for it. Reports [finished] (for 3: 1 once the transfer is started).
pub const STEP_DEVOP: u64 = 5;
/// params: handle. Reports [rc].
pub const STEP_FREE: u64 = 6;
/// Everything a client can do to its own CSpace; reports one line per operation class.
pub const STEP_CSPACE_ATTACK: u64 = 7;
/// params: k. Unmaps page k from the task's address space and maps it again. Reports [unmap rc, map rc].
pub const STEP_REMAP: u64 = 8;
/// params: k. The task revokes and deletes its capability to page k's frame (not the mapping first). Reports [revoke rc, delete rc].
pub const STEP_DROP_FRAME: u64 = 9;
/// Tries the admin operations and re-badging. Reports [rc admin ping, rc admin events, rc mint re-badge].
pub const STEP_TRY_ADMIN: u64 = 10;
/// M: params: k. Retypes a 4 KiB frame from `U_M` into its own slot, maps it at page k. Reports [rc retype, rc map, physical address].
pub const STEP_M_FRAME: u64 = 11;
/// M: params: k, target client id. Calls S to donate page k's frame for the client's stream. Reports [rc, iova].
pub const STEP_M_DONATE: u64 = 12;
/// params: k. Maps the frame received in receive slot k' (given in params[1]) at page k. Reports [rc].
pub const STEP_MAP_RECEIVED: u64 = 13;
pub const STEP_IDLE: u64 = 14;
/// params: n. Allocates n pages in a row (no mapping); reports [pages obtained, last rc, 0, 0]. Resource-exhaustion check.
pub const STEP_ALLOC_MANY: u64 = 15;

/// The number of 32-bit-word-sized pattern words every test uses (64 bytes).
pub const PATTERN_WORDS: usize = 16;
pub const PATTERN_BYTES: u64 = 64;
/// Word j of the pattern with base `b`.
pub const fn pattern(base: u64, j: usize) -> u32 {
    ((base as u32) ^ (j as u32)).wrapping_mul(0x9e37_79b1)
}
