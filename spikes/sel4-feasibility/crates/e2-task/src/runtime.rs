//
// Copyright 2024, Colias Group, LLC
//
// SPDX-License-Identifier: BSD-2-Clause
//
// Adapted from seL4/rust-sel4 v6.0.0 crates/examples/root-task/spawn-task/child/src/runtime.rs. Changed:
// no heap (no allocator, no `unwrap`), and the entry point reports a missing IPC buffer instead of panicking.

use core::ptr;

use sel4::CapTypeForFrameObjectOfFixedSize;
use sel4_panicking::catch_unwind;
use sel4_panicking_env::abort;

use crate::main;

const STACK_SIZE: usize = 1024 * 64;

sel4_runtime_common::declare_stack!(STACK_SIZE);

sel4_panicking_env::register_debug_put_char!(sel4::debug_put_char);

sel4_runtime_common::declare_entrypoint_with_stack_init!();

sel4_runtime_common::declare_rust_entrypoint! {
    entrypoint()
}

fn entrypoint() -> ! {
    // SAFETY: the root task mapped a granule at the first granule-aligned address at or after `_end` and
    // passed that address to the kernel as this thread's IPC buffer, so it is a valid, exclusive IpcBuffer.
    match unsafe { get_ipc_buffer().as_mut() } {
        Some(ipc_buffer) => sel4::set_ipc_buffer(ipc_buffer),
        None => abort!("no IPC buffer"),
    }

    match catch_unwind(main) {
        #[allow(unreachable_patterns)]
        Ok(never) => never,
        Err(_) => abort!("main() panicked"),
    }
}

fn get_ipc_buffer() -> *mut sel4::IpcBuffer {
    unsafe extern "C" {
        static _end: usize;
    }
    (ptr::addr_of!(_end) as usize)
        .next_multiple_of(sel4::cap_type::Granule::FRAME_OBJECT_TYPE.bytes())
        as *mut sel4::IpcBuffer
}
