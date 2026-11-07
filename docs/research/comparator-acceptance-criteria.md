# Comparator acceptance criteria

- **Status:** Draft proposal. Nothing is implemented, and building a comparator is **not
  authorized**. The [spike plan](sel4-spike-plan.md) makes the comparator prototype a scope limit
  that needs the owner's approval.
- **Purpose:** fix, before anything is built, what an optional comparator must show and how its
  result is judged, so that the judging cannot be bent by the result.
- **Adoption:** these criteria take effect when the owner approves them and records the approval as
  an Amendment to the plan. They add no criterion to A1 to C3.
- **Candidate-neutral:** "comparator" means any alternative to unmodified seL4 that is built to be
  measured. That includes a minimal custom Rust kernel, an exokernel-style design, or seL4 with an
  approved Class 2 patch. The same rules apply to all of them.

## Why a comparator, and when

The plan's Stage D counts a design that is not built as a cost and never as a capability. That rule
is sound, and it means no alternative can win without being built. The comparator is the way an
alternative earns measured evidence. It is built only to answer a question that the spike has left
open.

**Trigger (all must hold, recorded before any work starts):**

1. Stage D has run, and the owner and the Stage D record name one **specific question** that a
   measurement on a second design would answer. Examples: "is seL4's same-core IPC the cause of the
   C1 result, or the virtualized host?" or "would a different revocation semantics remove the B2
   indirection?"
2. The question cannot be settled by the bill of work, by published figures, or by more seL4
   experiments.
3. The owner approves the comparator, its scope and its **effort budget** in writing.

A comparator proposed without a named question is not accepted.

## Fairness rules

These apply equally to the comparator and to seL4.

| Rule | Meaning |
|---|---|
| **Same method** | The comparator is measured with the committed [C1](../../spikes/sel4-feasibility/results/C1-method.md) and [C2](../../spikes/sel4-feasibility/results/C2-method.md) methods: same host, QEMU, HVF, counter, warm-up, batches, runs and statistics. A method change is an Amendment that applies to both designs. |
| **Same run conditions** | seL4 and the comparator run in alternating order on the same host in the same series. Neither gets a better time of day, thermal state or core placement. |
| **Same tuning effort** | seL4 is built as the C1 and C2 methods fix (release, fast path, the same options). The comparator gets a declared tuning budget. Both budgets are written down, and the results state what each side tried. |
| **Equal labels** | Both are U or M at best. A comparator carries label M or S as applicable and **no proof claim**. seL4 may cite only what its verified-configuration page states for the same configuration, and no QEMU run is V. |
| **No hypothetical credit** | Only what is built and measured counts as capability. Everything else is cost, as in Stage D. |
| **No hypothetical blame** | A property that seL4 lacks and the comparator demonstrates by a passing test counts as measured evidence for the comparator, however unconventional the design. |
| **Falsifiable and pre-registered** | The outcomes and their consequences below are committed before building starts. Changing them after results exist is an Amendment with the owner's approval. |

## Scope bound

The comparator implements only what the named question needs. For an IPC or page-fault question:

- entry at EL1 under HVF, address spaces, and a capability check that the measured path really
  performs;
- synchronous call and reply, and fault reflection to a user-level pager;
- nothing else: no scheduler beyond what the workloads need, no drivers, no filesystem.

The slice is measured on the C1 workloads W1 to W4 and, if it has three servers, W5 and W6. For a
page-fault question it is measured on C2's F1 to F3. Workloads that the slice cannot run are
reported as not run, never as zero.

**Effort budget:** set by the owner when approving. The work stops when it is spent, and the outcome
is then Incomplete (below). The cost is recorded for Stage D.

## Validity gates

A comparator number counts only if all of these hold. A failed gate voids the numbers and does not
produce an outcome by itself.

| Gate | Test | Why |
|---|---|---|
| **V1 Checks are on the measured path** | The code under timing performs the same classes of check as seL4's: capability lookup and type check, rights check, and an address-space switch with isolation. A reviewer pass confirms it in a fresh context. | A path that skips validation is not comparable. |
| **V2 Negative tests pass** | The comparator passes the equivalent of B4's illegal-capability sub-tests (empty slot, wrong type, amplified rights, forged badge) and B3's cross-client read refusal, and each is refused with no effect. | Speed without isolation is not the same product. |
| **V3 Rust rules** | No `unwrap`, `expect` or `panic!` outside tests, and every `unsafe` has a `// SAFETY:` comment (`unsafe-audit`). | AGENTS.md rules apply. |
| **V4 Reproducible** | One documented command builds it twice with identical output or a documented cause. | The A1 standard. |
| **V5 Counter parity** | Both designs use the same counter configuration. | Equal timing source. |

## Outcomes

Applied per measured workload, in this order, using the C1 and C2 statistics. "Range" is the
minimum to maximum of the 30 run medians.

| Outcome | Condition | Consequence |
|---|---|---|
| **Void** | A validity gate failed | The numbers are not used. The failed gate is the finding |
| **Incomplete** | The effort budget ran out before the slice ran the workload | Counts as cost in Stage D. The work done is recorded |
| **Better** | The comparator's range lies entirely below seL4's | Reported to the owner. Reopens the performance assumptions in ADR 0004. Does not falsify |
| **Equivalent** | The two ranges overlap | No performance reason to prefer either. Stage D rests on assurance, cost and the other results |
| **Worse** | The comparator's range lies entirely above seL4's | Evidence against the comparator for that workload. Does not falsify |

No fixed percentage is used, because the spread of the runs decides what is distinguishable on this
host. A "Better" on a performance workload is never an assurance result. Stage D weighs it against
the proof gap: seL4 has verified configurations on supported boards and a comparator has none.

## What a comparator result can and cannot change

- It can change the **performance** assumptions in ADR 0004 and the Stage D weighing of cost.
- It cannot lower the **assurance** cost of leaving seL4. That needs proofs, which a comparator
  slice does not have.
- It does not by itself decide ADR 0004. The owner decides.
- It cannot be generalised beyond the slice. A fast IPC path is not a fast kernel.

## Recorded disclosures

Every comparator results file states: the named question, the effort budget and what was spent, the
tuning each side received, the commit of each build, the validity-gate results, and every limit of
the slice.
