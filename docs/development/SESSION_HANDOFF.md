# Session handoff

A snapshot for the next session, not a source of truth. [ADRs](../adr/README.md) and Git win over it.
It records approvals and grants none. Owner decisions are in the last entries of the
[spike plan's Amendments](../research/sel4-spike-plan.md#amendments).

## Snapshot

- **Date:** 2026-11-08. `origin/main` is `09f5dd5` (pull request 10, the documentation update, merged). The E1 work is on the
  local branch `spike/e1-route-ii`, branched from `09f5dd5`, **until it is committed and pushed, the only copy of it is the
  working tree** (a `clean`, `checkout` or branch change loses the untracked files; check `git status` and `gh pr list` for its state). Local `main` is stale: use `origin/main`.
- **Open Dependabot PR #9** (`protobuf` 3.20.3 to 5.29.6 in the spike's `requirements.txt`) is **not to be merged** without the
  owner. [Measured: `gh`]

## Milestone status

- **M0:** complete (owner, 2026-11-07). **S1** (exit: the owner decides ADR 0004; M1 cannot be finalized before it): in
  progress. ADRs: 0001 Part A Provisional, Part B Withdrawn; 0002 and 0003 Provisional; 0004 Proposed. **None is Accepted.**
- A1 Pass (U); A1 rerun Pass (U), owner-accepted limited to build reproducibility. A3 Fail (U) for unmodified seL4 17.0.0 under HVF
  on one M2 Pro (decision rule 2 applies to that HVF-specific hypothesis only). A2a, A4, A5: not started.
- **E1 (Route II) ran: the agent's reading is Pass, label U, functional only.** A hypervisor-enabled seL4 17.0.0, the pinned Rust loader
  and the unchanged Rust root task reached `TEST_PASS` in 3 of 3 boots under QEMU 11.1.3 TCG. Record:
  [E1](../../spikes/sel4-feasibility/results/E1.md). **Independently reviewed** (fresh-context `reviewer`): acceptable with corrections, Pass justified, corrections applied. **Conditionally accepted by the owner, subject to the final review of the corrections** (that review: evidence confirmed, no material finding).

## Completed since the last handoff

Documentation PR 10 merged (reviewer MERGE-READY on the exact blobs, all three CI checks passed). E1 built and ran. The PR 9
investigation was done and reported. The result, new spike code (D17 `build-e1.sh`, D18 the verifier's E1 checks) and an
Amendments entry are in the working tree.

## Authorizations in force

Source: the owner's messages in this conversation and the plan's last Amendments entries.
- **E1:** authorized and used. Used scope: Route II, the specification and its verbatim baseline. **Nothing further is authorized after
  E1**: the owner's instruction was to record the results, request independent review and not proceed to another experiment.
- **Deviations approved for the isolated S1 research scope only (not a precedent):** D2, D3, D7, D9 (including the E1 reuse),
  D10, D14(b), D17 and D18 (owner, 2026-11-08; the verifier self-tests are to be preserved).
- **E1 pull request:** commit and push on `spike/e1-route-ii`, one focused review of the final corrections, a PR, and **merge only after an
  explicit MERGE-READY verdict and all required CI checks pass**. Then report the final commit and stop.
- **PR 9:** do not merge it and do not dismiss its alerts; keep the `protobuf` pin while a compatible remediation is evaluated; no more
  `protobuf` experiments.
- **Not authorized:** A2a, A4, A5, the comparator, Class 3 kernel modifications; any
  kernel, loader or root-task source change; any new tool or global installation; unrelated dependency changes; merging or touching
  PR 9; a GitHub Support request; reopening completed research; another experiment.

## Pending items (all the owner's unless stated)

1. **E1 is conditionally accepted** as Pass (U), functional only, subject to the final review of the corrections (the first review: acceptable with
   corrections, applied). Do not claim byte-identical serial logs. The open point was: accept the Pass as recorded,
   including the qualification on "identical output" (2 bytes of trailing line terminator differ, which the agent reads as timing).
2. **The E1 work** is authorized for commit and push (see above). The paths, all under `spikes/sel4-feasibility/` unless noted: new `build-e1.sh`,
   `results/E1.md` and `results/E1/`; changed `verify-evidence.py`, `results/deviations.md` and `results/evidence-manifest.txt`; and
   `../../docs/research/sel4-spike-plan.md`, `docs/roadmap.md` and this file. Gated paths touched: none (`docs/adr/`, `xtask/`, `.github/` are untouched).
3. **D17 and D18:** approved for S1 only.
4. **PR 9** (investigated; the owner has decided to keep the pin and not merge or dismiss). Findings [Measured unless marked]:
   - No `protobuf<4` fix exists: PyPI has no 3.x release after 3.20.3.
   - `sel4-deps` 0.9.0 declares `protobuf<4,>=3.19`. A resolving install of 5.29.6 with it is refused, but the project's documented
     install is `--require-hashes --no-deps`, and a dry run of that with PR 9's stanza reports "Would install protobuf-5.29.6".
     `pip check` would then flag the conflict [Inferred: not run after a real install].
   - `protobuf` is used only by nanopb's generator in the sel4test build (A3). GHSA-8qvm-5x2c-j2w7 (pure-Python parsing) is
     exercised there, on one pinned, locally generated input; GHSA-7gcm-g887-7qv7 (`json_format`) is not used. The A1 build and E1 do
     not use it. Neither is exploitable through S1's trusted inputs [Inferred].
   - nanopb's output for `rpc.proto` is byte-identical under 3.20.3 and 5.29.6 (Python 3.12 and 3.15), in scratch copies. One input only;
     5.29.6 inside the real venv was not run. The scratch work downloaded and ran the 5.29.6 wheel (hash in PR 9's list) in the
     scratchpad only.
5. Long-term toolchain policy (`nightly-2026-08-21` is approved for S1 only); the A5 question (class D or Investigate); whether ADR 0002
   or ADR 0004 text should change in light of E1; whether to delete the stale local branches.

## Blockers and conflicts

- The stop condition blocks everything except what the owner has named. **PR 9's fix conflicts with the `sel4-deps` `<4` pin** (metadata
  only, see above).
- **Privacy exposure remains:** `refs/pull/7/head` still resolves to `c99300d`; the original commits are fetchable by SHA from the
  public repo. Not erasure. `main` never held them. [Measured]
- Open items: the `RUSTSEC-2024-0449` note (host-side only, policy unchanged); a base-controlled `pull_request_target` check
  (`m0-acceptance.md`); CI uses QEMU 8.2.2 against the spike's pinned 11.1.3.

## Verified results

| Command | State | Result |
|---|---|---|
| `cargo xtask check` | `09f5dd5` + the uncommitted E1 work | "check: all 12 steps passed" |
| `spikes/sel4-feasibility/verify-evidence.py` | same | 55 of 55 checks passed (15 for E1); `--self-test`: 7 of 7 corruptions caught |
| E1 boots | image `4487ab9b…`, three fresh QEMU starts | 3 of 3 reached `TEST_PASS`, in order, no failure string |

**Not verified:** `cargo xtask boot`; E1 with half the RAM compared with A1 in any memory-sensitive test (E1-H has one 512 MiB region); E1 on another QEMU version, host or accelerator; a second build of the E1 image; that the kernel warning
`Could not infer GIC interrupt target ID` is benign; a real install of PR 9's pin and `pip check`; nanopb inputs other than `rpc.proto`.

## Next actions

1. **E1 PR:** commit (signed, DCO), push, open the PR; merge only on an explicit MERGE-READY verdict for the final head and green required CI; then report the final commit and stop.
2. Commit and push the E1 work (signed, DCO), run the final focused review, open the PR, merge on MERGE-READY and green CI, report the final commit, stop.
3. The owner's next priority is two isolated Rust tasks over seL4 IPC with a negative capability test: a proposal only, not authorized to start.

## Context not recorded elsewhere

- The E1 build output is in the gitignored `spikes/sel4-feasibility/external/e1-build/`; raw logs are in the gitignored
  `results-raw/E1/`. A root-task ELF embeds the build path: **publish hashes, never the binary.**
- **Unsanitized history** is on `local-only/s1-workspace-unsanitized` (at `81a2ca7`, `pushremote=no_push_remote`), retained on the
  owner's instruction, with raw logs in `results-raw/` and a backup `fyrkat-s1-raw-evidence-2026-11-08.tar.gz` (SHA-256 `768af917…`)
  beside the repository. **Never push it.**
- **Local safeguard (D16):** local `core.hooksPath` is `.git/fyrkat-hooks/`; its `pre-push` refuses the five unsanitized commits and
  `local-only/*`, then runs the global hook. Ancestry and ref names only; `--no-verify`, rewritten copies and other clones bypass it.
  Undo: `git config --local --unset core.hooksPath && rm -rf .git/fyrkat-hooks`.
- The original A1 run and lock are in the gitignored `external/a1-original-build/` (rerun build 1 in `a1-rerun-build1/`).
- The disposition-matrix draft and the E1 proposal were never committed. Both survive only in an earlier session's scratchpad
  (`s1-proposals.md`), which may be deleted. The plan's Amendments entry on E1 Route II quotes the chosen proposal verbatim.
- Commits here are signed with SSH, and `git log --show-signature` fails locally because `gpg.ssh.allowedSignersFile` is not set; GitHub
  verifies them. Local branches `spike/s1-prerequisites`, `docs/agents-research-section`, `spike/s1-workspace-sanitized` and `docs/s1-direction-record`
  belong to squash-merged PRs. The scratch commands behind the PR 9 findings are not in the repository. A project hook mistakes shell
  commands mentioning the ADR directory for writes: use the Edit or Read tool for ADRs.
  For privacy scans, use `git ls-files` rather than `grep -r`. The `reviewer` and `researcher` agents have Bash: check `git status`
  after they run. Start with `/fyrkat-resume`.
