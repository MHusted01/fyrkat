# Engineering workflow: baseline, proposal and validation plan

- **Status:** Research note. The owner approved the proposal in section 4 on 2026-11-15 and
  authorized its implementation and validation. Sections 5 and 6 are filled in as results arrive.
- **Question:** where do time and usage go in agent-driven work on Fyrkat, and what can be
  removed without weakening review?
- **Scope:** the eight working sessions of 2026-11-07 to 2026-11-11 (S1 to S8), which produced
  the fifteen commits on `main` up to `460f385`.

Labels follow [AGENTS.md](../../AGENTS.md#evidence-labels). **[Measured, local]** means measured
from session transcripts that exist only on the owner's machine, so the figure is reproducible
there and nowhere else. Unless a source is named, such a figure is the output of
[scripts/workflow-metrics](../../scripts/workflow-metrics/README.md). Where a source is named
as "transcript query", the figure came from a one-off query of the same transcripts that is not
in the repository. Dollar figures are an estimator's output for comparing runs, not a bill. The
scripts' token totals are about 4% below Claude Code's own cost records, because background
requests are not in the transcripts.

## 1. Baseline

| Role | Requests | Output tokens | Thinking share of output | Context per request | Estimate |
|---|---|---|---|---|---|
| Main loop, Sonnet 5.5 | 1,434 | 2.40M | 41% | 330k | $100 |
| Main loop, Fable 5.2 (one session) | 144 | 0.40M | 34% | 458k | $51 (Claude Code's own record) |
| `reviewer`, Opus 5.5, 22 runs | 1,622 | 2.25M | 71% | 157k | $137 |
| `researcher`, Sonnet 5.5, 1 run | 42 | 0.03M | 45% | 68k | $1 |

All rows are [Measured, local].

- **Review is the largest consumer**, about 47% of the estimate. Every one of the 22 runs ran at
  `xhigh` effort. The agent file set no effort, so the level came from a user-level setting.
  [Measured, local]
- **The main loop pays mostly for context.** Cache reads and writes are 74% of its estimate. In
  five of eight sessions, more than 80% of input tokens came from requests above 200k tokens of
  context, and in none less than 62%. The largest request read 963k. The sessions compacted
  four times in total. [Measured, local]
- **The 5-hour usage limit stopped work five times.** [Measured, local]
- **A session starts at 52k to 58k tokens** before any work [Measured, local: transcript query].
  A fresh session then reads 0.6M to 1.8M tokens before it first changes a file other than the
  handoff. [Measured, local; the detection of changes made through the shell is a heuristic]
- **Checks are not a bottleneck.** A CI run took about a minute in all but one of the runs
  listed on 2026-11-15, and 17 minutes in that one [Measured: `gh run list`]. `cargo xtask check`
  took a median of 10 seconds over 135 runs and `verify-evidence.py` 2 seconds over 138.
  [Measured, local: transcript query]
- **Pull requests.** Of 14 merged pull requests, 7 merged within three minutes of opening and 7
  took between 21 minutes and 17 hours. [Measured: `gh pr list`] PRs 6, 8 and 14 were reviewed
  after they were pushed.
- **Review rounds:** PR 6 took five, PR 8 four, PRs 15 and 16 three between them, and E1, E2,
  E3 and A2a one each. [Inferred from the descriptions callers gave the 22 runs]
- **Reviews find real defects.** At least 16 of the 22 reports carried a finding rated blocking
  or material: device registers mapped as cacheable memory, verifiers that accepted altered
  evidence, a change that broke an earlier experiment's build. This count is from report
  headings, not from re-checking each finding. [Inferred]
- **What reviewers read.** Of 6.6M characters of tool results, 34% was the spike plan and other
  records, 20% project source, and 5% diffs. The grouping reads paths and command text, so it is
  approximate. 2% was an identical repeat of an earlier read. [Measured, local]
- **Records.** Three of the fifteen commits on `main` carried only records [Measured: `git log`].
  Reviewers repeatedly reported stale handoff lines and one claim restated differently in
  several files. [Inferred from report headings]
- **The advisor.** An advisor model is recorded on all 4,129 main-loop response records of S1
  to S8 (1,578 requests), and no response contains an advisor call. [Measured, local:
  transcript query] The first review of this note read the same transcripts as showing only
  that the advisor beta was enabled. The count of the `advisorModel` field settled it.

## 2. GitHub: what is confirmed and what is inferred

**Confirmed** [Measured: GitHub API, read-only, 2026-11-15, and the session transcripts]

- The `gh` token agents use is the owner's OAuth token. Its scopes are `repo`, `workflow`,
  `admin:ssh_signing_key`, `user`, `gist` and `read:org`. Its permission on the repository is
  admin. The repository has one collaborator.
- Agent sessions have written repository settings with it. Seven branch-protection writes
  succeeded, among them the first `PUT` on `main` and a create and delete on a throwaway branch.
  The same session also wrote the Actions permissions, the default permission of the workflow
  token and other repository settings, and deleted a ref.
- No hook inspects `gh api`. The local control is an `ask` permission rule.
- Rulesets are available to this account on a public, user-owned repository: another such
  repository has two active rulesets with empty bypass lists, and the API reports that its admin
  cannot bypass them. No blocked push was observed. Fyrkat's ruleset endpoints respond and list
  nothing.

**Documented** by GitHub (read on 2026-11-15):

- Protecting a branch "requires admin or owner permissions to the repository".
  (`docs.github.com/en/rest/branches/branch-protection`, "Update branch protection")
- Branch-protection and ruleset writes are listed under the "Administration" repository
  permission. (`docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens`)
- A ruleset accepts a rule of type `creation`. (`docs.github.com/en/rest/repos/rules`, "Create a
  repository ruleset")
- Personal access tokens are "tied to the user who generated them".
  (`docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens`)

**Inferred, not tested**

- That the token could weaken the protection of `main` today. Testing it would change a setting.
- That the `ask` rule produced a prompt for those writes. The transcripts do not record prompts.
- That a ruleset with a `creation` rule can be made on Fyrkat. Section 6 records the test.

Consequences [Inferred]:

- Every server-side rule is a convention for as long as the agent holds an admin token.
- With the `admin:ssh_signing_key` scope an agent could add a signing key to the owner's
  account, and its commits would then show as verified for the owner. With `gist` it has a way
  to publish data.
- Narrowing the token is not enough. Any token of the owner's, including a fine-grained one,
  acts as the owner, so GitHub cannot tell agent from owner. A rule that needs the owner's
  review of an agent's work needs a separate account for the agent.

## 3. Findings

1. Cost follows context size and review effort, not checks or CI.
2. Review is worth its cost and must stay deep where it guards a security property. Most spike
   work does. The saving therefore has to come from what a review reads, not from how hard it thinks.
3. A third of review intake is the plan and records. The plan is 1,375 lines at `460f385`, and
   half of it is the append-only Amendments.
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
| H2 | A 200k compaction window lowers usage within a task | Tokens; identical reads and commands repeated after a compaction; active time | Lower total, no rise in repeats. Otherwise try 300k, then keep the default |
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
forbidden, and `audit.py` checks the run's tool calls afterwards; one forbidden access voids the
run. The audit reads command text, so a clean audit is evidence of a blind run and not proof of
one. Scoring happens after the report is returned, strict and lenient.

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
