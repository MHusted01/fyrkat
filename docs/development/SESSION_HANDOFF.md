# Session handoff

What the next session needs and no other file holds. A snapshot, not a source of truth:
[ADRs](../adr/README.md) and Git win over it, and it records approvals without granting any. Each
fact has one home ([workflow, Records](workflow.md#4-records)); this file links to it. Start with
`/fyrkat-resume`, which reads the branch, the commits and the pull requests from Git.

## Authorizations in force

- **General rules since 2026-11-15** (in `AGENTS.md` and the [workflow](workflow.md), for all
  work): local commits on branches other than `main`; the review, follow-up review and
  adjudication agents the workflow calls for; settlement of routine technical disagreements by
  the workflow.
- **Workflow implementation (owner, 2026-11-15 and 2026-11-16):** merging the pull requests that
  implement the approved workflow, on the owner's token, under the conditions recorded in the
  [Amendments, 2026-11-15](../research/sel4-spike-amendments.md#2026-11-15-the-owners-approval-of-the-engineering-workflow-and-its-standing-authorizations)
  and [2026-11-16](../research/sel4-spike-amendments.md#2026-11-16-the-owners-answer-on-merging-the-workflows-pull-requests).
  "And not for other work" is the agent's reading. It covers neither K3 nor the policy draft.
- **K3 (owner, 2026-11-11):** authorized, design left to the agent. Recorded in the
  [Amendments](../research/sel4-spike-amendments.md#2026-11-11-k3-the-owners-authorization-and-the-agents-results-the-agents-measurement-for-the-owner).
- **K3 decision delegated (owner, in conversation, 2026-11-17):** the interpretation of K3 section 1
  and the A5-arm outcome, after the deep review and its Major fixes passed follow-up; no ADR
  status and no criterion changed; push, PR and merge only if the review is clean. Decided: A5-arm
  **Investigate**, the agent's decision, in the
  [Amendments](../research/sel4-spike-amendments.md#2026-11-17-k3-decision-the-owner-delegates-the-k3-interpretation-and-the-a5-arm-outcome-the-agents-decision).
- **No separate agent account (owner, 2026-11-17):** agents use the owner's account, and Claude
  appears as neither author nor co-author (the agent's reading of the owner's wording). See the
  [Amendments](../research/sel4-spike-amendments.md#2026-11-17-the-owner-declines-a-separate-agent-account).
  It authorizes no push, pull request or merge.
- **Push, PR and merge of the K3 branch (owner, in conversation, 2026-11-17):** "1. yes" to whether the
  review, with its Majors fixed and followed up, counts as clean. Conditions as in the
  [Amendments](../research/sel4-spike-amendments.md#2026-11-17-k3-decision-later-the-owners-answers-on-the-push-and-the-successor-run).
- **Successor run (owner left it to the agent, 2026-11-17; the agent decided yes, as a new task after K3
  merges):** same entry. Not started.
- **Not authorized:** any other push, pull request or merge, including the policy draft; Stage B; A4;
  the comparator; any change to the seL4 kernel, ABI, dependencies or ADR statuses; new tools or
  installations; touching PR 9 (Dependabot `protobuf`: not to be merged, its alerts not to be
  dismissed); any change to CI beyond the two the 2026-11-15 entry names; bypassing CI or a GitHub
  protection. Isolated kernel
  prototypes are allowed in principle by the K3 message, the plan's Class 3 rule still applies,
  and none was built: ask first.

## Waiting for the owner

1. **K3's decision.** Object to it if you disagree: A5-arm Investigate, or reading (b) of K3 section 1
   (the control's REACHED is not a Fail), which if rejected makes the outcome Fail.
2. **Rulesets** (drafts only, see Context): apply `protect-main` and `block-local-only` after a
   test on a throwaway branch with the owner watching, then delete the classic rule.
3. **The merge-delegation draft** in the `fyrkat-policy` worktree: take, change or drop. Its clause
   that a disputed finding is the owner's to settle predates the approved workflow, and its
   `AGENTS.md` edits will conflict with `main`'s.
4. **After K3:** E-pin (a Class 3 change: a new ADR and an amendment); a new crate for an SMMUv3
   format library (a `Cargo.toml` gate); whether a hypervisor-mode row joins the Stage B matrix;
   toolchain policy (`nightly-2026-08-21` is S1-only); ADR 0002 and 0004 text; Tier 2 for A4's
   x86-64 half.

## Blockers and open findings

- **Open from K3's deep review:** no Blocker or Major. Nine Minors and a few Nits stay open because
  each edits a pinned file: listed in [K3](../../spikes/sel4-feasibility/results/K3.md) section 10d, and
  to be listed in the pull request. One more Nit: the DMA note's label does not cover one sentence.
- **Privacy exposure remains:** `refs/pull/7/head` still resolves to `c99300d`; commit `e163dff`,
  reachable through `refs/pull/18/head`, holds a random Claude Code session identifier used as
  test data (not a credential, not on `main`). Neither can be removed from here. See
  [EVIDENCE-PRIVACY](../../spikes/sel4-feasibility/results/EVIDENCE-PRIVACY.md).
- The macOS workflow has never passed and is started by hand only. Open: `RUSTSEC-2024-0449`
  (host-side); a base-controlled `pull_request_target` check; CI uses QEMU 8.2.2 against the
  spike's 11.1.3.
- The replay-audit script is on its own branch (`chore/replay-audit`), not on `main`: its review
  did not converge and it was split out of pull request 18.
- **A resumed reviewer ran at `high`**, not the `xhigh` its file sets (baseline note, section 6;
  cause open). Start deep follow-up reviews as fresh agents.

## Local state that Git does not show

- **Untracked, not the project's:** `.agents/` and `.codex/` (hooks, home paths). Never stage them.
  Stage by name, never `git add -A`. A `~/.codex` pre-commit hook runs on commits here and prints
  "Broken pipe" noise; the commits succeed.
- **Gitignored, keep:** `spikes/sel4-feasibility/external/` (328 MB, was 11 GB) and `results-raw/`.
  In `external/` kept: the sources (`seL4`, `rust-sel4`, `sel4test-workspace`), tools, small logs,
  the K3 images in `k3-build/`, and in `relk-build` only `K2`, `K2R` and the three dtbs. The build
  outputs of A1, A2a, E1 to E3, A5 steps 0 to 2, Route I and the K3 cargo targets were deleted: an
  earlier evidence driver needs a rebuild first, and `build-k3.sh` needs `relk-build/K2` and
  `K2R`. `verify-evidence.py` needs no images. Do not `git clean`, `checkout .`, `stash` or `reset`.
- **Worktrees:** `../fyrkat-policy` (`docs/merge-authority-policy`) holds uncommitted policy work.
  Five more hold squash-merged workflow branches and are clean: `../fyrkat-audit`, `-stage1`,
  `-stage2`, `-validation`, `-workflow`. Removing them needs `git worktree remove` and
  `git branch -D`. Other local branches: `docs/s1-session-record`, `spike/s1-prep-work`,
  `spike/stage-b-prep`, `spike/a5-smmu`.
- **Never push** `local-only/s1-workspace-unsanitized`. A `core.hooksPath` guard refuses it by
  ancestry and by name; it guards this machine only.

## Verified, and not verified

Verified on the K3 commits rebased onto `main` at `b617525`, 2026-11-17: `cargo xtask check` (12
steps), `verify-evidence.py` (174 of 174), its `--self-test` (191 of 191). K3 had a deep review and rounds of
follow-up until no Blocker or Major was open (K3 section 10d). `main` requires the
checks `check and boot (ubuntu x86-64)`, `boot (ubuntu arm64)`, `security-sensitive paths` and
`spike evidence`, with `enforce_admins` on (`gh api`).
**Not verified:** that K3 can be rebuilt after the cleanup (no rebuild was attempted); anything on
hardware; the CI QEMU against the spike's images; clippy on the spike workspace; that the draft
rulesets behave as assumed (none applied); the workflow hypotheses H1 to H3, H6 and H7 (no
results) and H5 (seeded-defect tests not run).

## Next actions

1. **Authorized (owner left it to the agent, 2026-11-17):** the successor run, in a fresh session on a
   new branch from `main`: see "What would change it" in the K3-decision Amendments entry. It must not
   edit any file that merged evidence pins. **Needs the owner:** Waiting items 2 to 4, and Stage B, A4
   and the comparator.
2. The owner's permission to push, open and merge the K3 branch (Amendments, 2026-11-17) was for that
   one pull request and is used up with it.
3. **Authorized (workflow grant):** finish the validation: replay `004bf9e` (re-export base
   `44d1d70` and head `004bf9e`), design the seeded-defect test for H5, measure H1 and H2 with
   one-task sessions at `--autocompact 200000`; record in the baseline note, section 6. Run one
   review at a time: the usage limit cut three runs.
4. Stage B and A4 each need authorization. A2b is future work for A2-final.

## Context not recorded elsewhere

- **Evidence pins.** Each set records the SHA-256 of its inputs. `run-k3-evidence.sh` hashes the K3
  sources, scripts and checker before the first build and after the last boot, and `verify_k3.py`
  requires them unchanged. Editing a listed file means re-running the driver (about 25 minutes,
  after rebuilding the kernel variants), then `sanitize-run.py K3`, refreshing K3 sections 8 and 9,
  and `verify-evidence.py`. Dry-test a changed checker against a log recorded with QEMU's trace on.
  Shared files (`a5_mmio.rs`, `pl011.rs`, `slots.rs`, `edu.rs`, `child_vspace.rs`,
  `object_allocator.rs`, `boot-a5.py`, `a2a-compare.py`, `build-relk.sh`) are read by K3 and were not edited; files
  pinned by merged evidence are not changed: write a new script.
- **Running K3 by hand** (under bash, not zsh): `./build-k3.sh K2|K2R [design|naive|MUTANT]`, then
  `boot-a5.py --smp 4 --machine-extra iommu=smmuv3,highmem=off --device edu,dma_mask=0xffffffffff
  --device edu,dma_mask=0xffffffffff --marker K3_DONE external/k3-build/ID-VARIANT/image`. Keep the
  machine quiet during an evidence run: the in-flight kill test relies on the `edu` 100 ms timer
  on the virtual clock.
- **Hazards found.** Invoking any operation on an endpoint or notification capability is an IPC or
  a signal, not an error: never type-probe a CSpace by invocation without skipping communication
  slots. A `Revoke` of an untyped holder's untyped destroys its own frames. QEMU's SMMU leaves a
  device buffer zero when a read is refused, and `pattern(0, 0)` is zero.
- **Draft rulesets** (no copy survives outside this description). `protect-main`: target the default
  branch, empty bypass list, rules deletion, non-fast-forward, linear history, pull request (squash
  only, review count 0, thread resolution), required status checks (strict; the required checks,
  bound to the GitHub Actions app, id 15368). `block-local-only`: `refs/heads/local-only/**`, empty
  bypass list, rules creation and update. Modelled on the two active rulesets of another public
  repository of the owner; the exact shape comes from `gh api repos/<owner>/<repo>/rulesets/<id>`.
- **Replay materials** (the keys are the original reports of reviews of `96f68c2`, `05c40b2`,
  `004bf9e`, recoverable from the review transcripts). Matching rules: score a finding strict if it
  names the same defect at the same place, lenient if the same problem less exactly; reject a
  configuration for missing a checkable Blocker, Critical or High; a miss both arms make is
  attributed to the replay conditions. The first replay's scoring is in the baseline note.
- `git log --show-signature` fails on this machine although the commits carry signatures and GitHub
  verifies them. `cargo xtask check` in a new worktree needs `.tools/` copied from the main
  checkout and its own `target/`.
