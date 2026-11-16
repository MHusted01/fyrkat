# Session handoff

What the next session needs and no other file holds. A snapshot, not a source of truth:
[ADRs](../adr/README.md) and Git win over it, and it records approvals without granting any. Each
fact has one home ([workflow, Records](workflow.md#4-records)); this file links to it. Start with
`/fyrkat-resume`, which reads the branch, the commits and the pull requests from Git.

## Authorizations in force

- **Workflow implementation (owner, 2026-11-15).** For implementing the approved engineering
  workflow and completing its validation, and for nothing else: edits to security-sensitive
  paths; review, follow-up and adjudication agents; local commits on branches other than `main`;
  the replays, seeded-defect tests and paired reviews; settlement of routine technical
  disagreements by the workflow. Condition: security requirements are preserved and no GitHub
  protection is bypassed. Merging is authorized for the pull requests that implement the workflow
  and for nothing else. Recorded in the
  [Amendments, 2026-11-15](../research/sel4-spike-amendments.md#2026-11-15-the-owners-approval-of-the-engineering-workflow-and-its-standing-authorizations).
- **K3 (owner, 2026-11-11).** The owner authorized K3 and left its design to the agent. That
  authorization is recorded only in an uncommitted Amendments entry in the main checkout. See
  Blockers.
- **Not authorized:** any other push, pull request or merge; Stage B; A4; the comparator; any
  change to the seL4 kernel, ABI, dependencies or ADR statuses; new tools or installations;
  touching PR 9; any change to CI beyond the two the 2026-11-15 entry names; bypassing CI or a
  GitHub protection.

## Waiting for the owner

1. **An identity for agents:** a separate GitHub account with write access, and the owner's token
   out of the agent's environment. Agents use the owner's admin token today, so every server-side
   rule is a convention. See the [baseline, section 2](../research/workflow-baseline-2026-11.md#2-github-what-is-confirmed-and-what-is-inferred).
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
- The script that audits a blind replay is not in the repository: its review did not converge and
  it was split out of pull request 18 to be redone on its own.
- Open: `RUSTSEC-2024-0449` (host-side); a base-controlled `pull_request_target` check; CI uses
  QEMU 8.2.2 against the spike's 11.1.3.

## Local state that Git does not show

- **Untracked, not the project's:** `.agents/` and `.codex/` (they include hooks and absolute home
  paths). Never stage them. Stage by name, never `git add -A`.
- **Gitignored, local only, keep:** `spikes/sel4-feasibility/external/` (all builds) and
  `results-raw/` (raw logs, including earlier runs kept on purpose). Do not `git clean`,
  `checkout .`, `stash` or `reset` in the main checkout.
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

- **Evidence pins.** Each evidence set records the SHA-256 of its inputs, and shared files (`a5_mmio.rs`, `pl011.rs`, `slots.rs`, `smmuv3.rs`, `edu.rs`, `boot-a5.py`, `build-relk.sh`, `build-a5-e1h.sh`, `object_allocator.rs`) are inputs of several sets. Editing one means re-running `run-a5-step0-evidence.sh`, `run-relk-evidence.sh`, `run-a5-step1-evidence.sh` and `run-a5-step2-evidence.sh` as applicable (under bash; about 12 minutes together), then `sanitize-run.py <A5-step0|ReleaseKernel|A5-step1|A5-step2>` and `verify-evidence.py`. Never edit a listed file while its driver runs or while a reviewer is reading the tree. `build-routei.sh`, `boot-image.py`, `a2a-compare.py` and `build-e2.sh` are pinned by merged evidence: do not change them.
- **Running the experiments by hand.** Release kernels: `./build-relk.sh K1R` (or `K2R path/to/k2-smc.dtb`; `RELK_BIN=a5_step1_root_task` builds an A5 root task for a K row), boot with `boot-image.py --smp 1` (K1R) or `--smp 4 --virt` (K2R). A5 on E1-H: `./build-a5-e1h.sh step1|step2 [MUTANT]`, boot with `boot-a5.py --machine-extra iommu=smmuv3,highmem=off --device edu,dma_mask=0xffffffffff --device edu,dma_mask=0xffffffffff --trace "smmuv3_translate_*" --marker A5S1_PASS IMAGE` (`--smp 4` for a K2R image). `highmem=off` is required: the ECAM address and the I/O address window at 4 GiB assume it.
- **QEMU's sources** for the SMMU and `edu` were read from the public repository at tag `v11.1.3` as documentation; nothing of them is in this repository.
- `git log --show-signature` fails on this machine although the commits carry signatures and
  GitHub verifies them. Run the spike's drivers under bash: zsh does not split words.
