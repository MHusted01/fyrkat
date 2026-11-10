# Session handoff

A snapshot for the next session, not a source of truth. [ADRs](../adr/README.md) and Git win over it.
It records approvals and grants none. Owner decisions are in the last entries of the
[spike plan's Amendments](../research/sel4-spike-plan.md#amendments).

## Snapshot

- **Date:** 2026-11-09. `origin/main` is `44d1d70` (PR 13, E3, squash-merged; before it `59dc7cb` E2, `c90f0e6` E1). CI on `44d1d70` passed. [Measured: `git`, `gh`]
- **Checked-out branch:** `spike/a2a-assurance`, PR #14 (open at the time of writing; review corrections in progress). It carries the A2a work, the E3 final-acceptance records and the A5 proposal. Follow-on work (release variants, Route I, A5 step 0) is on separate branches and is **not** part of it.
- **Open PR:** only #9 (Dependabot, `protobuf` 3.20.3 to 5.29.6). **Not to be merged; its alerts are not to be dismissed.** [Measured: `gh pr list`]
- **ADRs:** 0001 Part A Provisional, Part B Withdrawn; 0002 and 0003 Provisional; 0004 Proposed. **None is Accepted.** [Measured: Status lines]

## Milestone status

- **M0:** complete (owner, 2026-11-07). **S1** (exit: the owner decides ADR 0004; M1 cannot be finalized before it): in progress.
- **Stage A:** A1 Pass (U); A1 rerun Pass (U), accepted for build reproducibility only. A3 Fail (U): unmodified seL4 17.0.0 under HVF on one M2 Pro (rule 2 applies to that HVF hypothesis only).
  **A2a: run (2026-11-09), outcome Investigate** by the plan's definition, accepted by the owner as the recorded result subject to independent review; the K1 and K2 cells for P1 to P4 are **expected** class B but **not yet classified** (the dependency lists were not completed: a departure from the plan, to be done in A2b); the P5 cell of K3 cannot be classified. Record: [A2a](../../spikes/sel4-feasibility/results/A2a.md). **A4, A5: not started.**
- **E1, E2, E3: merged, Pass (U), functional only, on the experiment-only E1-H kernel (hypervisor support on), which is not a row of the assurance matrix.** E2 and E3 are finally accepted (E3: limited to the tested revocation topology under single-vCPU QEMU TCG with the debug kernel; D21 to D23 approved).
  They are precursors, **not** Stage B, P1, P2 or P3 evidence. E3 limits that must not be dropped: the verifier was tightened **after** the second review and that was **not** independently reviewed; some forged-log gaps in `verify_e3.py` remain; the `SAFETY` comment on `static mut FREE_PAGE_PLACEHOLDER` in `e3_spawn.rs` is inaccurate. Not production-ready.

## A2a in short (the agent's reading; the record has the detail and the limits)

- **Three things kept apart.** *Build success:* K0 (`AARCH64_verified.cmake`, platform `tx2`), K1, K2 and the informational E1H all build with `aarch64-elf-gcc` 16.2.0, twice. *Configuration similarity:* against K0, 554 (E1H), 396 (K1) and 339 (K2) of about 900 functions are textually identical; the tables are reproducible across clean builds, complete against `nm`, and recomputed by the verifier.
  *Formal-verification applicability:* none established. The public documentation lists AArch64 verified configurations as hypervisor-mode, for listed platforms (QEMU virt is not one), C-level functional correctness, not covering SMP, MCS, IOMMU/DMA, debug or printing builds, boot, or timing channels, and it **names no seL4 version**.
- **Corrected earlier statements:** (1) the handoff used to say the E1-H kernel was "probably further from K0"; it is the opposite: **every** AArch64 verified configuration is hypervisor-mode, K0 included, so K1 and K2 differ from K0 in that option and E1-H does not (one option only, not "closer to verified"). (2) The first A2a record said the documentation names no seL4 version; **the FAQ points to the verification manifest, whose `17.0.0.xml` pins the pinned seL4 commit** with l4v `12c300e7…` (found by the independent review, re-checked by me). Which AArch64 proof sessions exist for it is not established.
- **Debug against release:** K0 is a release build; K1, K2 and E1-H are debug builds. Sampled differences on the capability path are debug assertions, so much of the function-level difference is probably the debug option [Inferred; not measured; needs release variants, which were out of scope].
- Named path functions against K0: `cteRevoke`, `cteDelete`, `isMDBParentOf`, `isCapRevocable`, `deriveCap`, `invokeUntyped_Retype` and `resetUntypedCap` are identical in K1, K2 and E1-H; `cteInsert`, `cteDeleteOne`, `finaliseCap`, `createObject` and `decodeUntypedInvocation` are not. Of the functions that differ from K0, 259 (K1), 299 (K2) and 254 (E1-H) are in no property file list, some on the paths (`mdb_node_get_mdbNext`, `sanitiseRegister`, `decodeTCBInvocation`).

## S1 gates now

| | Status | What decides it |
|---|---|---|
| **Configuration and loader (before Stage B)** | Needs the owner | `sel4-kernel-loader` boots only hypervisor-enabled kernels (EL2); the plan's K1 and K2 are non-hypervisor, so only seL4's own elfloader could start them. **In the committed evidence, no loader is known to start K2**: A3 recorded that its elfloader aborts on the PSCI conduit, and K1 has run only sel4test's userland under it. The owner has since ruled that K1 and K2 remain legitimate baselines and asked for Route I (elfloader) to be investigated; that work is on a separate branch and is not recorded here. E1 to E3 ran on a hypervisor-enabled kernel that is not a matrix row. The matrix also does not say whether K1 and K2 are debug or release, and says they run under HVF, which A3 contradicts |
| **A4** (UEFI boot, AArch64 and x86-64) | Not authorized | AArch64 half: EDK2 firmware ships with Homebrew QEMU; a thin UEFI stub is new code. x86-64 half needs Tier 2 (`x86_64-elf-gcc`, rustup `x86_64-unknown-none`), not installed, not approved. Pass needs both architectures with no kernel patch |
| **A5** (SMMUv3 and DMA isolation) | Held for a reviewed design | [A5 design proposal](../research/a5-design-proposal.md): the crux is revoke-while-mapped, and the smallest falsification test is one stream, one page, one `edu` device. A5-arm Fail falsifies the hypothesis, so this is the likeliest falsifier. A cheaper informational first probe could run on E1-H |
| **A2-final, Stage B, C, D** | Later | A2-final needs the required Stage B tests on a matrix configuration; none has run on one |

## macOS CI (checked, independent of A2a)

- The scheduled run `42629351498` (2026-11-09 13:52 UTC) was **cancelled by GitHub with no step executed**: "The job was not acquired by Runner of type hosted even after multiple attempts", with a macOS arm64 capacity notice; `runner_id` 0 [Measured].
- The **one manual run authorized**, `42674266306` (18:28 UTC), **failed after 51 s with no job started** and one annotation, "Internal server error" with a correlation ID: a GitHub-side error [Measured: `gh`, and the public run page read by a fetch agent]. `gh` reports "likely failed because of a workflow file issue", but no file defect is established: the file equals the copy GitHub holds, it uses the same pinned GitHub-owned actions as `ci.yml`, the repository allows GitHub-owned actions, and `actionlint` passes.
- **The workflow was not modified.** The macOS path (`cargo xtask check` and `boot` on a hosted runner) has still never run to completion. No further run was triggered (one was authorized).

## Authorizations in force

Source: the owner's messages in this conversation; the plan's Amendments (entries of 2026-11-09).
- **Authorized and used:** A2a, local execution and evidence verification, the one manual macOS run, the A5 design proposal as a document; and (owner message of 2026-11-09, after the A2a report) commit, push, PR #14 and merging it when the independent review is satisfactory and the required checks pass, without a further approval. **Authorized and in progress on separate branches:** release variants of K1, K2 and E1-H, the Route I investigation and the Stage B matrix Amendment, and A5 step 0 (an environment and feasibility probe only). The E3 PR and its merge are used up.
- Standing: D2, D3, D7, D9, D10, D14(b), D17, D18 (2026-11-08); D19, D20 for E2; D21, D22, D23 for E3 (2026-11-09). **D24 (A2a tooling) was authorized as routine tooling and is not independently reviewed.**
- **Not authorized:** executing Stage B, A4, the full A5 experiment, the custom-kernel comparator, Class 3 kernel modifications; changing ADR statuses, dependencies, kernel or loader source; any new tool or installation; replacing K1 or K2 solely to suit the Rust loader; merging or touching PR 9; modifying or bypassing CI requirements.
- Agents never push, force push or merge without the owner; do not spawn agents on their own initiative; an agent does not review its own work.

## Pending approvals (the owner's)

1. Nothing for PR #14 once the review is satisfactory and CI is green: the owner authorized the merge. The A2a tooling (D24) has had one independent review; its low and editorial findings are listed in the A2a record.
2. The configuration, build-type and loader question above, before any Stage B work.
3. Whether to authorize the A5 design (and the informational E1-H probe), A4's AArch64 half, or release variants of K1, K2 and E1H (the smallest addition that would separate the debug effect from the hypervisor, platform and SMP effects).
4. Long-term toolchain policy (`nightly-2026-08-21` is approved for S1 only); whether ADR 0002 or 0004 text should change; Tier 2 for A4's x86-64 half.
5. PR 9: the owner decided to keep the `protobuf` pin and not merge or dismiss. Its conflict with the `sel4-deps` `protobuf<4` metadata is known (installs use `--no-deps`); no more `protobuf` experiments.

## Blockers and conflicts

- The S1 stop condition blocks Stage B, A4 and A5 until the owner names one. No conflict found between this file, Git and the ADRs, apart from the plan's matrix saying K1 and K2 run under HVF.
- **Privacy exposure remains:** `refs/pull/7/head` still resolves to `c99300d`; the original commits are fetchable by SHA. Not erasure. `main` never held them.
- Open items: `RUSTSEC-2024-0449` (host-side, policy unchanged); a base-controlled `pull_request_target` check; CI uses QEMU 8.2.2 against the spike's 11.1.3; the macOS workflow has not completed once.

## Uncommitted changes

`git status -sb`: `## spike/a2a-assurance` (from `main` at `44d1d70`). Modified: this file, `docs/research/sel4-spike-plan.md` (Amendments), `docs/roadmap.md`, `spikes/sel4-feasibility/{verify-evidence.py, results/{E3.md, deviations.md, evidence-manifest.txt}}`.
New: `docs/research/a5-design-proposal.md`, and under `spikes/sel4-feasibility/`: `build-a2a.sh`, `a2a-compare.py`, `run-a2a-evidence.sh`, `verify_a2a.py`, `results/A2a.md`, `results/A2a/`. `.agents/skills/*` and `.codex/*` (agent and hook configuration; `.codex/hooks.json` holds absolute home paths) are untouched and not part of this:
**stage files by name, never `git add -A`**. No gated file is changed. The raw builds are in the gitignored `external/a2a-build*` and `results-raw/A2a`.

## Verified results

| Command | State | Result |
|---|---|---|
| `verify-evidence.py` | the working tree with the A2a evidence | 100 of 100 checks (9 for A2a) |
| `verify-evidence.py --self-test` | same | 60 of 60 corruptions caught (46 earlier, 13 new on the A2a evidence, 1 for its removal) |
| `a2a-compare.py self-test` | same | the parser sample passes (4 of 4) |
| A2a builds | `external/a2a-build/` and `a2a-build-repro/` | 8 of 8 exit 0; the function tables are byte-identical across the two builds of each configuration |
| `cargo xtask check` | before this file's last edit | see "Next actions": rerun before any commit |

`cargo xtask boot` was not run (A2a boots nothing). **Not verified:** that the documentation's quotes are exact (they were read by a fetch agent); the macOS CI path; clippy on the spike workspace (not installed for the pinned nightly).

## Next actions

1. Merge PR #14 when the re-review is satisfactory and the required checks pass; then rebase the follow-on branches on `main` and open their PRs separately (A5 step 0 stays apart from A2a).
2. If the owner authorizes the push: run `cargo xtask check`, the verifier and its self-test; request an independent `reviewer` pass on the A2a tooling if the owner wants one (D24 is not reviewed); signed DCO commits staged by name; the PR description should mention the new Python/shell tooling and that no `unsafe` was added.
3. Smallest concrete engineering step after the decisions: if the owner authorizes the A5 probe, its step 0 (can the root task reach the SMMU's MMIO as a device untyped on the E1-H kernel, and does `-machine virt,iommu=smmuv3` with `edu` start under the existing harness). If instead release variants are authorized: `build-a2a.sh` gains three more IDs and the comparison is rerun.

## Context not recorded elsewhere

- Build output of E2, E3 and A2a is in the gitignored `spikes/sel4-feasibility/external/` (`e2-build`, `e3-build`, `e3-mutant-*`, `a2a-build`, `a2a-build-repro`, the `*-superseded-*` runs); raw logs in `results-raw/`. The A2a procedure is `run-a2a-evidence.sh`, then `sanitize-run.py A2a`, then `verify-evidence.py`; the E3 one is `run-e3-evidence.sh`.
  The ELFs embed build-dependent data: **publish hashes, never the binary.** The A2a `kernel_all_pp.c` files are not published (about 1 MB each, absolute paths); the tables derived from them are.
- **Unsanitized history** is on `local-only/s1-workspace-unsanitized` (at `81a2ca7`, `pushremote=no_push_remote`), retained on the owner's instruction, with a
  backup tarball (SHA-256 `768af917…`) beside the repository. **Never push it.** A local `pre-push` guard (`core.hooksPath` = `.git/fyrkat-hooks/`) refuses it;
  it covers ancestry and ref names only. Undo: `git config --local --unset core.hooksPath && rm -rf .git/fyrkat-hooks`.
- Commits are signed with SSH; `git log --show-signature` fails locally because `gpg.ssh.allowedSignersFile` is not set; GitHub verifies them. A project hook
  mistakes shell commands that mention the ADR directory for writes: use Edit or Read for ADRs. For privacy scans use `git ls-files`, not `grep -r`. The `reviewer`
  and `researcher` agents have Bash: check `git status` after they run. A zsh quirk: unquoted `$VAR` is not word-split, so run multi-word variable expansions under `bash`. Start with `/fyrkat-resume`.
