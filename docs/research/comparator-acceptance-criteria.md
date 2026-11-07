# Comparator acceptance criteria

- **Status:** Draft proposal. Nothing is implemented, and building a comparator is **not
  authorized**. The [spike plan](sel4-spike-plan.md) makes the comparator prototype a scope limit
  that needs the owner's approval.
- **Purpose:** fix, before anything is built, what an optional comparator must show and how its
  result is judged, so that the judging cannot be bent by the result.
- **Adoption:** these criteria **add rules to Stage D**, which the plan treats as fixed. They take
  effect only if the owner approves them and records an Amendment (item P3 of the
  [decision package](s1-decision-package.md)). They add no criterion to A1 to C3.
- **Scope beyond the plan:** the plan describes "a minimal Rust kernel slice". This draft applies the
  same rules to any alternative built to be measured, such as an exokernel-style design or seL4 with
  an approved Class 2 patch. The owner may narrow it back to the plan's wording.

## Why a comparator, and when

The plan's Stage D counts a design that is not built as a cost and never as a capability. That is
sound, and it means no alternative can win without being built. The comparator is how an alternative
earns measured evidence. It is built only to answer a question the spike has left open.

**Trigger (all must hold, recorded before any work starts):**

1. Stage D has run, and the owner and the Stage D record name one **specific question** that a
   measurement on a second design would answer, and name the workloads that decide it.
2. The question cannot be settled by the bill of work, by published figures, or by more seL4
   experiments.
3. The owner approves the comparator, its scope, its **effort budget** and its **tuning budget** in
   writing. The **minimum meaningful difference** δ is fixed here at **10%**, before any seL4 result
   exists, so that it cannot be chosen after seeing one. Changing it is an Amendment with the owner's
   approval.

A comparator proposed without a named question is not accepted.

## Fairness rules

These apply equally to the comparator and to seL4.

| Rule | Meaning |
|---|---|
| **Same method** | The comparator is measured with the committed [C1](../../spikes/sel4-feasibility/results/C1-method.md) and [C2](../../spikes/sel4-feasibility/results/C2-method.md) methods: same host, QEMU, HVF, counter, warm-up, batches and runs. A method change is an Amendment that applies to both designs. |
| **Same machine shape** | Both boot with the same vCPU count, RAM and cross-core placement. A comparator that runs on one core while seL4 runs the 4-vCPU K2 is not comparable, and cross-core workloads are then Incomplete. |
| **Same run conditions** | The two designs run in alternating order on the same host in the same series. |
| **Same policy or same budget** | Where a workload depends on a policy (for example, the C2 pager retypes and zeroes one frame per fault), the comparator uses the equivalent policy for its headline. Any other policy is a separate result. Both sides get the same declared tuning budget, and the results state what each tried. |
| **No hypothetical credit, no hypothetical blame** | Only what is built and measured counts as capability. A property that the comparator demonstrates by a passing test counts as measured evidence. A claim that seL4 lacks that property is tested on seL4 with the same test. A property that the test cannot show on seL4 is reported as "not shown on seL4", never as "lacks". |
| **Pre-registered** | The outcomes, δ, the decisive workloads and the consequences below are committed before building starts. Changing them after results exist is an Amendment with the owner's approval. |

## Scope bound

The comparator implements only what the named question needs. For an IPC or page-fault question:
entry at EL1 under HVF, address spaces, whatever authority checks the design uses on its measured
path, synchronous call and reply, and fault reflection to a user-level pager. Nothing else.

The decisive workloads come from C1 (W1 to W6) and C2 (F1 to F4). **A workload the comparator does
not run is Incomplete and counts as a cost**, not as an omission. There is no aggregate score. The
results are a per-workload table, and the question named at the trigger says which rows decide.

**Effort budget:** set by the owner. When it is spent, work stops. An extension is recorded before
any further measurement, with the reason.

## Validity gates

A comparator number counts only if every gate holds. A failed gate makes the numbers **Void**.

| Gate | Test | Why |
|---|---|---|
| **V1 Isolation is demonstrated by outcome** | The comparator passes the equivalent of B3's cross-client read refusal and of B4's illegal-authority sub-tests: use of an empty or wrong-typed authority, amplified rights, and a forged identity are each refused with no effect. For **each check the design relies on**, a mutant with that check removed fails at least one of these tests | Outcome-based, so it fits designs that check at bind time or by other means, and it shows each check is needed |
| **V2 Revocation is demonstrated by outcome** | The equivalent of the B2 use-after-revoke test passes. A design without revocation fails this gate, and its numbers are Void | Speed without revocable authority is not the same product, and this is a stated Fyrkat requirement |
| **V3 Rust rules** | No `unwrap`, `expect` or `panic!` outside tests, and every `unsafe` has a `// SAFETY:` comment (`unsafe-audit`) | AGENTS.md rules |
| **V4 Reproducible** | One documented command builds it twice with identical output or a documented cause | The A1 standard |
| **V5 Same counter and kernel build rules** | Both designs use the counter configuration of the C1 method. The seL4 side uses the build the C1 method fixes | Equal timing source |

## Statistic and outcomes

The measurement unit is the run median from the C1 or C2 method. Runs are 30 per design per
workload, and **all series are reported**. The first complete valid series counts. A repeat series
is allowed once, is declared before it starts, and does not replace the first.

For each workload compute the ratio **R = (comparator median of run medians) / (seL4 median of run
medians)** and a **95% bootstrap confidence interval** for R: 10,000 resamples of the 30 run medians
of each design, drawn independently with replacement, a percentile interval (2.5th and 97.5th
percentiles), and a fixed seed and generator written in the method before the first run. With δ the
minimum meaningful difference:

| Outcome | Condition | Consequence |
|---|---|---|
| **Void** | A validity gate failed | The numbers are not used. The failed gate is the finding. It counts as a cost in Stage D |
| **Incomplete** | The slice did not run the workload, or the budget ran out | Counts as a cost in Stage D. The work done is recorded |
| **Better** | The interval's upper bound is below 1 − δ | Reported to the owner. Reopens the performance assumptions in ADR 0004. Does not falsify |
| **Worse** | The interval's lower bound is above 1 + δ | Evidence against the comparator for that workload. Does not falsify |
| **Equivalent** | The whole interval lies within 1 − δ and 1 + δ | No performance reason to prefer either design for that workload |
| **Inconclusive** | None of the above | No difference is shown. It is not read as Equivalent |

Using an interval keeps one bad run from deciding the result. The run count is fixed at 30.

## What a comparator result can and cannot change

- It can change the **performance** assumptions in ADR 0004 and the Stage D weighing of cost.
- It does not by itself decide ADR 0004. The owner decides.
- It cannot be generalised beyond the slice. A fast IPC path is not a fast kernel.
- **Assurance is weighed separately and on the same terms for both designs.** The measure is the A2
  gap classes for each design's cells, and any machine-checked proof that can be reproduced from the
  repository, for either side. A comparator slice has no such proof today. seL4's own A2 cannot be
  Pass in this spike either, since no QEMU run is V. The plan's reconsideration criterion for a
  Verus or similar proof stays open for both.

## Recorded disclosures

Every comparator results file states: the named question and the decisive workloads, δ, the effort
and tuning budgets and what was spent, what each side tried, the commit of each build, every series
run, the validity-gate results, and every limit of the slice.
