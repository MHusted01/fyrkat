# Session handoff

A snapshot for the next session, not a source of truth. [ADRs](../adr/README.md) and Git win over it.
It records approvals and grants none. Owner decisions are in the last entries of the
[spike plan's Amendments](../research/sel4-spike-plan.md#amendments). Start with `/fyrkat-resume`.

## Snapshot

- **Date:** 2026-11-11 (local; the evidence timestamps are UTC and still read 2026-11-10). `origin/main` is `bb9863e` (PR 16, A5 steps 0 to 2), on top of `48acaf0` (PR 15, Stage B preparation), on top of `bbaf23c` (PR 14). Both were squash-merged on 2026-11-11 00:00 and 00:04 UTC after three independent reviews and green CI. [Measured: `git`, `gh`]
- **This file travels in the documentation PR** (branch `docs/s1-session-record`: this handoff, the plan's Amendments, the roadmap, the A5 proposal's corrections). If that PR is not merged when you read this, those four files are the only uncommitted work.
- **Open PR besides it:** #9 (Dependabot, `protobuf`). **Not to be merged; its alerts are not to be dismissed.**
- **ADRs:** 0001 Part A Provisional, Part B Withdrawn; 0002 and 0003 Provisional; 0004 Proposed. **None is Accepted.** [Measured: Status lines]
- **Owner's last instruction (2026-11-10):** the engineering-session message recorded in the plan's Amendments ("2026-11-10 (later)"). Its authorizations were for that session's scope.

## Milestone status

- **M0:** complete. **S1** (exit: the owner decides ADR 0004): in progress.
- **Stage A:** A1 Pass (U); A3 Fail (U) under HVF on one M2 Pro; A2a Investigate. **A4 and A5 not run.** A5 steps 0 to 2 are preparatory and exploratory work, **not an A5 outcome**.
- **E1, E2, E3:** merged, Pass (U), functional only, on the E1-H kernel. Not Stage B evidence.
- **Stage B:** not executed. The matrix of the plan's Amendment of 2026-11-10 is the **working experimental plan** (owner, 2026-11-10); it is not an ADR.

## Completed this session (all [Measured] under QEMU 11.1.3 TCG; records in `spikes/sel4-feasibility/results/`)

- **Review and repair of D25 to D27.** First review: not merge-ready (verifiers that accepted altered evidence, cacheable device mappings, unchecked safe accessors, a swapped table row, Route I provenance gaps). Fixed; A5 step 0 re-recorded. Route I's gaps are stated in its record and closed for the positive K1 and K2 boots by the release-kernel evidence; its three negative controls were not re-run.
- **Release kernels** ([ReleaseKernel](../../spikes/sel4-feasibility/results/ReleaseKernel.md), D28): **K1R passes 7 functional tests, K2R (4 vCPUs) 8, in 3 of 3 boots each**, through seL4's elfloader, logging only through a user-level PL011 driver (`pl011.rs`). The kernels in the images have the same configuration and function-table hashes as the published K1, K1R, K2, K2R. Controls: debug kernels, two mutants, two mismatched pairings. Not isolation (the workers share the root task's capability space), not Stage B.
- **A5 step 1** ([A5-step1](../../spikes/sel4-feasibility/results/A5-step1.md), D29): a user-level SMMUv3 driver (`smmuv3.rs`). With the SMMU enabled and one stream configured, `edu`'s DMA is translated to the mapped page and refused at an unmapped address, at a physical address, on a write to a read-only mapping, and for a second unconfigured device; a cleared entry is honoured until the invalidation command completes. 3 of 3 boots on E1-H and on K2R; five mutants; QEMU's trace agrees.
- **A5 step 2, exploratory** ([A5-step2](../../spikes/sel4-feasibility/results/A5-step2.md), D30; design reviewed before the first boot; verifier fixed by hash beforehand and not requiring an outcome): with a stream's mapping left in place, the frame's untyped is revoked, the kernel reuses the same physical page, and **the device reads and overwrites the new contents with no fault**. Cleared, invalidated and synced before the revoke: refused. Cleared without invalidation: not refused. Reused as a CNode: the device reads a raw capability, and a capability it copied into an empty slot is accepted when copied out and survives the revocation of its origin. **One task played every role; this is not the proposal's falsifier; A5-arm is neither passed nor failed; the record lists four options and selects none.**

## Authorizations in force

Source: the plan's Amendments, entry "2026-11-10 (later)".
- **Used this session:** the matrix as working plan; review, commit, push, PR and merge of the completed work (PRs 15, 16 and the documentation PR); K1R and K2R; A5 step 1; A5 step 2 after its design review; tooling.
- **These were for that session.** AGENTS.md says agents never push or merge and that the owner merges; the owner authorized otherwise by message for this session (and for PRs 13 and 14 before). The conflict is noted in the Amendments for the owner to settle. **A later session needs the owner's own word before any push, PR or merge.**
- **Not authorized:** executing Stage B; A4; the full A5 (K3 and its four tests); the comparator; any change to the seL4 kernel, ABI, dependencies or ADR statuses; new tools or installations; touching PR 9; modifying or bypassing CI.
- Agents do not spawn agents on their own initiative; the `reviewer` runs of this session were covered by the owner's instruction to use independent review.

## Pending approvals (the owner's)

1. **The design of K3:** the four options in section 3 of the A5 step 2 record (a DMA pool; shadow buffers; the kernel binding mappings to capabilities; the kernel deferring reuse). The last two change the kernel (Class 3, not available under the present policy).
2. **Whether a hypervisor-mode row joins the Stage B matrix:** E1HR (17 functions differ from K0) and K0Q (6) are textually nearer K0 than K1R (105) and K2R (210).
3. **Whether to authorize the proposed next experiment** (K3 proper: SMMU server and client in separate capability spaces, the four A5 tests with mutants), or Stage B, or A4's AArch64 half.
4. **AGENTS.md against per-session merge authorizations:** amend the file, or merge personally.
5. Toolchain policy (`nightly-2026-08-21` is S1-only); ADR 0002/0004 text; Tier 2 for A4's x86-64 half; PR 9 stays as decided.

## Blockers and conflicts

- No conflict found between this file, Git and the ADRs, apart from item 4 above.
- **Privacy exposure remains:** `refs/pull/7/head` still resolves to `c99300d`. `main` never held it. See EVIDENCE-PRIVACY.
- macOS CI has never completed (GitHub-side failures; workflow unmodified).
- Open: `RUSTSEC-2024-0449` (host-side); a base-controlled `pull_request_target` check; CI uses QEMU 8.2.2 against the spike's 11.1.3, and CI does not run `verify-evidence.py`.

## Uncommitted changes

After the documentation PR: none of ours. **Untracked, not ours:** `.agents/` and `.codex/` (they include hooks and absolute home paths): never stage them; stage by name, never `git add -A`.
**Gitignored, local only, keep:** `spikes/sel4-feasibility/external/` (all builds, including `relk-build/`, `a5-step1-build/`, `a5-step2-build/`, `e3-build/`) and `results-raw/` (raw logs; `A5-step0-superseded-first-run` and `A5-step2-first-run` are the earlier runs kept on purpose). Do not `git clean`, `checkout .`, `stash` or `reset`.
Local branches: `main` (at `bb9863e`; behind once the documentation PR merges), `spike/s1-prep-work` (at `bbaf23c`, superseded, never pushed), `spike/stage-b-prep` and `spike/a5-smmu` (merged), `docs/s1-session-record`, and `local-only/s1-workspace-unsanitized` (**never push**).

## Verified results

| Command | State | Result |
|---|---|---|
| `python3 -B verify-evidence.py` (in `spikes/sel4-feasibility`) | the tree of `bb9863e` | 165 of 165 checks |
| `python3 -B verify-evidence.py --self-test` | same | 170 of 170 corruptions caught |
| `cargo xtask check` | same, plus the four documentation files | `check: all 12 steps passed` |
| CI on PRs 15 and 16 | their head commits | all three required checks passed |

**Not verified:** anything on hardware; the CI QEMU against the spike's images; clippy on the spike workspace; `cargo xtask boot` (nothing it covers changed); the last re-recording of the evidence and the last text corrections, which were made after the third review and are not themselves reviewed (the records and D27, D29, D30 say exactly what is and is not).

## Next actions

1. **Needs the owner:** pending items 1 to 4. Until then no new experiment.
2. **If the owner authorizes K3 proper:** turn `smmuv3.rs` into a server task with its own capability space (the E2 and E3 spawn code is the model), give a client derived frame capabilities and no ancestor, and run the four A5 tests with mutants on K2 and K2R; step 2's scenario A is the positive control it must reproduce when the client is given the ancestor. No dependency or kernel change is needed for options 1 and 2.
3. A2b (complete the dependency lists for K1, K1R, K2, K2R) is still future work for A2-final.

## Context not recorded elsewhere

- **Evidence pins.** Each evidence set records the SHA-256 of its inputs, and shared files (`a5_mmio.rs`, `pl011.rs`, `slots.rs`, `smmuv3.rs`, `edu.rs`, `boot-a5.py`, `build-relk.sh`, `build-a5-e1h.sh`, `object_allocator.rs`) are inputs of several sets. Editing one means re-running `run-a5-step0-evidence.sh`, `run-relk-evidence.sh`, `run-a5-step1-evidence.sh` and `run-a5-step2-evidence.sh` as applicable (under bash; about 12 minutes together), then `sanitize-run.py <A5-step0|ReleaseKernel|A5-step1|A5-step2>` and `verify-evidence.py`. Never edit a listed file while its driver runs or while a reviewer is reading the tree. `build-routei.sh`, `boot-image.py`, `a2a-compare.py` and `build-e2.sh` are pinned by merged evidence: do not change them.
- **Running the experiments by hand.** Release kernels: `./build-relk.sh K1R` (or `K2R path/to/k2-smc.dtb`; `RELK_BIN=a5_step1_root_task` builds an A5 root task for a K row), boot with `boot-image.py --smp 1` (K1R) or `--smp 4 --virt` (K2R). A5 on E1-H: `./build-a5-e1h.sh step1|step2 [MUTANT]`, boot with `boot-a5.py --machine-extra iommu=smmuv3,highmem=off --device edu,dma_mask=0xffffffffff --device edu,dma_mask=0xffffffffff --trace "smmuv3_translate_*" --marker A5S1_PASS IMAGE` (`--smp 4` for a K2R image). `highmem=off` is required: the ECAM address and the I/O address window at 4 GiB assume it.
- **QEMU's sources** for the SMMU and `edu` were read from the public repository at tag `v11.1.3` as documentation; nothing of them is in this repository.
- The local `core.hooksPath` guard, the unsanitized branch and its backup, the SSH-signing note (`git log --show-signature` fails locally; the commits carry signatures and GitHub verifies) and the zsh word-splitting note are as in the previous handoff. `cargo xtask check` in a temporary worktree fails `cargo-nextest` and `cargo-deny` only because `.tools/bin` is not there.
