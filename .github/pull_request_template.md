## Summary

What changes and why. Link the issue or ADR.

## Type

<!-- Conventional Commit type: feat, fix, refactor, docs, test, chore, perf, ci -->

## Verification

Commands you ran and what they printed. Say what you did not run, and why.

| Command | Result |
|---|---|
| `cargo xtask check` | |
| `cargo xtask boot` | |
| Other | |

- Evidence is [Measured], [Documented], [Inferred] or [Speculative]; claims about hardware rest on hardware, not emulation.
- A new check was shown failing at least once: yes / no / not applicable.

## Checklist

- [ ] Commits are signed and carry a `Signed-off-by` line (DCO)
- [ ] Docs describe behaviour that exists, and nothing undecided is stated as decided
- [ ] No secrets and no personal email addresses (public research-source URLs excepted)
- [ ] Any `unsafe` has a `// SAFETY:` comment and is called out in this description
- [ ] Touches a security-sensitive path (`.github/`, `.claude/`, `.cargo/`, `xtask/`, `docs/adr/`, `deny.toml`, `rust-toolchain.toml`, every `Cargo.toml` and `Cargo.lock`, `AGENTS.md`, `CLAUDE.md`): owner approval needed
- [ ] An ADR is not accepted by this PR unless the owner is doing it
