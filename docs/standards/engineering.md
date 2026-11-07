# Engineering standards

How Rust code is written and reviewed in this repository. Unsafe code has its own
[standard](unsafe-rust.md).

## Rust

- Edition 2024, stable toolchain only, pinned ([toolchain policy](toolchain.md)).
- Lints are set once in `[workspace.lints]`. `unwrap`, `expect` and `panic!` are denied
  outside tests. A crate that needs an exception states the reason in an `#[allow(..., reason = "...")]`.
- Format with rustfmt as configured. Warnings are errors in `cargo xtask check`.
- Functions stay under about 50 lines and files under about 400. Split by purpose.
- Prefer immutable data. Local mutation is fine where it is clearer.
- Public items are documented. Comments explain why, not what.

## Error handling

- Return `Result` and propagate with context. Never swallow an error silently.
- Messages that reach a user say what failed, with what input, and what to do next.
- In kernel and driver code, a failure path is designed, not discovered: define what state the
  system is left in. Panic is a last resort and needs justification in review.
- Validate everything that crosses a trust boundary: files, user input, messages, hardware
  registers, firmware tables.

## Dependencies

Every new dependency is a reviewed decision. Before adding one, record in the PR:

1. What it does that is not worth writing, and why a smaller option does not suffice.
2. Licence, compatible with `deny.toml`.
3. Maintenance: recent releases, number of maintainers, open security issues.
4. Size of its transitive tree, and whether it uses `unsafe` or build scripts.
5. For kernel or boot code: whether it is `no_std` and allocation-free.

`xtask` has no external dependencies by policy. Dependencies that affect the trusted
computing base need an ADR. `cargo-deny` enforces licences, advisories, bans and sources.

## Review

- Every change goes through a pull request, with the verification section filled in using
  real command output.
- Review should be independent: the author does not approve their own change. While there
  is a single maintainer, the owner merges their own PRs with no required approval, and the
  `reviewer` agent is adversarial review, not independent human review.
- Security-sensitive paths (`.github/`, `deny.toml`, `rust-toolchain.toml`, `.claude/`,
  `Cargo.lock`, `docs/adr/`) are listed in the PR job summary and need owner approval.
- A claim in a PR or document carries an evidence label from the
  [ADR README](../adr/README.md#evidence-labels).

## Technical debt

Debt is allowed only if it is written down. Mark it in code with `TODO(debt-NNN)` and open an
issue with the same number stating: what was deferred, why, the risk of leaving it, and the
condition that should trigger paying it. An unlabelled `TODO` or `FIXME` fails review. Review
the list at each milestone boundary in the [roadmap](../roadmap.md).
