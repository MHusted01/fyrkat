# Engineering workflow: baseline, proposal and validation plan

- **Status:** Research note. The owner approved the proposal in section 4 on 2026-11-15 and
  authorized its implementation and validation. Sections 5 and 6 are filled in as results arrive.
- **Question:** where do time and usage go in agent-driven work on Fyrkat, and what can be
  removed without weakening review?
- **Scope:** the eight working sessions of 2026-11-07 to 2026-11-11 (S1 to S8), which produced
  the fifteen commits on `main` up to `460f385`.

Labels follow [AGENTS.md](../../AGENTS.md#evidence-labels). **[Measured, local]** means measured
with [scripts/workflow-metrics](../../scripts/workflow-metrics/README.md) from session
transcripts that exist only on the owner's machine. Such a figure is reproducible there and
nowhere else. Dollar figures are an estimator's output for comparing runs, not a bill.

## 1. Baseline

| Role | Requests | Output tokens | Thinking share of output | Context per request | Estimate |
|---|---|---|---|---|---|
| Main loop, Sonnet 5.5 | 1,434 | 2.40M | 41% | 329k | $101 |
| Main loop, Fable 5.2 (one session) | 144 | 0.40M | 34% | 450k | $51 (Claude Code's own record) |
| `reviewer`, Opus 5.5, 22 runs | 1,622 | 2.25M | 71% | 157k | $137 |
| `researcher`, Sonnet 5.5, 1 run | 42 | 0.03M | 45% | 68k | $1 |

All rows are [Measured, local].

- **Review is the largest consumer**, about 47% of the estimate. Every one of the 22 runs ran at
  `xhigh` effort. The agent file set no effort, so the level came from a user-level setting.
- **The main loop pays mostly for context.** Cache reads and writes are 74% of its estimate. In
  six of eight sessions, more than 80% of input tokens came from requests above 200k tokens of
  context. The largest request read 963k. The sessions compacted four times in total.
- **The 5-hour usage limit stopped work five times.**
- **A session starts at 53k to 58k tokens** before any work. A fresh session then reads 0.8M to
  3.0M tokens before its first edit.
- **Checks are not a bottleneck.** CI finishes in 40 to 65 seconds. `cargo xtask check` takes
  about 10 seconds and `verify-evidence.py` about 2. Most pull requests merged within two
  minutes of opening, because review happens before the pull request.
- **Review rounds:** PR 6 took five, PR 8 four, PRs 15 and 16 three between them, and E1, E2,
  E3 and A2a one each.
- **Reviews find real defects.** At least 16 of the 22 reports carried a finding rated blocking
  or material: device registers mapped as cacheable memory, verifiers that accepted altered
  evidence, a change that broke an earlier experiment's build. This count is from report
  headings, not from re-checking each finding. [Inferred]
- **What reviewers read.** Of 6.6M characters of tool results, 34% was the spike plan and other
  records, 27% project source, and 5% diffs. 8% was a file the reviewer had already read.
- **Records.** Three of the fifteen merges carried only records. Reviewers repeatedly reported
  stale handoff lines and one claim restated differently in several files.
- **The advisor** was configured for all 4,250 requests and never called.

## 2. GitHub: what is confirmed and what is inferred

**Confirmed** [Measured: GitHub API, read-only, 2026-11-15, and the session transcripts]

- The `gh` token agents use is the owner's OAuth token with the `repo` and `workflow` scopes.
  Its permission on the repository is admin. The repository has one collaborator.
- Agent sessions have written repository settings with it: seven branch-protection writes
  succeeded, among them the first `PUT` on `main` and a create and delete on a throwaway branch.
- No hook inspects `gh api`. The local control is an `ask` permission rule.
- Rulesets work for this account on a public, user-owned repository: another such repository
  has two active rulesets with empty bypass lists, and the API reports that its admin cannot
  bypass them. Fyrkat's ruleset endpoints respond and list nothing.

**Documented** by GitHub's REST reference: protecting a branch "requires admin or owner
permissions"; branch-protection and ruleset writes fall under the "Administration" permission of
a fine-grained token; rulesets accept a `creation` rule; a personal access token is "tied to the
user who generated" it.

**Inferred, not tested**

- That the token could weaken the protection of `main` today. Testing it would change a setting.
- That the `ask` rule produced a prompt for those writes. The transcripts do not record prompts.
- That a ruleset with a `creation` rule can be made on Fyrkat. Section 6 records the test.

Two consequences. A fine-grained token of the owner's acts as the owner, so GitHub cannot tell
agent from owner; a rule that needs the owner's review of an agent's work needs a separate
account. And every server-side rule is a convention for as long as the agent holds an admin token.

## 3. Findings

1. Cost follows context size and review effort, not checks or CI.
2. Review is worth its cost and must stay deep where it guards a security property. Most spike
   work does. The saving therefore has to come from what a review reads, not from how hard it thinks.
3. A third of review intake is the plan and records. The plan is 1,386 lines, and half of it is
   the append-only Amendments.
4. One fact kept in several files costs twice: once to write, once to review for agreement.
5. Long sessions that span several tasks carry each task's context into the next.

## 4. Proposal (approved 2026-11-15)

1. **Review depth by impact, uncertainty and claim**, not by whether work is exploratory.
2. **Commit before review**, and give the reviewer a packet built mechanically from two commits.
3. **Focused follow-up review** of fixes to blocking and major findings.
4. **A convergence procedure** in place of a round limit: diagnose why review is not converging,
   settle a disagreement by experiment where one exists, and bring the owner only an owner's
   decision or a material risk that remains.
5. **One home per fact.** The handoff stays tracked and stops repeating what Git holds.
6. **One task per session.**
7. **Settings are hypotheses** (section 5). Today's values stay until measured.
8. **A separate agent identity and rulesets** before any delegated merge.

The rules themselves are written in `docs/development/workflow.md` when they come into force.

## 5. Hypotheses

| | Hypothesis | Measure | Adopt if |
|---|---|---|---|
| H1 | One task per session lowers usage per verified task | Tokens by role; re-orientation tokens | Lower total in matched tasks, no more rework |
| H2 | A 200k compaction window lowers usage within a task | Tokens; files re-read and commands re-run after a compaction; active time | Lower total, no rise in repeats. Otherwise try 300k, then keep the default |
| H3 | A review packet and a split plan cut reviewer intake by a third | Intake characters by category | Intake falls and replay recall does not |
| H4 | `high` effort matches `xhigh` for standard-depth review | Replay recall | No known blocking or high finding is missed |
| H5 | `high` matches `xhigh` for deep review | Seeded defects in `unsafe`, MMIO and verifier code; paired reviews of deep changes | Every seeded defect is found by both. Replays cannot decide this |
| H6 | Sonnet at `medium` matches `high` for the main loop | Tokens, failed checks, fix commits after review | No rise in rework |
| H7 | A one-hour cache for reviewers lowers cache writes | Cache-write tokens per review | Lower total |

Recorded per task: tokens by role, active time, elapsed time to merge, review rounds, evidence
re-recordings, files re-read, fix commits after review, defects found after merge, and owner
interventions.

### Replays of recorded reviews

Three commits that were reviewed before they were fixed are reviewed again: `96f68c2` (PR 6),
`05c40b2` (PR 8) and `004bf9e` (PR 14).

**Limits.** Three cases. Only pushed, unfixed commits can be replayed; the reviews of uncommitted
trees (E3, D25 to D27, K3), which hold most of the `unsafe` and MMIO work, cannot. A recorded
review is one sample of a process that varies, so today's configuration is run again as a
control. Recall counts only defects someone already found. The scorer knows the answers. A replay
can reject a configuration. It cannot show one is safe for deep review.

**Blinding.** The reviewer works in a scratch directory outside the repository that holds two
commits made from `git archive` of the base and the head: no later history and no remote. It runs
as a separate session started there, so it loads neither this project's memory nor its present
instructions. Its brief is built mechanically. The earlier findings are written to a key file
before any replay starts. GitHub, the network, the real repository and the transcripts are
forbidden, and `audit.py` checks every command of the run afterwards; one forbidden access voids
the run. Scoring happens after the report is returned, strict and lenient.

## 6. Validation log

Results are appended here as they are produced.

| Date | Hypothesis | What ran | Result | Label |
|---|---|---|---|---|
| | | *(none yet)* | | |

## 7. Limits of this note

- The baseline is five days of one project phase, mostly documentation and spike code.
- How a subscription counts cached tokens and large contexts is not published, so the estimate
  may not track the usage limit.
- Nothing here shows that quality is preserved by any change. Section 5 exists to test that, and
  for deep review the test is seeded defects and paired reviews, which are small samples.
