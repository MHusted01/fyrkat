# Releases

Fyrkat has made no release. There is nothing to run, so nothing is supported
([platforms](../supported-platforms.md)). This document fixes the process in advance, so the
first release follows it.

## Versioning

- Versions follow [Semantic Versioning](https://semver.org/). While the major version is `0`,
  any release may break compatibility, and the release notes say what changed.
- `0.1.0` is not tagged until there is a bootable system that meets acceptance criteria in the
  [roadmap](../roadmap.md). Workspace crates stay at `0.0.0`, `publish = false`, until then.
- Interfaces that other software depends on, once they exist (system call ABI, IPC
  protocols), carry their own version and compatibility policy, set by an ADR.

## Procedure

1. The owner decides to release. Agents do not tag or publish.
2. Confirm `main` is green: `cargo xtask check` and `cargo xtask boot` pass in CI, and the
   weekly macOS workflow is not failing.
3. Update the changelog from merged PRs, grouped by Conventional Commit type, and list known
   issues and what was only tested under emulation.
4. Bump versions in one commit: `chore: release vX.Y.Z`.
5. Create a signed, annotated tag `vX.Y.Z` on that commit.
6. Build artefacts from the tag in CI with the pinned toolchain. Publish checksums with them.
   Record the toolchain, tool and dependency versions in the release notes.
7. Never move or delete a published tag. Fix forward with a new version.

## Security fixes

A fix for a reported vulnerability is prepared privately through GitHub security advisories,
released with a new patch version, and credited and described only after the fix is available.
See [SECURITY.md](../../SECURITY.md).
