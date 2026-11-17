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
- **Workflow implementation (owner, 2026-11-15)**, for implementing the approved engineering
  workflow and completing its validation: edits to security-sensitive paths; the replays,
  seeded-defect tests and paired reviews; merging the pull requests that implement the workflow.
  "And not for other work" is the agent's reading. Conditions: security requirements are
  preserved; no GitHub protection is bypassed; a pull request is merged only after its required
  checks pass and its review is complete at the reviewed head commit, with `--match-head-commit`
  and never with auto-merge. The approved proposal also asks for a separate agent account and
  rulesets "before any delegated merge": pull request 18 was merged on the owner's token on the
  agent's reading that the explicit direction governs. See Waiting item 1. Recorded in the
  [Amendments, 2026-11-15](../research/sel4-spike-amendments.md#2026-11-15-the-owners-approval-of-the-engineering-workflow-and-its-standing-authorizations).
- **K3 (owner, 2026-11-11).** The owner authorized K3 and left its design to the agent. That
  authorization is recorded only in an uncommitted Amendments entry in the main checkout. See
  Blockers.
- **Not authorized:** any other push, pull request or merge; Stage B; A4; the comparator; any
  change to the seL4 kernel, ABI, dependencies or ADR statuses; new tools or installations;
  touching PR 9; any change to CI beyond the two the 2026-11-15 entry names; bypassing CI or a
  GitHub protection.

## Waiting for the owner

1. **An identity for agents.** A separate GitHub account with write access, and
   the owner's token out of the agent's environment. Agents use the owner's admin token today, so
   every server-side rule is a convention. See the
   [baseline, section 2](../research/workflow-baseline-2026-11.md#2-github-what-is-confirmed-and-what-is-inferred).
   On 2026-11-16 the owner answered the question of merging the remaining workflow pull
   requests on the owner's token with "whatever you deem correct and best". The agent decided
   to merge them on that token, disclosed in each pull request, under the conditions in the
   [Amendments, 2026-11-16](../research/sel4-spike-amendments.md#2026-11-16-the-owners-answer-on-merging-the-workflows-pull-requests).
   The account and the rulesets are still the owner's to set up.
2. **K3.** Accept or reject K3's interpretation of the plan's wording, and decide the A5-arm
   outcome. Whether K3 is committed, pushed and opened as a pull request.
3. **The merge-delegation draft:** take, change or drop it. Its clause that a disputed finding is
   the owner's to settle predates the approved workflow.
4. **After K3:** a kernel-assisted pin of an untyped in a copy of seL4 (a Class 3 change: a new
   ADR and an amendment); a new crate for an SMMUv3 format library; whether a hypervisor-mode row
   joins the Stage B matrix.
5. Toolchain policy (`nightly-2026-08-21` is S1-only); ADR 0002 and 0004 text; Tier 2 for A4's
   x86-64 half.

Items 2 to 4 are set out in the K3 record and in the handoff beside it, both uncommitted in the
main checkout.

## Blockers and open findings

- **K3 is not in Git.** The main checkout, on `spike/k3-isolation`, holds uncommitted K3 code,
  evidence and results, an Amendments entry dated 2026-11-11 written into the plan as it was
  before the split, and a newer handoff. The branch itself has no K3 commit. When K3 is committed,
  its entry goes into `sel4-spike-amendments.md` and its handoff is merged into this one.
- **A merge-delegation draft** is uncommitted in a second worktree, on
  `docs/merge-authority-policy`. It is not in force.
- **Privacy exposure remains:** `refs/pull/7/head` still resolves to `c99300d`. `main` never held it.
  See [EVIDENCE-PRIVACY](../../spikes/sel4-feasibility/results/EVIDENCE-PRIVACY.md).
- The macOS workflow has never passed. It is started by hand only.
- The `spike evidence` CI job blocks nothing until it is a required check.
- The script that audits a blind replay is not on `main`: its review did not converge and it was
  split out of pull request 18 to be redone on its own. Earlier versions of it are in that pull
  request's history.
- **An identifier in pull request 18's history.** Commit `e163dff`, reachable through
  `refs/pull/18/head`, holds a Claude Code session identifier that was used as test data. It is a
  random ID, not a credential and not personal data, and it is not on `main`. Like the pull
  request 7 ref, it cannot be removed from here.
- Open: `RUSTSEC-2024-0449` (host-side); a base-controlled `pull_request_target` check; CI uses
  QEMU 8.2.2 against the spike's 11.1.3.

## Local state that Git does not show

- **Untracked, not the project's:** `.agents/` and `.codex/` (they include hooks and absolute home
  paths). Never stage them. Stage by name, never `git add -A`.
- **Gitignored, local only, keep:** `spikes/sel4-feasibility/external/` and `results-raw/` (raw
  logs, including earlier runs kept on purpose). Do not `git clean`, `checkout .`, `stash` or
  `reset` in the main checkout.
- **Most build output is gone.** On 2026-11-11 and 12, at the owner's request, `external/` was cut
  from 11 GB to 328 MB: the builds of A1, A2a, E1 to E3 and A5 steps 0 to 2 were deleted. An
  evidence driver for any of them needs a rebuild first. The record of what was deleted is in the
  uncommitted handoff in the main checkout.
- **Never push** `local-only/s1-workspace-unsanitized`. A local pre-push hook, set through
  `core.hooksPath`, refuses it by ancestry and by name. It is a guard on this machine only.

## Verified, and not verified

CI shows the checks for each merged commit, and runs `verify-evidence.py` and its self-test.
**Not verified:** anything on hardware; the CI QEMU against the spike's images; clippy on the
spike workspace.

## Next actions

1. **Authorized:** make `spike evidence` a required check once it has passed on `main`; continue
   the workflow validation in the [baseline](../research/workflow-baseline-2026-11.md#5-hypotheses)
   and record each result there; redo the replay audit script as a change of its own.
2. **Needs the owner:** the list above. Until item 2 is decided, no new experiment.
3. If the owner accepts K3: record the A5-arm outcome in the Amendments (needs approval), then
   Stage B and A4, each of which needs authorization.
4. A2b (complete the dependency lists for K1, K1R, K2, K2R) is future work for A2-final.

## Context not recorded elsewhere

- **Evidence pins.** Each evidence set records the SHA-256 of its inputs, and shared files are
  inputs of several sets. Editing one means re-running the drivers that list it, then
  `sanitize-run.py` and `verify-evidence.py`. Never edit a listed file while its driver runs or
  while a reviewer is reading the tree. Files pinned by merged evidence are not changed: write a
  new script.
- **Running the experiments by hand.** The commands for the release kernels and for A5 are in
  this file's history at `460f385`. The images they name were deleted and must be rebuilt first.
  The K3 commands are in the uncommitted handoff in the main checkout.
- **QEMU's sources** for the SMMU and `edu` were read from the public repository at tag `v11.1.3`
  as documentation. Nothing of them is in this repository.
- `git log --show-signature` fails on this machine although the commits carry signatures and
  GitHub verifies them. Run the spike's drivers under bash: zsh does not split words.
- `cargo xtask check` in a new worktree needs `.tools/` copied from the main checkout, and its own
  `target/` directory.
