# A1 rerun with the corrected `Cargo.lock`: a separate verification result

**This is not the A1 result and does not replace it.** The original A1 result ([A1](A1.md), **Pass**, label
**U**) and its evidence ([A1/](A1/)) are unchanged, and the original hashes stay the record of the original
lock file. This file records one authorized verification run made after the owner decided to restore the six
`Cargo.lock` versions that A1 had not been approved for.

- **Outcome of the rerun:** the A1 acceptance criterion holds again with the corrected lock: two clean builds
  give an identical kernel, loader and root task, and the boot image differs only by QEMU's random
  device-tree seeds. Label **U**. **One output differs from the original run: the root task.** Section
  "What changed, and what it means" accounts for every differing byte.
- **Authorization:** the owner's message of 2026-11-08 (the plan's Amendments): restore the six crates.io
  versions approved in rust-sel4 `v6.0.0`, and run A1 once more with the same methodology and acceptance
  criteria. "One run" was read as one A1 procedure, which is two clean builds, because that is what the
  criterion compares. Nothing else was re-run.
- **Date:** 2026-11-08. **Run by:** Sonnet. **Plan:** [spike plan](../../../docs/research/sel4-spike-plan.md).
- **Command (unchanged):** `spikes/sel4-feasibility/build.sh`, twice, each from a clean `build/`.

## What was changed before the run

Only `Cargo.lock` in the spike workspace, with four offline commands (`cargo update --offline -p NAME
--precise VERSION`, [02](A1-rerun/02-lock-correction.txt)). No `Cargo.toml`, toolchain, pin, script or other
input changed, and the loader and `add-payload` still build from rust-sel4's own approved lock.

| Crate | Original spike lock (A1) | Corrected lock (rerun) | Approved at `v6.0.0` |
|---|---|---|---|
| `cc` | 1.11.0 | **1.10.0** | 1.10.0 |
| `log` | 0.4.35 | **0.4.34** | 0.4.34 |
| `psm` | 0.1.32 | **0.1.24** | 0.1.24 |
| `pest_stack_guard` | 1.0.1 | **1.0.0** | 1.0.0 |
| `ar_archive_writer` | 0.5.3 | removed | absent |
| `object` | 0.39.1 | removed (no longer in this workspace's graph) | 0.40.0 (used by other crates of that workspace) |

Checked after the change [Measured]: every registry package of the corrected lock exists, with the same
version and checksum, in the approved rust-sel4 lock (0 differences); exactly these four downgrades and two
removals differ from the original spike lock, and all git and path packages are identical; the rerun's compile
log shows `cc v1.10.0`, `log v0.4.34`, `pest_stack_guard v1.0.0` and `psm v0.1.24`
([03](A1-rerun/03-build-rerun1.txt)). The original lock is kept unchanged (SHA-256 `c92d1dca…`, also in Git at
`b563904`). The corrected lock has 79 packages against 81, and 51 changed lines: 16 of them are the `s1-root-task` block moving to its sorted position, with no package changed. File 02 is a condensed record written after the commands were run (cargo's output is summarized); its diff is the real diff. The two `# Note` lines at the top of 02 were added in response to the final review; the file is otherwise unchanged, and its earlier version (SHA-256 `879919dd…`) is in Git at `0b84ded`.

## Environment

Unchanged from A1 [Measured: [01](A1-rerun/01-preflight.txt)]: seL4 `62e345c`, rust-sel4 `c819c27`, nightly
`nightly-2026-08-21` with Tier 1 components only, the same Homebrew inventory (386 formulae, sorted-list
SHA-256 `58168eca…`, equal to A1's recorded after-state), and the same source pins (seL4, rust-sel4). The Homebrew-pins
section of 01 is empty: nothing was captured there. The Homebrew pins, the Command Line Tools / libclang version and the macOS
build were **not re-recorded** at the rerun. A check made afterwards found them equal to A1's, but that check is not part of the
evidence. Nothing was installed.

## Results

| Output | Original A1 run | Rerun, build 1 (39.4 s) | Rerun, build 2 (38.5 s) |
|---|---|---|---|
| `kernel.elf` | `95891911d0bed9e4…` | `95891911d0bed9e4…` | `95891911d0bed9e4…` |
| `sel4-kernel-loader.elf` | `8be9d6df5e569b1c…` | `8be9d6df5e569b1c…` | `8be9d6df5e569b1c…` |
| `s1-root-task.elf` | `a7c6be9afdefeab6…` | **`64fcc25c933418d0…`** | **`64fcc25c933418d0…`** |
| `image.elf` | `bc4831cd…` / `bb9bb79e…` | `cf6a0d6795ad3602…` | `388e120845f44049…` |

Full hashes: [build 1](A1-rerun/04-sums-rerun1.txt), [build 2](A1-rerun/06-sums-rerun2.txt), and the original
[run 1](A1/16-sums-run1.txt) and [run 2](A1/18-sums-run2.txt).

- **Kernel and loader: identical to the original.** The corrected lock does not touch them.
- **Root task: identical across the two rerun builds, different from the original.**
- **Boot image: differs in every build.** The rerun's two images differ in 40 bytes, all inside the embedded
  device tree and all in `rng-seed` and `kaslr-seed`, the cause found in A1.

## What changed, and what it means

`compare-a1-runs.py` ([07](A1-rerun/07-comparison-with-original.txt)) accounts for every differing byte
[Measured]:

1. **Root task, `s1-root-task.elf`:** 65,552 bytes originally and 65,568 now. All sections have the same size
   except `.strtab` (17,274 to 17,287 bytes). The loaded sections that differ are `.rodata` (763 of 6,835 bytes)
   and `.text` (18 of 19,180 bytes). There are 4,795 instruction words in both, and **8 differ**, every one an
   `adr` or `add` that computes the address of a constant in `.rodata`. `.data`, `.eh_frame` and `.eh_frame_hdr`
   are byte-identical.
2. **The cause of the shifted addresses** [Measured, then Inferred]. Both binaries embed the path of the
   generated `invocations.rs` of `sel4-sys` in a panic-location string, and the path contains Cargo's hashed
   build-script directory name: `3d413dfeda2b8c15` in the original, `315641f36d34bbc3` in the rerun, which are
   exactly the two builds' `sel4-sys` build directories [Measured]. That name is a hash over the build's
   dependency set [Inferred: Cargo's behaviour, not tested in isolation], so changing the lock changes it,
   changes the string pool, and moves the offsets that those 8 instructions load. The mangled Rust symbol hashes
   also change (the string table grows by 13 bytes). Which of the six crates changes the hash was not
   separated, and does not need to be.
3. **Boot image:** 782 bytes differ between the original image and an image made by `add-payload` from the
   original inputs plus the new root task, and all 782 are root-task bytes: 763 in `.rodata`, 18 in `.text`, and
   1 in the ELF header's section-table offset, which moved by 16 with the longer `.strtab`. That image then
   differs from the rerun's own image only in the device-tree seeds (39 bytes). As a control, `add-payload`
   reproduces the original image from the original inputs exactly, and its binary is byte-identical in both runs.

**Implications.**

- **The root-task hash is a function of the lock file** (and of the build path, see below), not only of the
  source. A1's claim "two clean builds give an identical root task" still holds within one lock. It does not
  hold across the two locks. Any later reference to a root-task hash must say which lock produced it. The
  corrected lock is the one the owner approved, so the rerun's hashes are the reference for it.
- **No functional difference was found in the code** by static comparison: the same instruction count, 8
  address-computation instructions differ, and the initialized data and unwind tables are identical
  [Measured]. That is **not** a behavioural test. The A1 image has never booted (loader and kernel fail to
  run, see [A3](A3.md), finding 1), so no execution evidence exists for either root task [Measured].
- **The A1 outcome is unchanged.** The original run stands as recorded. The rerun adds that the criterion also
  holds with the approved lock.
- The deviation D13 (six unapproved lock versions) is resolved by this change, see [deviations](deviations.md).

## Limitations

- Both builds ran on one machine, in one directory. A root-task ELF embeds the absolute path of the build
  directory in its panic-location strings [Measured]. **Do not publish the binary**: it carries the builder's
  home path. Only hashes are published. Cross-path and cross-machine reproducibility are still untested.
- Rerun build 1's image was kept; its install prefix was not, so the seed check of rerun 1 reads its device tree
  out of its own image.
- `log` 0.4.34 against 0.4.35 was not tested alone, so this rerun does not say which crate is responsible for
  the changed directory hash.

## Evidence

[A1-rerun/](A1-rerun/): preflight (01), the lock-file correction with its diff (02), the two clean builds (03,
05) and their checksums (04, 06), and the comparison with the original (07). They are sanitized public copies,
listed in the [manifest](evidence-manifest.txt), and `verify-evidence.py` checks the conclusions above from them
and from the repository's `Cargo.lock`. The comparison tool is [`compare-a1-runs.py`](../compare-a1-runs.py).
The preserved original run (binaries and lock file) is kept locally in the gitignored `external/`.
