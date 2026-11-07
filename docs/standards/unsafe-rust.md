# Unsafe Rust

`unsafe` moves a proof obligation from the compiler to the author and reviewer. This standard
makes that obligation explicit.

## When unsafe is allowed

Only where safe Rust cannot express the operation, and only for:

- Talking to hardware, firmware or the CPU: registers, MMIO, page tables, inline assembly.
- Implementing a primitive that has a safe interface around it, such as an allocator or a
  lock.
- Calling a foreign interface, such as UEFI services.

It is not allowed to avoid a borrow-checker error, to gain a small speedup without a
measurement, or because a safe version is longer. Task runner and tooling code uses
`#![forbid(unsafe_code)]`.

## Rules

1. **Minimal scope.** One unsafe operation per block, enforced by
   `clippy::multiple_unsafe_ops_per_block`. Keep surrounding logic in safe code.
2. **`// SAFETY:` on every block**, directly above it, enforced by
   `clippy::undocumented_unsafe_blocks`. It states why each precondition holds here. "The
   pointer is valid" is not enough: say why it is valid, and who guarantees it.
3. **`# Safety` on every `unsafe fn`**, naming what the caller must guarantee, enforced by
   `clippy::missing_safety_doc`.
4. **`unsafe_op_in_unsafe_fn` is denied.** An `unsafe fn` body still needs its own blocks.
5. **Safe wrappers.** Expose a safe API whose type or checks make misuse impossible. If a safe
   wrapper cannot guarantee the precondition, the wrapper function is itself `unsafe`.
6. **Data layout is explicit.** Use `#[repr(C)]` or `#[repr(transparent)]` for anything shared
   with hardware or firmware, and cite the specification section for the layout.
7. **No unsafe in `build.rs` or tests of safe code** without the same documentation.

## Review

Each PR that adds or changes unsafe code states so in its description. It is reviewed by the
`reviewer` agent or a human who did not write it, and the `unsafe-audit` skill lists every
block for the review. A reviewer who cannot verify a SAFETY argument rejects it.

## Tooling

- Today there is no unsafe product code, only `tests/boot-smoke`. Miri and fuzzing are
  deferred until there is something to run them on; see [testing](testing.md).
- Unsafe code that depends on the target hardware gets a test on the emulator and is marked as
  not validated on hardware until it has been.
