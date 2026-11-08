# Deviations from the approved tooling, for owner review

**This list is not an approval.** The owner's message of 2026-11-08 says to document these as
deviations requiring review and not to treat that message as retroactive blanket approval. A row marked
**owner-approved** records one specific answer the owner gave in the working session on 2026-11-08 (see
the plan's Amendments). Every other row, and every detail of a row that is not named as approved, is
**not approved**. Each row says what was done, why, and how to undo it.

| # | Deviation | Why | Status | How to undo |
|---|---|---|---|---|
| D1 | GNU cpio 2.15, already installed as the keg-only Homebrew formula `cpio`, is put on `PATH` by [`build-sel4test.sh`](../build-sel4test.sh) (`/opt/homebrew/opt/cpio/bin`). **History:** the first sel4test runs used a custom Python stand-in for cpio, written because the agent wrongly believed GNU cpio was not available. It was removed. Its logs are in `A3/shim-era/`; an independent review found its archive differed from GNU cpio's in 3 bytes (the inode field) | seL4's `cmake-tool` needs `--append`, `--reproducible` and `--owner`, which macOS `cpio` lacks | **Uses an existing tool; not individually approved.** No installation was needed | Remove the `PATH` entry. The sel4test build then fails at the archive step |
| D2 | [`build-protoc.sh`](../build-protoc.sh): protoc 3.20.3 built from source at the pinned commit `fe271ab76f2ad2b2b28c10443865d2af21e27e0e` (tag `v3.20.3`) into the gitignored `external/` | nanopb's generator needs a protoc matching the venv's Python `protobuf` 3.20.3 (pinned `<4` by `sel4-deps`). Homebrew's protoc 36.2 does not. No Apple Silicon 3.20.3 binary exists, and `grpcio-tools` below 1.49 has no arm64 or Python 3.12 wheel | **A new tool built locally, not individually approved.** The owner asked on 2026-11-08 to check whether nanopb could use a compatible, pinned protoc on Apple Silicon without Rosetta or a system-wide installation, and conditionally approved `protobuf` 7.36.2 only if no practical compatible protoc existed. Building one from source was the **agent's own choice**. Whether a source build counts as "a practical compatible protoc" was never put to the owner, so that condition was not tested as written. The 7.36.2 override was **not used**. Provenance is a git commit pin, with no separate source-archive hash | Delete `external/protoc-build` and `external/protobuf-3.20.3` |
| D3 | Homebrew `aarch64-elf-binutils` and `aarch64-elf-gcc` installed with `--ignore-dependencies`, which Homebrew calls "an unsupported developer option" | A normal install would also upgrade `lz4` 1.10.0 to 1.11.0, which about 80 formulae including QEMU depend on, even with `lz4` pinned ([A1](A1.md), finding 4). Decision 7 forbids that drift | **The two formulae are owner-approved** (decisions 2 and 4). **The install option is not** | `brew uninstall aarch64-elf-gcc aarch64-elf-binutils` |
| D4 | `brew pin` on `qemu`, `cmake`, `ninja`, `dtc`, `lz4`, `aarch64-elf-gcc` and `aarch64-elf-binutils` | Decision 7: freeze, record, stop on drift. The decision text names QEMU, the cross GCC and its binutils, CMake, Ninja, `dtc` and "any already-installed library that the install would upgrade", with `lz4` as the example | **Owner-approved** as decision 7. The reviewer noted the pins match the decision text | `brew unpin <formula>` |
| D5 | In `build.sh`: `CC_aarch64_unknown_none`, `AR_aarch64_unknown_none=aarch64-elf-ar` and `RANLIB_aarch64_unknown_none=aarch64-elf-ranlib`; and `RUSTUP_TOOLCHAIN` with `RUSTUP_AUTO_INSTALL=0` | Without the `ar`/`ranlib` variables the `cc` crate uses macOS tools on AArch64 ELF objects and the loader loses its assembly ([A1](A1.md), finding 1; [evidence 22](A1/22-loader-defect-repro.txt)). The `RUSTUP_*` guards are in the Amendments | Inside the approved tool set. The `RUSTUP_*` guards are **owner-approved** (plan Amendments). The `ar`/`ranlib` variables are a build-recipe change from the upstream demo | Remove the lines. The loader then builds empty |
| D6 | In `build.sh`, `RUSTFLAGS`, `RUST_TARGET_PATH` and the build-std flags are passed on the command line, replacing the demo's `.cargo/config.toml` | `.cargo/config.toml` is a gated file and was not approved | Follows the owner's decision 5 (no `.cargo/config.toml`). The command line is the agent's equivalent of the demo's file | None needed |
| D7 | Python 3.12.16 for the venv instead of the host default 3.15, with `setuptools` 84.2.1, `wheel` 0.48.0 and `packaging` 26.3, hash-pinned | Python 3.15 has no `pyyaml` wheel, and `pyfdt` 0.3 is source-only for every version | **Owner-approved:** the interpreter, `setuptools` and `wheel`. **Not named:** `packaging`, which is `wheel`'s own dependency and was disclosed in A1 | Delete `.venv` |
| D8 | [`fetch-sel4test.sh`](../fetch-sel4test.sh) uses `git init --separate-git-dir` so each project's `.git` is a file, skips `opensbi`, and recreates the manifest's three linkfiles as symlinks | musllibc's build runs `rm src/.git`, which expects a `repo`-style `.git` file. `opensbi` is RISC-V only | Plain git as decision 4 describes. The `.git` layout and the `opensbi` skip are the agent's choices | Delete `external/sel4test-workspace` |
| D9 | [`boot-image.py`](../boot-image.py), [`probe-idregs.sh`](../probe-idregs.sh) and [`probes/idregs.c`](../probes/idregs.c): a QEMU boot harness and a bare-metal ID-register probe | A3 needed a repeatable boot-and-watch harness, and a direct measurement of what the HVF guest reports | **Spike code, not individually approved.** The probe is freestanding and reads read-only ID registers | Delete the files. The A3 evidence logs remain |
| D10 | The spike-local [`deny.toml`](../deny.toml) keeps `wildcards = "deny"`, evaluates no licences, and allows exactly the six approved git origins | Decision 3. The loader is `BSD-2-Clause AND GPL-2.0-only`, which the root policy would deny | **Owner-approved in principle** (decision 3 and 5). The licence omission is the agent's choice | Edit the file |
| D11 | The root task [`crates/root-task/src/main.rs`](../crates/root-task/src/main.rs) keeps the demo's three `unwrap()` calls and one `assert_eq!`: line 22 (`.unwrap()` ending the search for a non-device untyped), lines 30 and 31 (`empty_slots.next().unwrap()`, twice) and line 62 (`assert_eq!(observed_badge, badge)`) | It is the approved demo's code, adapted with its BSD-2-Clause attribution kept. AGENTS.md says no `unwrap`, `expect` or `panic!` outside tests, and also that `spikes/` is disposable and isolated. Editing them would change the root-task hash and need a new A1 run, which is not authorized | **Owner-approved one-time exception, 2026-11-08**, for exactly these four sites. It is acceptable because this is disposable, isolated spike code, a test program that prints a result and stops, and nothing outside `spikes/` depends on it. **It does not apply to production kernel or userspace code, or to any future experiment.** Recorded in the plan's Amendments | Replace the four sites and re-run A1 (needs authorization) |
| D12 | The sel4test control boots use `-cpu cortex-a57`, and the sel4test "clean" builds reuse a cached musllibc from `external/sel4test-workspace/.sel4_cache` | The A1 kernel is built for a Cortex-A57 and the sel4test kernels for a Cortex-A53 (`KernelArmCPU`), which was not varied | Agent's choice. Neither is expected to change the HVF result, which depends on the guest ID registers | Delete `.sel4_cache` and rebuild |
| D13 | The spike `Cargo.lock` was the rust-root-task-demo's lock at `c13bdae` ("Update everything", 2026-11-04) with the package name changed. It resolved **six crates.io versions that were not the ones in the lock the owner approved at rust-sel4 `v6.0.0`** (`c819c27`, "Release 6.0.0", 2026-10-29). Detail below | The owner approved `bindgen` 0.72.1 "as locked at `v6.0.0`" and said versions that appear only in the demo's lock "are not covered, and any such difference stops the work and asks". There is no record that the difference was noticed, that the work stopped, or that the owner was asked | **Resolved by owner decision, 2026-11-08 (option 2): the approved versions were restored** with four offline `cargo update --precise` commands, and A1 was rerun as a separate result ([A1-rerun](A1-rerun.md)). The original lock (SHA-256 `c92d1dca…`, Git `b563904`) and the original A1 evidence and hashes are preserved unchanged | Not applicable. To return to the original configuration, check out `b563904:spikes/sel4-feasibility/Cargo.lock` |
| D14 | Smaller items found by the independent review: (a) `HOMEBREW_NO_INSTALLED_DEPENDENTS_CHECK` was set during the Homebrew install runs ([01](A1/01-brew-dryrun.txt) to [03](A1/03-brew-install.txt) show its warning); the logs do not show whether other Homebrew variables were set. (b) [`sanitize-evidence.py`](../sanitize-evidence.py) and [`verify-evidence.py`](../verify-evidence.py) are spike code. (c) A3 log [06](A3/06-fetch-sel4test.txt) was produced by an earlier revision of `fetch-sel4test.sh` (`0bbda42`) that did not print "OK kernel", and the logs do not record which script revision made them. (d) A3 [41](A3/41-config-1cpu.txt) and [42](A3/42-config-4cpu.txt) are excerpts extracted from the build directories by a small script that is not in the repository | Disclosure. The extra evidence files were added to support claims that the published logs could not verify | **Not individually approved.** (a) only suppresses a check on installed dependents. (b) and (d) read local files and write text | Delete the files. Re-run the extraction from the gitignored build directories |
| D15 | [`compare-a1-runs.py`](../compare-a1-runs.py): a comparison of the original A1 outputs with the rerun's. It reads the preserved outputs in place, runs the approved `add-payload` binary of the original run to rebuild images for the byte accounting, and writes only to a temporary or `--work` directory | The owner asked for the differences to be accounted for. A hash comparison alone would not show whether the change is real | **Spike code, not individually approved.** It uses only tools already installed (`aarch64-elf-objcopy`, `-objdump`, `-readelf`, `dtc`) and changes none of the preserved files | Delete the file. The recorded output `A1-rerun/07` remains |
| D16 | **A local push safeguard** (the owner's request, 2026-11-08): this clone's local Git config sets `core.hooksPath` to the untracked `.git/fyrkat-hooks/`. Its `pre-push` refuses any push that carries the five unsanitized commits (`e778e29`, `7e763f0`, `f835b21`, `c99300d`, `81a2ca7`) or a ref named `local-only/*`, then runs the global pre-push hook unchanged. Every other hook name delegates to the global hook at run time | The global hooks directory is set in the user's global Git config, so a hook in `.git/hooks` would not run, and `pushremote = no_push_remote` on the local-only branch only stops a bare `git push` from it. **Global Git configuration was not modified** | Owner-requested. Tested with crafted inputs and `git push --dry-run` (the unsanitized branch, an original SHA and a commit built on one are refused; the PR branch passes and still runs the global hook). It checks **commit ancestry and ref names only**. `git push --no-verify` skips it, and so do rewritten copies of the commits (a rebase, a cherry-pick, a commit made from one of their trees), pushes of raw tree or blob objects, and any other clone, which does not have the hook | `git config --local --unset core.hooksPath && rm -rf .git/fyrkat-hooks` |

### D13 detail: the six lock-file differences [Measured unless marked]

*This section is the investigation made before the owner's decision, kept as the record of what was known then. Where it says a new A1 run was "not authorized", that has since been authorized and done, see the Resolution below.*

Dependency paths are from `cargo tree --frozen --offline --target all -e normal,build -i CRATE` on the spike workspace. "Approved" is the
version in `external/rust-sel4/Cargo.lock` at `c819c27`. Release dates are from the crates.io API.

| Crate | Approved | Resolved | Released (resolved / approved) | Path | Reaches the target binary? |
|---|---|---|---|---|---|
| `cc` | 1.10.0 | **1.11.0** | 2026-11-02 / 2026-10-23 | build-dependency of `psm` 0.1.32 and of `stacker`, under `pest_stack_guard` and `pest` | Not linked into the target. Runs on the build host, with the builder's privileges, inside `sel4-sys`'s build script, which uses `pest` to parse seL4's `.bf` files and generate code that is compiled into the target |
| `log` | 0.4.34 | **0.4.35** | 2026-10-30 / 2026-08-22 | dependency of `sel4-sys` (normal edge, so on the root task's AArch64 target graph) and of `bindgen` (build) | **Yes**: the only one of the six on the target's normal graph. Whether it changes the root-task bytes was not tested |
| `psm` | 0.1.24 | **0.1.32** | 2026-08-02 / 2024-11-13 | `pest_stack_guard` 1.0.1 and `stacker` -> `pest` -> `pest_derive`, a build-dependency of `sel4-sys` | Not linked into the target. Runs on the build host, with the builder's privileges, inside `sel4-sys`'s build script, which uses `pest` to parse seL4's `.bf` files and generate code that is compiled into the target |
| `pest_stack_guard` | 1.0.0 | **1.0.1** | 2026-11-03 / 2026-10-26 | `pest` 2.9.5 -> `pest_derive`, `pest_generator`, `pest_meta`, build-dependencies of `sel4-sys` | Same as above |
| `ar_archive_writer` | absent | **0.5.3** (new) | 2026-07-31 / n/a | build-dependency of `psm` 0.1.32 (its manifest requires `^0.5.0`) | Same as above |
| `object` | 0.40.0 | **0.39.1** (older) | 2026-04-21 / 2026-08-01 | dependency of `ar_archive_writer` 0.5.3, whose manifest requires `^0.39` | Same as above |

**Why they resolved this way.** The spike lock is the demo's lock, produced by "update everything" on 2026-11-04. rust-sel4's own lock at
`v6.0.0` is from 2026-10-29. Three of the resolved versions were published after the release lock (`cc` 1.11.0, `log` 0.4.35 and
`pest_stack_guard` 1.0.1). The `psm` change is different [Measured: the crates' own manifests]: `pest_stack_guard` 1.0.0 requires `psm` as
exactly `=0.1.24`, so the release lock could not move it. `pest_stack_guard` 1.0.1 (2026-11-03) relaxed that to `0.1.24`, which let `psm` resolve to
0.1.32. `psm` 0.1.32 adds `ar_archive_writer` as a build-dependency, and `ar_archive_writer` 0.5.3 requires the `object` 0.39 series, which is why
`object` is *older* than the approved 0.40.0. The other differences in a full comparison (`bitflags`, `itertools`, `windows-sys`) are only extra
older copies that the larger rust-sel4 workspace carries and the spike does not. The loader and `add-payload` were built from rust-sel4's own
lock, which is the approved one. **Only the root task, built in the spike workspace, used the spike lock.**

**Advisories.** None of the six crates has an entry in the local RustSec database (checked out 2026-11-06, 999 crate directories, none for these
six). `cargo deny` 0.20.2 on the spike workspace passes (advisories, bans and sources ok) with the original lock and with the restored one below
[Measured: scratch copies, `--frozen --offline`]. That says only that no known advisory applies as of that database.

**Is restoring the approved versions feasible?** Yes, offline and with no new download: the old versions are in the local Cargo cache. In a scratch
copy of the workspace (not the repository), these four commands produced a lock with all four approved versions and without `ar_archive_writer` and
`object`, 51 changed lines against the spike lock, and `cargo tree --locked` and `cargo deny` still passed:
`cargo update --offline -p cc --precise 1.10.0`, `-p log --precise 0.4.34`, `-p psm --precise 0.1.24` and `-p pest_stack_guard --precise 1.0.0`.
Costs and unknowns: it edits a gated file (`Cargo.lock`), so it needs the owner's approval; the `log` change may alter the root-task binary
[Inferred, not tested], so the A1 root-task hash (`a7c6be9a…`) and the identical-build claim would have to be re-established by a new A1 run,
which is not authorized; and it moves the lock away from the demo's lock, so the demo's own provenance claim changes.

**Resolution (2026-11-08).** The owner chose option 2 and authorized the four operations and one A1 rerun. Original and corrected
dependency configurations:

| Crate | Original (A1 run) | Corrected (rerun) | Approved at `v6.0.0` |
|---|---|---|---|
| `cc` | 1.11.0 | 1.10.0 | 1.10.0 |
| `log` | 0.4.35 | 0.4.34 | 0.4.34 |
| `psm` | 0.1.32 | 0.1.24 | 0.1.24 |
| `pest_stack_guard` | 1.0.1 | 1.0.0 | 1.0.0 |
| `ar_archive_writer` | 0.5.3 | removed | absent |
| `object` | 0.39.1 | removed from this workspace's graph | 0.40.0 |

After the change every registry package of the corrected lock is, with the same version and checksum, in the approved lock (0 differences),
and only these six entries differ from the original spike lock [Measured]. The rerun changed the root-task binary (the kernel and loader are
identical) because a hashed build-script directory name embedded in the binary depends on the dependency set [Inferred: Cargo's behaviour, not tested in isolation]; see
[A1-rerun](A1-rerun.md) for the byte-level account and its limits. The options list that was here before the decision (approve as they were, restore all six, restore only `log`) was removed from this file; it is in Git at `d1b0f46`. The Amendments record only the chosen option 2.

## Privacy note

The raw logs contained the local home path and user name (about 720 times in 26 files) and the full Homebrew
inventory. They were first pushed unredacted in pull request 7. The owner chose a narrow replacement: that
branch was deleted and the pull request closed, and the sanitized branch of pull request 8 was built from
`main`. The public copies are sanitized and the unredacted originals are kept only locally. **The original
commits are not erased:** `c99300d` still resolved by SHA on the public repository after the replacement, and
`refs/pull/7/head` still pointed to it. The owner decided not to contact GitHub Support at this time. What was
found, what was removed, and what remains are in [EVIDENCE-PRIVACY](EVIDENCE-PRIVACY.md).

## What was not done

No kernel change. No Tier 2 or Tier 3 install. No change to a criterion. The `cargo deny` advisory was
investigated and not suppressed ([A1](A1.md), finding 3, and
[the dependency path](A1/19-unsafe-libyaml-path.txt)).
