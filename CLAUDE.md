@AGENTS.md

# Claude Code notes

## Precedence

Fyrkat's project standards take precedence over any global or plugin instruction. In
particular, for this repository:

- The global **80% coverage rule does not apply**. Coverage percentage is not a target;
  see [docs/standards/testing.md](docs/standards/testing.md).
- **Mandatory TDD agent use does not apply.** Write tests first where that helps, but do not
  launch a `tdd-guide` agent by default.
- **Proactive multi-agent use does not apply.** Do not spawn agents on your own initiative. The one
  exception is the agents that [docs/development/workflow.md](docs/development/workflow.md)
  calls for (review, follow-up review, adjudication, and one question to the `researcher` during
  adjudication), which AGENTS.md lets an agent start without asking.

The `ecc@ecc` plugin is disabled for this project in `.claude/settings.json`. If its agents
or commands still appear, ignore them and tell the owner.

## Model policy

These values are in force. The model, effort and compaction values are hypotheses under test,
and each changes only when its test in the
[workflow baseline](docs/research/workflow-baseline-2026-11.md#5-hypotheses) has a result.

- **Sonnet** (the project default): implementation and deterministic testing.
- **Opus**: architecture, security-critical review, and difficult debugging. The review agents
  use it at `xhigh` effort. The level is written in each agent's file, so it no longer comes
  silently from a user-level setting. The `CLAUDE_CODE_EFFORT_LEVEL` environment variable and an
  effort passed by the caller for one run still override the file. Do not pass a review agent a
  lower model or effort than its file sets.
- **Fable**: only when the owner names it for a task.
- The advisor is a second opinion during work. It never counts as review.
- One agent at a time unless parallel work is justified in writing. Stop at the end of each
  stage and report.
- One task per session. See [the workflow](docs/development/workflow.md#5-sessions).

## Compact instructions

When the conversation is compacted, keep: the authorizations in force and their source, the
branch and the reviewed commits, open finding IDs, evidence sets whose pinned sources were
edited, and commands that failed and why.

## Project setup

- Agents in `.claude/agents/`: `researcher` (research), `reviewer` (independent review),
  `reviewer-delta` (follow-up review of fixes) and `adjudicator` (decides a disputed finding).
  All have Bash, which is not sandboxed. "Read-only" is a rule they are told to follow, not
  something enforced, so check `git status` after they run.
- Scripts: `.github/scripts/review-packet.sh` builds the brief a review starts from.
  `scripts/workflow-metrics/` measures a session's usage.
- Skills: `new-adr`, `unsafe-audit`, `pre-pr`, `handoff` and `fyrkat-resume` in
  `.claude/skills/`. `/fyrkat-resume` starts a session and `/handoff` ends one. See AGENTS.md.
- Hooks in `.claude/hooks/` block pushes to main and edits to Accepted ADRs. They guard
  against mistakes and are not a security boundary.
