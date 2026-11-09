# Session handoff

A snapshot for the next session, not a source of truth. [ADRs](../adr/README.md) and Git win over it.
It records approvals and grants none. Owner decisions are in the last entries of the
[spike plan's Amendments](../research/sel4-spike-plan.md#amendments).

## Snapshot

- **Date:** 2026-11-09. `origin/main` is `59dc7cb` (PR 12, E2, squash-merged; before it `c90f0e6` E1, `09f5dd5`, `07c35e2`). [Measured: `git`]
- **Checked-out branch:** `spike/e3-revocation`, created from `origin/main` (`59dc7cb`) for E3. HEAD is still `59dc7cb`: **all E3 work is uncommitted**, together with the earlier
  edit of this file. Local `main` is stale: use `origin/main`. Stale local branches still exist: `spike/e1-route-ii` (at `22aae47`) and `spike/e2-ipc-isolation` (at `d2250ca`) among them. Each equals its remote branch and is tree-identical to its squash-merge commit [Measured, 2026-11-09]; `local-only/s1-workspace-unsanitized` has unique commits and is retained by the owner's instruction.
- **Open PR:** only #9 (Dependabot, `protobuf` 3.20.3 to 5.29.6). **Not to be merged; its alerts are not to be dismissed.** [Measured: `gh pr list`]
- **ADRs:** 0001 Part A Provisional, Part B Withdrawn; 0002 and 0003 Provisional; 0004 Proposed. **None is Accepted.** [Measured: Status lines]

## Milestone status

- **M0:** complete (owner, 2026-11-07). **S1** (exit: the owner decides ADR 0004; M1 cannot be finalized before it): in progress.
- A1 Pass (U); A1 rerun Pass (U), accepted for build reproducibility only. A3 Fail (U): unmodified seL4 17.0.0 under HVF on one M2 Pro (rule 2 applies to
  that HVF hypothesis only). A2a, A4, A5: not started.
- **E1 (Route II): merged, Pass (U), functional only.** A Rust root task boots on a hypervisor-enabled seL4 under QEMU TCG, 3 of 3 boots.
- **E2: merged, Pass (U), functional only, finally accepted by the owner** (2026-11-09) as limited to its demonstrated functional and capability-isolation probes. It does **not** establish
  kernel-generated fault delivery (see the forged-fault-message limitation in [E2](../../spikes/sel4-feasibility/results/E2.md)). A precursor, **not** Stage B, P1 or P2 evidence (A2a has not run).
- **E3 (capability revocation): run, Pass (U), functional only, provisionally accepted by the owner** (2026-11-09) as limited to the tested revocation behaviour under QEMU TCG, **pending independent review**. D21 and D22 approved for E3 only. Record: [E3](../../spikes/sel4-feasibility/results/E3.md).
  A first review returned NOT MERGE-READY; its findings were fixed and the evidence rerun; a second review of the final state returned **MERGE-READY** (no material finding; low and editorial points noted in E3.md). The owner's final acceptance is pending.

## Completed since the last handoff

- **E3 built, run and tested locally; nothing committed, pushed or opened.** Branch `spike/e3-revocation` from `origin/main`. Code is in the existing `e2-task` and `e2-root-task` crates as new binaries
  (`e3_task`, `e3_root_task`), found by Cargo's automatic discovery, so **`Cargo.toml` and `Cargo.lock` are unchanged** (D21); `build-e3.sh`; `verify_e3.py` and `sanitize-run.py` (D22); evidence in `results/E3/`.
- **What E3 shows** [Measured, emulator]: a root task builds two identical tasks, each with a badged mint of its endpoint capability `P`, a copy of that mint, and a mint of an unrelated endpoint `Q`, and
  no capability to its own CNode. All are shown populated (a root-side `Copy` succeeds) and usable (the root task receives the call with the kernel-attached badge). The root task calls `Revoke` on `P`.
  Afterwards the mints of `P` and their copies are gone (root-side `Copy` refused with `FailedLookup`; the tasks' calls refused with label 2; the kernel logs a null-cap line each; nothing reached the root
  task through them), and `P`, the mints of `Q`, and a new mint of `P` made after the revoke all work. 3 of 3 boots.
- **Six mutants fail as they should** (the evidence kernel, loader and task binary, byte for byte; only the root task differs): no revoke, a revoke of `Q`, a revoke of too much (the control probe fails), a removal from task 1 only (task 2's probe fails) are stopped by the root task's probes;
  a no-op without two probes is stopped by a call reaching the root task; a root task that answers the call is stopped by the task's own refusal check.
- **Error behaviour** (required item 8): a call through a revoked slot returns label 2, **the same as a never-populated slot**; the copy error is `FailedLookup` for both. The record does not rely on the codes.
- **Limits, stated in E3.md:** one revoke topology (retype-original unbadged `P`, badged mints and a same-badge copy); the two tasks are symmetric (no server/client difference); slots 1 and 2 share a badge;
  the probe is a `Copy`; no revoke of a badged child, untyped, deeper chain, blocked thread or other object type; debug kernel, one vCPU, TCG only.
- **The first independent review** (`reviewer`, fresh context) returned NOT MERGE-READY. It confirmed the kernel semantics and reproduced the evidence, and found: **E3's binaries broke E2's build recipe** (`build-e2.sh` named no root-task binary; fixed, D23, and my
  earlier "E2 regression" check had named the binary itself, so it had not shown this); three detectors had never been shown to fail (mutants M4 to M6 added); the authorized baseline recommendation had been overwritten here (now quoted in the plan's Amendments); provenance and verifier gaps (source hashes
  now recorded and compared, the driver script `run-e3-evidence.sh` committed, the verifier tightened); and several overstatements, corrected. Because the fixes changed the root task, the whole evidence was rerun from the final source. Details: E3.md, "The independent review".
- **Things that went wrong on the way, disclosed in E3.md, none of them evidence:** a first build attempt failed on an unexported `SEL4_PREFIX` in `build-e3.sh`; a first complete run had two mutants and rebuilt the task binary for each; a second complete run (three mutants) is what the
  first review examined; the final run is the third. Local copies are in `external/e3-superseded-*` and `results-raw/E3-superseded-*` (gitignored). One verifier bug (kernel-line counts joined across boots) was found by the first verifier run and fixed before the evidence was recorded.
- The plan's Amendments have new entries (the owner's E2 final acceptance and E3 authorization; the agent's E3 measurement; the owner's provisional acceptance and the PR and merge conditions; the review's corrections, with the baseline recommendation quoted). `docs/roadmap.md` and `results/E2.md` were updated to match.

## Authorizations in force

Source: the owner's messages in this conversation; the plan's Amendments (entries of 2026-11-09, the last four).
- **Authorized, conditionally:** the independent review of E3 (done twice; the second, of the final state, returned MERGE-READY); then, **only after a MERGE-READY verdict on the final implementation** (given): the full verifier, its self-tests and `cargo xtask check`, signed DCO commits, a push of `spike/e3-revocation`, a PR that includes this file, and a merge
  **only when the required CI checks pass on the final reviewed head and no material finding remains**. Then report and stop. Deleting stale local branches is allowed after verifying they hold no unique commits or uncommitted work. Unrelated untracked directories (`.agents/`, `.codex/`) are not to be touched.
- Standing: D2, D3, D7, D9, D10, D14(b), D17, D18 (2026-11-08), **D19, D20 for E2's experimental scope only**, **D21, D22 for E3 only** (2026-11-09). D23 (the `build-e2.sh` repair) is **not** approved as such.
- **Not authorized:** changing ADR statuses, changing dependencies (any change to `Cargo.toml` or `Cargo.lock`), another experiment; A2a, A4, A5, the custom-kernel comparator, Class 3 kernel modifications; any kernel, loader or `crates/root-task` change; any new tool or global installation; merging or touching PR 9.
- Agents never push, force push or merge outside the conditions above; do not spawn agents on their own initiative; an agent does not review its own work.

## Pending approvals (the owner's)

1. E3: final acceptance as Pass (U) after the review (it is provisional until then). D23: whether the `build-e2.sh` repair is accepted (the alternative is separate crates, which needs a `Cargo.toml` and `Cargo.lock` change and a full E3 rerun).
2. Whether to commit this handoff (it goes into the E3 PR as the owner asked), and the stale local branches (see "Context").
3. Long-term toolchain policy (`nightly-2026-08-21` is approved for S1 only); the A5 question; whether ADR 0002 or 0004 text should change in light of E1, E2 and E3. Which experiment, if any, comes next.
4. PR 9: the owner decided to keep the `protobuf` pin and not merge or dismiss. Its conflict with the `sel4-deps` `protobuf<4` metadata is known (installs use
   `--no-deps`); no more `protobuf` experiments.

## Blockers and conflicts

- The S1 stop condition blocks everything except what the owner names. No conflict found between this file, Git and the ADRs.
- **Privacy exposure remains:** `refs/pull/7/head` still resolves to `c99300d`; the original commits are fetchable by SHA. Not erasure. `main` never held them.
- Open items: `RUSTSEC-2024-0449` (host-side, policy unchanged); a base-controlled `pull_request_target` check; CI uses QEMU 8.2.2 against the spike's 11.1.3.

## Uncommitted changes

`git status -sb`: `## spike/e3-revocation...origin/main`. Modified: `docs/development/SESSION_HANDOFF.md` (this file), `docs/research/sel4-spike-plan.md`, `docs/roadmap.md`,
`spikes/sel4-feasibility/{build-e2.sh, crates/e2-task/src/lib.rs, results/E2.md, results/deviations.md, results/evidence-manifest.txt, verify-evidence.py}`. New: `spikes/sel4-feasibility/{build-e3.sh, run-e3-evidence.sh, sanitize-run.py, verify_e3.py,
results/E3.md, results/E3/, crates/e2-task/src/bin/e3_task.rs, crates/e2-task/src/e3_abi.rs, crates/e2-root-task/src/bin/e3_root_task.rs, crates/e2-root-task/src/e3_spawn.rs}`.
Untracked and not from the spike work, not to be committed with it: `.agents/skills/*` and `.codex/*` (agent and hook configuration; `.codex/hooks.json` holds absolute home paths), untouched: **stage files by name, never `git add -A`**.
Gated files changed: none (`Cargo.toml`, `Cargo.lock`, `.github/`, `xtask/`, `docs/adr/`, `.claude/` are all unchanged); `docs/research/` and `docs/roadmap.md` are not gated.

## Verified results

| Command | State | Result |
|---|---|---|
| `verify-evidence.py` | the working tree with the final E3 evidence | 91 of 91 checks (20 for E3) |
| `verify-evidence.py --self-test` | same | 46 of 46 corruptions caught (19 earlier, 26 new on the E3 evidence, 1 on the lock) |
| E3 final image, 3 clean boots under QEMU 11.1.3 TCG | `external/e3-build/image.elf` `0460ce1d…` | `E3_PASS` in 3 of 3; logs identical apart from the harness footer |
| E3 mutants | `external/e3-mutant-*` | 6 of 6 stop at their intended detector, `E3_PASS` never printed |
| E2's recipe after D23 | scratch directory, bare environment (`E3_TASK_ELF` and the others unset) | `build-e2.sh`'s two cargo commands (as edited) succeed; without `--bin` on the root task, the same command fails (control). **This checks the recipe, not a rebuild to E2's recorded hashes** (reproduction of E2's hashes is a separate, pre-existing question; see E2.md) |
| `cargo xtask check` | re-run before the PR (see "Next actions") | |

An earlier version of this table said that E2 was rebuilt and booted with the E3 binaries present. That check had named `--bin e2-root-task` itself and so did not exercise `build-e2.sh`; the independent review found the break.
`cargo xtask boot` was not run locally. **Not verified:** E3 on another QEMU version, host or accelerator; anything about hardware; clippy on the spike workspace (not installed for the pinned nightly).

## Next actions

1. The E3 PR: signed DCO commits (files staged by name; `.agents/` and `.codex/` stay out), push `spike/e3-revocation`, a PR that includes this file and **states that `unsafe` code was added** (`e3_spawn.rs`: an `unsafe extern` declaration and a `static mut`, both copied). Merge only when the required CI checks pass on the final reviewed head and no material finding remains; then report the `main` commit and stop.
2. After the merge: the owner's final acceptance of E3, the D23 decision, and the outstanding S1 gates (see "Milestone status"). Do not start another experiment.
3. Known, left as is: the low and editorial points of the second review (E3.md, "Limitations"), none of which changes the evidence.

## Context not recorded elsewhere

- E3 build output is in the gitignored `spikes/sel4-feasibility/external/e3-build/` (and `e3-mutant-*`); raw logs in `results-raw/E3/`; the superseded runs in `external/e3-superseded-first-run/`, `external/e3-superseded-second-run/` and `results-raw/E3-superseded-*`. The evidence procedure is `run-e3-evidence.sh`, then `sanitize-run.py E3`, then `verify-evidence.py`.
  The E3 root-task ELF embeds a build-script directory name (and the symbol-hash suffixes of the ELFs depend on the build directory): **publish hashes, never the binary.**
- E2 build output is in the gitignored `spikes/sel4-feasibility/external/e2-build/`; raw logs in `results-raw/E2/`; the superseded first run in
  `external/e2-superseded-first-run/`. A root-task ELF embeds the build path: **publish hashes, never the binary.**
- **Unsanitized history** is on `local-only/s1-workspace-unsanitized` (at `81a2ca7`, `pushremote=no_push_remote`), retained on the owner's instruction, with a
  backup tarball (SHA-256 `768af917…`) beside the repository. **Never push it.** A local `pre-push` guard (`core.hooksPath` = `.git/fyrkat-hooks/`) refuses it;
  it covers ancestry and ref names only. Undo: `git config --local --unset core.hooksPath && rm -rf .git/fyrkat-hooks`.
- Commits are signed with SSH; `git log --show-signature` fails locally because `gpg.ssh.allowedSignersFile` is not set; GitHub verifies them. A project hook
  mistakes shell commands that mention the ADR directory for writes: use Edit or Read for ADRs. For privacy scans use `git ls-files`, not `grep -r`. The `reviewer`
  and `researcher` agents have Bash: check `git status` after they run. Start with `/fyrkat-resume`.
