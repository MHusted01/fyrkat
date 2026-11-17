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
- **Checks are not a bottleneck.** The 47 successful runs of the CI workflow up to 2026-11-15
  took a median of 53 seconds from creation to last update. Three took longer than 90 seconds,
  the longest 17 minutes, and that one was on its third attempt.
  [Measured: `gh run list --workflow CI --limit 100`] `cargo xtask check` took about 10 seconds
  at the median over more than 130 runs, and `verify-evidence.py` a few seconds. [Measured,
  local: transcript query; the run counts depend on how commands are matched]
- **Pull requests.** Of 14 merged pull requests, 7 merged within three minutes of opening and 7
  took between 21 minutes and 17 hours. [Measured: `gh pr list`] PRs 6, 8 and 14 were reviewed
  after they were pushed. [Inferred: the commits those reviews name are on GitHub unfixed]
- **Review rounds:** PR 6 took five, PR 8 four, PRs 15 and 16 three between them, and E1, E2,
  E3 and A2a one each. [Inferred from the descriptions callers gave the 22 runs]
- **Reviews find real defects.** At least 16 of the 22 reports carried a finding rated blocking
  or material: device registers mapped as cacheable memory, verifiers that accepted altered
  evidence, a change that broke an earlier experiment's build. This count is from report
  headings, not from re-checking each finding. [Inferred]
- **What reviewers read.** Of 6.6M characters of tool results, 34% was the spike plan and other
  records, 20% project source, and 5% diffs. The grouping reads paths and command text, so it is
  approximate. 2% was an identical repeat of an earlier read with the Read tool, which carries
  39% of intake; reads through the shell are not tracked. [Measured, local]
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
9. **CI verifies the recorded spike evidence** and runs the verifier's self-test. The job becomes
   a required check once it has passed on a clean checkout.
10. **The macOS workflow's weekly trigger is removed** until a run of it passes.

The rules in force are in [docs/development/workflow.md](../development/workflow.md).

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
instructions. Its brief is built mechanically. The earlier findings are saved as a key before
any replay starts, in a directory that is not an ancestor or a sibling of the run's directory.
GitHub, the network, the real repository and the transcripts are forbidden. The run's tool calls
are read afterwards from its transcript, and the run is void if one of them reached material
outside it. That reading is a check on a reviewer that was told the rules, not a defence against
one that tries to evade them: it is evidence of a blind run and not proof of one. A script that
flags suspect calls for that reading was written with this note and is not part of it. Its review
did not converge in two follow-up rounds, so it was split out to be redone as a smaller change
of its own, as the approved procedure directs. Scoring happens after the report is returned,
strict and lenient.

## 6. Validation log

Results are appended here as they are produced. Nothing in this section changes a setting: the
values in `CLAUDE.md` and the agent files stay as they are until a hypothesis in section 5 has
a result that meets its rule, and these results do not.

### Review rounds and convergence [Measured, local; review reports and `git log`]

| Unit | Rounds | Open Blocker + Major after each round |
|---|---|---|
| Foundation (this note and the scripts), #18 | 3 | 9, then 2, then 3. The last round did not shrink the set, so the audit script was split out and the rest merged |
| Review system, #19 | 5 | 12 distinct (two independent reviews), then 4, 2, 2, 0 |
| Records and CI, #20 | 5 | 6 distinct (two independent reviews), then 3, 1, 0, 0 |

The first round of each unit found the most. Later rounds found problems in what the previous
fix added, or older problems of the same kind. In the review system the findings after round 3
were increasingly exotic Git settings, and the review's question was narrowed to configurations
a developer could plausibly have. [Inferred: the narrowing is the author's judgment; the
reviewer applied it.]

### H4 and H5: effort for review [Measured, local; one replay and two paired reviews]

**Replay of `96f68c2`** (PR 6, the C1 and C2 method files). One replay per arm, each a separate
headless session in an exported two-commit tree, with a mechanically built packet. The key was
the original review's report, saved before any replay ran, with its matching rules written first. Finding 6 of the original needed the network and was excluded.

| | Original, `xhigh`, full repository | Replay, `xhigh` | Replay, `high` |
|---|---|---|---|
| Checkable original findings found (strict, lenient), of 6 | n/a | 2, 4 | 1, 3 |
| Estimated cost, requests, wall time | $3.4, 49, 16 min | $1.3, 19, 5.9 min | $0.6, 10, 2.8 min |

- Neither arm missed a Blocker or High: the original had none. The one miss that only the `high`
  arm made, on first-touch cost in the C2 method, was a Major. By rule 6 of the matching rules
  this does not reject `high` for standard depth. By rule 7, the two findings both arms missed
  are attributed to the replay conditions (no network, no repository history).
- Both arms found a real defect the original did not: the per-hop figure divides by 4 call-reply
  pairs where the chain has 3. A later review round fixed that on `main`.
- The replay of `004bf9e` was started twice and cut off both times by the usage limit. Both
  attempts are void and were not scored.

**Paired live reviews** of two changes at deep depth, `xhigh` against `high`, same brief, blind
to each other.

| Change | `xhigh` | `high` |
|---|---|---|
| Review system, first commit | 1 Blocker and 9 Major; 10 of 12 distinct material issues; 134k tokens | 8 Major (the Blocker's issue rated Major); 10 of 12; 101k tokens |
| Records and CI, first commit | 4 Major; 5 of 6 (rated the sixth Minor); 156k tokens | 6 Major; 6 of 6; 104k tokens |

Neither arm missed a finding the other rated Blocker. Each missed material issues the other
found on the first change.

**What this supports.** On these cases `high` did about as well as `xhigh` at about two thirds
to three quarters of the tokens. That is two paired reviews and one replay. It is not enough to
change a setting: H5 asks for seeded defects in `unsafe`, MMIO and verifier code, and none has
been run, and the replay cannot decide H5 at all. **Decision: effort stays as it is.**

### Not yet tested

- **H1, H2:** sessions have not yet been run one task at a time with the 200k window, so there
  is no comparison.
- **H3:** the review packet is in use. Intake per review was not measured separately for the
  replays; the usage figures above include the reading the packet saved. [Speculative]
- **H6, H7:** not measured.
- **Seeded-defect tests** for H5: not run.
- **The replay audit script** is not in the repository. Its review did not converge and it was
  split out of #18. It has since been reworked in a scratch copy and still needs its own review.

## 7. Limits of this note

- The baseline is five days of one project phase, mostly documentation and spike code.
- How a subscription counts cached tokens and large contexts is not published, so the estimate
  may not track the usage limit.
- Nothing here shows that quality is preserved by any change. Section 5 exists to test that, and
  for deep review the test is seeded defects and paired reviews, which are small samples.
