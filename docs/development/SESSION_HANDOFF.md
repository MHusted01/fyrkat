# Session handoff

A snapshot for the next session, not a source of truth. [ADRs](../adr/README.md) and Git win over it.
It records approvals and grants none. Owner decisions are in the last entries of the
[spike plan's Amendments](../research/sel4-spike-plan.md#amendments).

## Snapshot

- **Date:** 2026-11-09. `origin/main` is `c90f0e6` (pull request 11, E1 Route II, merged; before it `09f5dd5` and `07c35e2`). The E2 work is on the
  local branch `spike/e2-ipc-isolation`, branched from `c90f0e6`, **uncommitted and unpushed: until it is committed, the only copy of it is the
  working tree** (a `clean`, `checkout` or branch change loses the untracked files). Local `main` is stale: use `origin/main`.
- **Open Dependabot PR #9** (`protobuf` 3.20.3 to 5.29.6 in the spike's `requirements.txt`) is **not to be merged** and its alerts are not to be
  dismissed. [Measured: `gh`]

## Milestone status

- **M0:** complete (owner, 2026-11-07). **S1** (exit: the owner decides ADR 0004; M1 cannot be finalized before it): in
  progress. ADRs: 0001 Part A Provisional, Part B Withdrawn; 0002 and 0003 Provisional; 0004 Proposed. **None is Accepted.**
- A1 Pass (U); A1 rerun Pass (U), owner-accepted limited to build reproducibility. A3 Fail (U) for unmodified seL4 17.0.0 under HVF
  on one M2 Pro (decision rule 2 applies to that HVF-specific hypothesis only). A2a, A4, A5: not started.
- **E1 (Route II): merged, Pass (U), functional only,** owner-accepted conditionally, then reviewed and merged (PR 11). 3 of 3 boots reached `TEST_PASS`
  on a hypervisor-enabled kernel under QEMU 11.1.3 TCG, with half A1's RAM. Record: [E1](../../spikes/sel4-feasibility/results/E1.md).
- **E2: Pass (U), functional only; provisionally accepted by the owner (2026-11-09) subject to independent review; the `reviewer` returned MERGE-READY
  on the final state after four material findings were fixed.** Two isolated Rust tasks (own address space, CNode, TCB) over one seL4 endpoint; the
  client made two invalid invocations (an empty slot; label 0 on its own CNode capability) that returned errors, its badge forgery was refused, and its
  read of the server's memory produced a VM-fault-shaped message at the root task. That message is not proof of a real fault, because the client holds a
  send capability to that endpoint (see E2.md, "What the fault check shows"). 3 of 3 boots; two mutants fail as they should. Record: [E2](../../spikes/sel4-feasibility/results/E2.md). A precursor,
  **not** Stage B, P1 or P2 evidence; it does not test revocation or rights amplification (mint masks rights, it does not reject).

## Authorizations in force

Source: the owner's messages in this conversation and the plan's last Amendments entries.
- **E2:** authorized by "go ahead" and "Option 1, approve object" (2026-11-09): the proposal, the gated `Cargo.toml` and `Cargo.lock`, and the new
  dependency `object` 0.40.0, for S1 only. Later the same day the owner provisionally accepted E2 as Pass (U) subject to independent review,
  approved D19 and D20 **for E2's scope only**, and authorized: a focused `reviewer` run; fixes for material findings; then, only after an explicit
  MERGE-READY verdict, full checks, signed DCO commits, push of `spike/e2-ipc-isolation`, a PR, and a merge conditional on all required CI checks passing on the final head,
  the verifier passing and no material finding left. After the merge: report the `main` commit and stop.
- **Deviations approved for the isolated S1 research scope only (not a precedent):** D2, D3, D7, D9 (including the E1 reuse), D10, D14(b), D17 and D18
  (owner, 2026-11-08; the verifier self-tests are to be preserved). D19: see above.
- **PR 9:** do not merge it and do not dismiss its alerts; keep the `protobuf` pin; no more `protobuf` experiments.
- **Not authorized:** A2a, A4, A5, the comparator, Class 3 kernel modifications; any kernel, loader or `crates/root-task` source change; any new tool or
  global installation; any dependency beyond `object`; merging or touching PR 9; a GitHub Support request; reopening completed research; any further experiment.

## Pending items (all the owner's unless stated)

1. **E2:** committing, pushing and a PR are authorized only after the reviewer's MERGE-READY (given), with merge conditional on all required CI checks
   passing on the final head, the verifier passing and no material finding left. The owner's final acceptance of E2 is still the owner's. Check `git`
   and `gh` for whether the PR was opened or merged; this file was written before that.
2. **PR 9** (investigated; the owner decided to keep the pin and not merge or dismiss). Findings [Measured unless marked]:
   - No `protobuf<4` fix exists: PyPI has no 3.x release after 3.20.3.
   - `sel4-deps` 0.9.0 declares `protobuf<4,>=3.19`. The project's documented install is `--require-hashes --no-deps`, and a dry run of that with PR 9's
     stanza reports "Would install protobuf-5.29.6". `pip check` would then flag the conflict [Inferred: not run after a real install].
   - `protobuf` is used only by nanopb's generator in the sel4test build (A3). GHSA-8qvm-5x2c-j2w7 is exercised there on one pinned, locally generated
     input; GHSA-7gcm-g887-7qv7 is not used. Neither is exploitable through S1's trusted inputs [Inferred].
   - nanopb's output for `rpc.proto` is byte-identical under 3.20.3 and 5.29.6 (scratch copies, one input only).
3. Long-term toolchain policy (`nightly-2026-08-21` is approved for S1 only); the A5 question (class D or Investigate); whether ADR 0002 or ADR 0004 text
   should change in light of E1 and E2; whether to delete the stale local branches.

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
| `spikes/sel4-feasibility/verify-evidence.py` | `c90f0e6` + the uncommitted E2 work | 71 of 71 checks passed (16 for E2); `--self-test`: 19 of 19 corruptions caught (5 are on the lock file, added after review) |
| E2 boots | image `b4aec761…`, three fresh QEMU starts | 3 of 3 reached `E2_PASS`, full sequence in order, no failure string, one VM fault |
| E2 mutants | scratch images | both failed as expected (no `E2_PASS`, the matching `E2_FAIL`) |
| `cargo xtask check` | `c90f0e6` + the uncommitted E2 work | all 12 steps passed (after the review fixes) |

**Not verified:** `cargo xtask boot`; rebuilding E2 from the committed source to the recorded hashes (the root-task ELF would differ in symbol hash suffixes and one ELF-header field even in the same directory); E2 on another QEMU version, host or accelerator; a second build in a different directory
(the kernel hash depends on the build directory name, likely [Inferred]); revocation, rights amplification, a second fault, IRQ or untyped authority;
that the GIC warning is benign; a real install of PR 9's pin and `pip check`.

## Next actions

1. Finish the E2 PR as authorized, report the final `main` commit, and stop.
2. Owner's next milestone candidates after E2 (nothing authorized): a revocation test (use after revoke), which M3 requires; A2a, which is blocked.

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
