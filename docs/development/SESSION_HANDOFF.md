# Session handoff

A snapshot for the next session, not a source of truth. [ADRs](../adr/README.md) and Git win over it.
It records approvals and grants none. Owner decisions are in the last entries of the
[spike plan's Amendments](../research/sel4-spike-plan.md#amendments).

## Snapshot

- **Date:** 2026-11-08. This file ships in the documentation pull request, so it names no PR number or head
  SHA of its own: read them from Git and `gh`. Branch `docs/s1-direction-record`, branched from `origin/main` at `07c35e2`
  (PR 8, merged). Local `main` is stale (`4fb92a1`): use `origin/main`.
- **Open Dependabot PR #9** (`protobuf` 3.20.3 to 5.29.6 in the spike's `requirements.txt`) is **not to be merged**. [Measured: `gh`]

## Milestone status

- **M0:** complete (owner, 2026-11-07). **S1** (exit: the owner decides ADR 0004; M1 cannot be finalized before it):
  in progress, stopped at the A3 gate except for E1 below. ADRs: 0001 Part A Provisional, Part B Withdrawn; 0002 and 0003
  Provisional; 0004 Proposed. **None is Accepted.** [Measured: Status lines]
- A1 Pass (U). A1 rerun, approved lock: Pass (U), **owner-accepted limited to build reproducibility**; kernel and loader
  hashes equal the original, **the root-task hash differs and must stay tied to its lock**; no runtime validation (the A1
  image has never booted). A3 Fail (U) for unmodified seL4 17.0.0 under HVF on one M2 Pro; decision rule 2 applies to
  that HVF-specific hypothesis only. A2a, A4, A5: not started. [Source: Amendments 2026-11-08]

## Authorizations in force

Source: the owner's messages in this conversation and the plan's last two Amendments entries.
- **Documentation PR:** commit (signed, DCO), push, open a PR, and **merge only after an explicit MERGE-READY verdict on the
  final head and all required CI checks pass.** If any condition fails: stop and report.
- **Deviations approved for the isolated S1 research scope only (not a precedent):** D2, D3, D7, D9 (including narrowly
  scoped reuse for E1), D10 (the `GPL-2.0-only` loader; no production licensing inference), D14(b). Everything else in
  `results/deviations.md` is as recorded there.
- **E1 Route II** (a hypervisor-enabled seL4 17.0.0 with the pinned Rust loader and the existing root task, under QEMU TCG)
  is authorized **only after the documentation PR is merged**, as specified in the plan's last Amendments entry. It is
  functional validation only. After it: record the results, request independent review, **do not start another experiment.**
- **PR 9 investigation:** read-only. No merge, no dependency change.
- **Not authorized:** A2a, A4, A5, the comparator, Class 3 kernel modifications; any kernel, loader or root-task source change;
  any new tool or global installation; unrelated dependency changes; merging or touching PR 9; a GitHub Support request;
  reopening completed research; another experiment after E1.

## Pending items

1. **The documentation PR** (merge conditions above). E1 starts only after it merges.
2. **PR 9 (investigated, the owner has not decided).** Two open high alerts on `spikes/sel4-feasibility/requirements.txt`:
   GHSA-8qvm-5x2c-j2w7 (fixed in 4.25.8) and GHSA-7gcm-g887-7qv7 (fixed in 5.29.6). PR 9 changes only the `protobuf` pin and its
   hashes. [Measured unless marked.]
   - **No `<4` fix exists:** PyPI has no `protobuf` 3.x release after 3.20.3, and both advisories cover all of 3.x.
   - **Pin conflict:** `sel4-deps` 0.9.0 declares `protobuf<4,>=3.19`. A dependency-resolving install of 5.29.6 with `sel4-deps`
     is refused (`ResolutionImpossible`, dry run). The project's documented install is `--require-hashes --no-deps`
     ([A1](../../spikes/sel4-feasibility/results/A1.md)); a dry run of that with PR 9's `protobuf` stanza reports "Would install
     protobuf-5.29.6", so pip would not enforce the pin, and `pip check` would then flag the conflict [Inferred: not run after a
     real install]. An earlier version of this file said pip would refuse; that was wrong for the documented command.
   - **Exercised?** `protobuf` is required only by `sel4-deps` and is used only by nanopb's generator in the sel4test build (A3);
     the A1 build and E1 do not use it (no `google.protobuf` import under `external/seL4`). **GHSA-8qvm-5x2c-j2w7 (CVE-2025-4565,
     pure-Python parsing of binary data): that code path is exercised** in the sel4test build, because the installed runtime is the
     pure-Python 3.20.3 wheel and the generator parses `protoc`'s output with it, but only for one pinned file,
     `libsel4rpc/rpc.proto`, produced by the locally built `protoc`. **GHSA-7gcm-g887-7qv7 (CVE-2026-0994, `json_format`):
     not exercised**; there is no `json_format` use in nanopb or seL4 sources. Both are recursion-depth denial of service on
     untrusted input, and S1's inputs are pinned and trusted [Inferred], so neither is exploitable through S1.
   - **Compatible?** In scratch copies (nothing in the repository or the venv changed), nanopb's output for `rpc.proto` is
     byte-identical under 3.20.3 (pure Python, the venv's Python 3.12) and under 5.29.6 (upb), with the same `protoc` 3.20.3. It was
     checked with Python 3.12.16 outside the venv (that interpreter also has another `protobuf` in its own site-packages; a separate
     check with the same interpreter and `PYTHONPATH` printed `google.protobuf.__version__` 5.29.6, output not kept) and with Python 3.15.0, both identical. One input only: the rest of sel4test's use
     is untested, and 5.29.6 inside the real venv was not run. The scratch work downloaded the 5.29.6 wheel (its hash is in PR 9's
     list) and ran it, only in the session scratchpad.
   - The recommendation is reported to the owner, who decides. Passing CI is not evidence here.
3. **Deviations this decision did not touch:** D1, D5, D6, D8, D12, D14 (a, c, d), D15, D16 stay as `results/deviations.md`
   records them (approvals and owner requests already recorded there for D5, D6 and D16 are unchanged). Settled: D4, D11
   (one-time), D13.
4. Long-term toolchain policy (`nightly-2026-08-21` is approved for S1 only); the A5 question (class D or Investigate);
   whether the ADR texts need more change; whether to delete the stale local branches.

## E1: what to do when it is time (plan Amendments, last entry)

- It needs a **new spike-local build script** derived from `build.sh`, differing only in `-DKernelArmHypervisorSupport=ON` and
  a separate build directory (`build.sh` removes `build/`, which holds the A1 rerun's outputs, so do not run it for E1). Record
  the script as a new deviation in `deviations.md` when it is written. The root task is rebuilt unchanged against the new
  kernel prefix, and the loader's hash may differ from A1's as well.
- Run through `boot-image.py --virt` with QEMU 11.1.3, TCG, Cortex-A57, 1 vCPU, marker `TEST_PASS`, 120 s (pass it: the harness
  default is 30 s), three boots. Pass needs the two seL4 banner strings, `Hello, World!`, `badge = 0x1337` and `TEST_PASS` in
  order, three times, with no kernel fault, halt, loader exception or root-task panic, **and identical output apart from timing
  and addresses**. The evidence needs sanitized logs (build and boots), a manifest entry and verifier checks.
- Stop and report on any source change, any tool or dependency not already installed or pinned, a configuration difference,
  three failed approaches to a first boot, anything unclear about authority, or a fault (one diagnostic boot of the same image
  through the unchanged harness, then stop). Nothing is pushed or merged.
- The verifier needs E1 checks added (authorized by E1, subject to D14(b)'s continuing independent verification). The plan's
  Amendments entry has the full specification and the verbatim baseline; read it before starting.

## Blockers and conflicts

- The A3 stop condition blocks everything except what the owner has named above. **PR 9's fix conflicts with the `sel4-deps`
  `<4` pin.**
- **Privacy exposure remains:** `refs/pull/7/head` still resolves to `c99300d`; the original commits are fetchable by SHA
  from the public repo. Not erasure. `main` never held them. [Measured]
- Open items: the `RUSTSEC-2024-0449` note (host-side only, policy unchanged); a base-controlled `pull_request_target`
  check (`m0-acceptance.md`); CI uses QEMU 8.2.2 against the spike's pinned 11.1.3.

## Verified results

| Command | State | Result |
|---|---|---|
| `cargo xtask check` | `07c35e2` + the uncommitted update, before the final review edits | "check: all 12 steps passed" |
| `spikes/sel4-feasibility/verify-evidence.py` | same | 40 of 40 checks passed |

**Not verified:** `cargo xtask boot`; whether either root task runs; whether the E1-H image builds or boots; a real install of
PR 9's pin and `pip check` afterwards; nanopb inputs other than `rpc.proto`. The scratch commands for the PR 9 findings are not
in the repository. Re-run both commands on the final head before the merge.

## Next actions

1. Independent review of this update, then fix, commit (signed, DCO), push, open the PR, and merge only on the conditions above.
2. Report the PR 9 investigation to the owner.
3. After the merge, and only then, run E1 within its Amendment, record the results, request independent review, and stop.

## Context not recorded elsewhere

- **Unsanitized history** is on `local-only/s1-workspace-unsanitized` (at `81a2ca7`, `pushremote=no_push_remote`), retained on
  the owner's instruction, with raw logs in the gitignored `spikes/sel4-feasibility/results-raw/` and a backup
  `fyrkat-s1-raw-evidence-2026-11-08.tar.gz` (SHA-256 `768af917…`) beside the repository. **Never push it.**
- **Local safeguard (D16):** local `core.hooksPath` is `.git/fyrkat-hooks/`; its `pre-push` refuses the five unsanitized
  commits and `local-only/*`, then runs the global hook. Ancestry and ref names only; `--no-verify`, rewritten copies and
  other clones bypass it. Undo: `git config --local --unset core.hooksPath && rm -rf .git/fyrkat-hooks`.
- The original A1 run and lock are kept in gitignored `spikes/sel4-feasibility/external/a1-original-build/` (rerun build 1 in
  `a1-rerun-build1/`). A root-task ELF embeds the build path: **publish hashes, never the binary.**
- The disposition-matrix draft and the E1 proposal were never committed. Both survive only in an earlier session's scratchpad
  (`s1-proposals.md`), which may be deleted. The plan's Amendments entry on E1 Route II quotes the chosen proposal verbatim as
  the baseline for "without weakening" and lists its differences.
- A project hook mistakes shell commands mentioning the ADR directory for writes: use the Edit or Read tool for ADRs. For
  privacy scans, use `git ls-files` rather than `grep -r`, so ignored directories are not read. Local branches `spike/s1-prerequisites`,
  `docs/agents-research-section`, `spike/s1-workspace-sanitized` belong to squash-merged PRs. The `reviewer` and
  `researcher` agents have Bash: check `git status` after they run. Start with `/fyrkat-resume`.
