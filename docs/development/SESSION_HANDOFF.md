# Session handoff

What the next session needs and no other file holds. A snapshot, not a source of truth:
[ADRs](../adr/README.md) and Git win over it, and it records approvals without granting any. Each
fact has one home ([workflow, Records](workflow.md#4-records)); this file links to it. Start with
`/fyrkat-resume`, which reads the branch, the commits and the pull requests from Git.

## Authorizations in force

- **Standing (owner, 2026-11-15):** edits to security-sensitive paths for the engineering
  workflow; review, follow-up and adjudication agents; local commits on branches other than `main`;
  the workflow validation runs (replays, seeded defects, paired reviews); settlement of disputed
  findings by the workflow. Recorded in the
  [Amendments, 2026-11-15](../research/sel4-spike-amendments.md#2026-11-15-the-owners-approval-of-the-engineering-workflow-and-its-standing-authorizations).
- **Merging** was authorized for the pull requests that implement the workflow, and for nothing
  else. A later session needs the owner's word before any other push, pull request or merge.
- **Not authorized:** executing Stage B; A4; the full A5 (K3 and its four tests); the comparator;
  any change to the seL4 kernel, ABI, dependencies or ADR statuses; new tools or installations;
  touching PR 9; modifying or bypassing CI or a GitHub protection.

## Waiting for the owner

1. **The design of K3:** the four options in section 3 of the A5 step 2 record (a DMA pool; shadow buffers; the kernel binding mappings to capabilities; the kernel deferring reuse). The last two change the kernel (Class 3, not available under the present policy).
2. **Whether a hypervisor-mode row joins the Stage B matrix:** E1HR (17 functions differ from K0) and K0Q (6) are textually nearer K0 than K1R (105) and K2R (210).
3. **Whether to authorize the proposed next experiment** (K3 proper: SMMU server and client in separate capability spaces, the four A5 tests with mutants), or Stage B, or A4's AArch64 half.
4. **AGENTS.md against per-session merge authorizations:** amend the file, or merge personally.
5. Toolchain policy (`nightly-2026-08-21` is S1-only); ADR 0002/0004 text; Tier 2 for A4's x86-64 half; PR 9 stays as decided.
6. **An identity for agents:** a separate GitHub account with write access, and the owner's token
   out of the agent's environment. Agents use the owner's admin token today, so every server-side
   rule is a convention. See the [baseline, section 2](../research/workflow-baseline-2026-11.md#2-github-what-is-confirmed-and-what-is-inferred).

## Blockers and open findings

- **Privacy exposure remains:** `refs/pull/7/head` still resolves to `c99300d`. `main` never held it.
  See [EVIDENCE-PRIVACY](../../spikes/sel4-feasibility/results/EVIDENCE-PRIVACY.md).
- The macOS workflow has never completed a run. It is now started by hand only.
- Open: `RUSTSEC-2024-0449` (host-side); a base-controlled `pull_request_target` check; CI uses
  QEMU 8.2.2 against the spike's 11.1.3.
- Workflow hypotheses not yet decided are listed in the
  [baseline, section 6](../research/workflow-baseline-2026-11.md#6-validation-log).

## Local state that Git does not show

- **Untracked, not the project's:** `.agents/` and `.codex/` (they include hooks and absolute home
  paths). Never stage them. Stage by name, never `git add -A`.
- **Gitignored, local only, keep:** `spikes/sel4-feasibility/external/` (all builds) and
  `results-raw/` (raw logs, including earlier runs kept on purpose). Do not `git clean`,
  `checkout .`, `stash` or `reset` in the main checkout.
- **Never push** `local-only/s1-workspace-unsanitized`.
- `spike/k3-isolation` holds uncommitted K3 work that predates the split of the Amendments. Its new
  Amendments entry goes in `sel4-spike-amendments.md`, and its handoff is rewritten in this format.

## Verified, and not verified

CI shows the checks for each merged commit. It also runs `verify-evidence.py` and its self-test. **Not verified:** anything on hardware; the CI QEMU against the spike's images;
clippy on the spike workspace.

## Next actions

1. **Needs the owner:** the items above. Until items 1 to 3 are decided, no new experiment.
2. **Authorized:** continue the workflow validation in the
   [baseline](../research/workflow-baseline-2026-11.md#5-hypotheses) and record each result there.
3. **If the owner authorizes K3 proper:** see the K3 record on `spike/k3-isolation`.
4. A2b (complete the dependency lists for K1, K1R, K2, K2R) is still future work for A2-final.

## Context not recorded elsewhere

- **Evidence pins.** Each evidence set records the SHA-256 of its inputs, and shared files (`a5_mmio.rs`, `pl011.rs`, `slots.rs`, `smmuv3.rs`, `edu.rs`, `boot-a5.py`, `build-relk.sh`, `build-a5-e1h.sh`, `object_allocator.rs`) are inputs of several sets. Editing one means re-running `run-a5-step0-evidence.sh`, `run-relk-evidence.sh`, `run-a5-step1-evidence.sh` and `run-a5-step2-evidence.sh` as applicable (under bash; about 12 minutes together), then `sanitize-run.py <A5-step0|ReleaseKernel|A5-step1|A5-step2>` and `verify-evidence.py`. Never edit a listed file while its driver runs or while a reviewer is reading the tree. `build-routei.sh`, `boot-image.py`, `a2a-compare.py` and `build-e2.sh` are pinned by merged evidence: do not change them.
- **Running the experiments by hand.** Release kernels: `./build-relk.sh K1R` (or `K2R path/to/k2-smc.dtb`; `RELK_BIN=a5_step1_root_task` builds an A5 root task for a K row), boot with `boot-image.py --smp 1` (K1R) or `--smp 4 --virt` (K2R). A5 on E1-H: `./build-a5-e1h.sh step1|step2 [MUTANT]`, boot with `boot-a5.py --machine-extra iommu=smmuv3,highmem=off --device edu,dma_mask=0xffffffffff --device edu,dma_mask=0xffffffffff --trace "smmuv3_translate_*" --marker A5S1_PASS IMAGE` (`--smp 4` for a K2R image). `highmem=off` is required: the ECAM address and the I/O address window at 4 GiB assume it.
- **QEMU's sources** for the SMMU and `edu` were read from the public repository at tag `v11.1.3` as documentation; nothing of them is in this repository.
- The local `core.hooksPath` guard, the unsanitized branch and its backup, the SSH-signing note (`git log --show-signature` fails locally; the commits carry signatures and GitHub verifies) and the zsh word-splitting note are as in the previous handoff. `cargo xtask check` in a temporary worktree fails `cargo-nextest` and `cargo-deny` only because `.tools/bin` is not there; and if that worktree shared this checkout's `target/`, the task runner's binary is left pointing at the worktree, so after the worktree is removed `cargo xtask check` says "`git` was not found" until `cargo clean -p xtask`.
