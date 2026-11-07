# Architecture decision records

An ADR records one significant decision: what was chosen, why, what was rejected,
and what evidence would change the outcome. ADRs are the source of truth for
architectural decisions. Other documents link here rather than restating them.

## When one is required

Write an ADR for any decision that is expensive to reverse or that constrains other
components: kernel structure, privilege boundaries, the capability model, ABI
commitments, CPU targets, boot flow, major dependencies, and security policy.
Routine implementation choices do not need one.

## Status

| Status | Meaning |
|---|---|
| Proposed | Under review. Not binding, and must not be described as decided. |
| Provisional | Approved by the owner for planning. Work may rely on it, but named conditions can reopen it. |
| Accepted | Approved by the project owner. Binding until superseded. |
| Rejected | Considered and declined. Kept so the reasoning is not lost. |
| Withdrawn | Removed by the owner before acceptance. Its reasons stay on record. |
| Superseded | Replaced by a later ADR, which it must link to. |

Only the project owner moves an ADR to Provisional or Accepted. Agents may draft and
propose ADRs, but may not accept them.

## Evidence labels

Every factual claim that supports a decision carries one of these labels:

- **[Measured]**: produced by this project, reproducible from the repository.
- **[Documented]**: stated by a primary source, cited with its location.
- **[Inferred]**: engineering reasoning from the above. It may be wrong.
- **[Speculative]**: an expectation with no supporting evidence yet.

## Process

1. Copy `0000-template.md` to the next free number.
2. Fill in every section. Write "None known" rather than deleting a section.
3. Open a PR with status Proposed.
4. On acceptance, change the status and date in the same PR.
5. To change an Accepted decision, write a new ADR and mark the old one Superseded.
   Do not rewrite history.

## Index

| ADR | Title | Status |
|---|---|---|
| [0001](0001-kernel-architecture.md) | Kernel architecture | Part A Provisional, Part B Withdrawn |
| [0002](0002-initial-cpu-architecture.md) | Initial CPU architecture | Provisional |
| [0003](0003-boot-strategy.md) | Boot strategy | Provisional |
| [0004](0004-kernel-foundation.md) | Kernel foundation | Proposed (working hypothesis) |
