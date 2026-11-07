# Contributing

Read [AGENTS.md](AGENTS.md) first. It holds the project rules and approval gates, and applies
to people as well as AI agents. Setup is in [docs/development.md](docs/development.md).

## Workflow

1. Open an issue first for anything larger than a small fix. Decisions that are expensive to
   reverse need an [ADR](docs/adr/README.md), not a PR alone.
2. Branch from `main`. One logical change per pull request.
3. Make the change, tests first where the behaviour can be tested.
4. Run `cargo xtask check`. Run `cargo xtask boot` if you touched boot, firmware, `xtask` or CI.
5. Open the PR using the template, and fill in the **Verification** section with the commands
   you ran and their real results. Say what you did not run.
6. Address review. The owner merges; contributors do not merge their own PRs.

Only the project owner accepts ADRs. Changes to `.github/`, `.claude/`, `.cargo/`, `xtask/`, `docs/adr/`, `deny.toml`, `rust-toolchain.toml`, every `Cargo.toml` and `Cargo.lock`, `AGENTS.md`, `CLAUDE.md` are security-sensitive and need owner approval.

## Commit messages

[Conventional Commits](https://www.conventionalcommits.org/): `<type>: <description>`, with
an optional body that explains why. Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`,
`perf`, `ci`. Use `!` or a `BREAKING CHANGE:` footer for incompatible changes.

## Sign-off and signing

- **DCO.** Every commit carries a `Signed-off-by: Your Name <you@example.com>` line, added by
  `git commit -s`. It certifies the [Developer Certificate of Origin](https://developercertificate.org/):
  you wrote the change or have the right to submit it under the project licence. Use an
  address you are comfortable having public in history.
- **Signed commits.** Commits are cryptographically signed (GPG, SSH or S/MIME) and show as
  verified on GitHub. See GitHub's documentation on signing commits.

## Verification

A PR is not ready until `cargo xtask check` passes locally and in CI. Do not weaken, skip or
delete a check to make it pass; fix the cause, or open an issue and explain. Claims in PR
text and documents describe behaviour that exists and was observed. Label evidence as in the
[ADR README](docs/adr/README.md#evidence-labels), and never present an emulator result as
hardware evidence.

## Conduct and security

Participation is covered by the [Code of Conduct](CODE_OF_CONDUCT.md). Report vulnerabilities
privately, as described in [SECURITY.md](SECURITY.md), not in issues or PRs.
