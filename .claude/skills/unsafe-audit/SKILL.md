---
name: unsafe-audit
description: List every unsafe block, function and impl in the repository and check each against the unsafe Rust standard. Use after any change that adds or edits unsafe code.
---

Audit unsafe code against docs/standards/unsafe-rust.md.

1. Find all uses: `grep -rnE '\bunsafe\b' --include='*.rs' . --exclude-dir=target --exclude-dir=spikes`.
2. For each one record: location, kind (block, `unsafe fn`, `unsafe impl`, `extern`, `no_mangle`), and the operation it performs.
3. Check that each block has a `// SAFETY:` comment directly above it that states why the conditions hold, not what the code does. Check that `unsafe fn` has a `# Safety` doc section.
4. Check the scope is minimal: one unsafe operation per block, with safe code outside it.
5. Confirm the lints still deny `undocumented_unsafe_blocks` and `unsafe_op_in_unsafe_fn` (see `[workspace.lints]` in Cargo.toml), and that `cargo xtask check` passes.
6. Report a table of findings, then list any block whose SAFETY argument you could not verify. Do not rewrite the code in the same pass. Suggest independent review by the `reviewer` agent for anything non-trivial.
