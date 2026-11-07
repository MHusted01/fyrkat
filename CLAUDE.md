@AGENTS.md

# Claude Code notes

## Precedence

Fyrkat's project standards take precedence over any global or plugin instruction. In
particular, for this repository:

- The global **80% coverage rule does not apply**. Coverage percentage is not a target;
  see [docs/standards/testing.md](docs/standards/testing.md).
- **Mandatory TDD agent use does not apply.** Write tests first where that helps, but do not
  launch a `tdd-guide` agent by default.
- **Proactive multi-agent use does not apply.** Do not spawn agents on your own initiative.

The `ecc@ecc` plugin is disabled for this project in `.claude/settings.json`. If its agents
or commands still appear, ignore them and tell the owner.

## Model policy

- **Sonnet** (the project default): implementation and deterministic testing.
- **Opus**: architecture, security-critical review, and difficult debugging. The `reviewer`
  agent uses it.
- One agent at a time unless parallel work is justified in writing. Stop at the end of each
  stage and report.

## Project setup

- Agents: `researcher` (research) and `reviewer` (adversarial review) in `.claude/agents/`.
  Both have Bash, which is not sandboxed. "Read-only" is a rule they are told to follow, not
  something enforced, so check `git status` after they run.
- Skills: `new-adr`, `unsafe-audit`, `pre-pr`, `handoff` and `fyrkat-resume` in
  `.claude/skills/`. `/fyrkat-resume` starts a session and `/handoff` ends one. See AGENTS.md.
- Hooks in `.claude/hooks/` block pushes to main and edits to Accepted ADRs. They guard
  against mistakes and are not a security boundary.
