# Evidence privacy: what is public and how to check it

The logs under [A1/](A1/), [A1-rerun/](A1-rerun/) and [A3/](A3/) are **sanitized copies**. The unredacted originals ("raw") are kept
only on the machine that produced them, in a gitignored directory, and are not published. This note says
what was removed, what was kept, and how to re-check the conclusions from the public copies alone.

## Status of earlier publication

**Not erased. Do not read this section as a claim that the exposure is gone.**

1. The raw logs were first pushed in the commits `e778e29`, `7e763f0`, `f835b21` and `c99300d` of branch
   `spike/s1-workspace`, in pull request 7 (never merged). They held the author's local user name and home
   path, about 720 times in 26 files.
2. The owner chose a narrow replacement. Pull request 7 was edited to remove the path and closed, and its
   remote branch was deleted. A new branch, `spike/s1-workspace-sanitized`, was built from `main` in new
   commits with sanitized copies of the logs. It is the branch of pull request 8. History **was** rewritten
   in that sense: the published branch was replaced, and `main` was not touched and was never force-pushed.
3. **The original commits remain retrievable.** On 2026-11-08, after the replacement, `c99300d` still
   resolved by SHA through the GitHub API of this public repository, and `refs/pull/7/head` still pointed
   to it [Measured: `gh api repos/{owner}/{repo}/commits/c99300d`, `git ls-remote origin 'refs/pull/7/*'`].
   Anyone who knows or guesses the SHA, anyone who cloned or forked while the branch was public, and any
   cache or mirror may still hold them. Pull request 7's edit history may also show its original text.
4. Only a GitHub Support request could ask for the retained references to be removed. **The owner decided on
   2026-11-08 not to make one at this time**, and no result is claimed from one.
5. `main` (pull requests 5 and 6) contains none of this.

## What the review found

| Category | Finding in the raw logs | Treatment in the public copies |
|---|---|---|
| Local home path and user name | About 720 occurrences in 26 files: build paths, `cargo` and `cmake` output, and the owner column of `ls -l` | Replaced by `<REPO>`, `<HOME>` and `<user>` |
| Host name, scratch and temp paths | None found | Rules exist and are applied if present |
| Homebrew inventory | 386 and 421 lines listing every installed formula | Cut to the formulae needed to reproduce A1 and A3, with a count and a SHA-256 of the full list |
| Homebrew taps | Three unrelated third-party tap names in warning output | Removed and replaced by a note |
| Email addresses, tokens, keys, IP or MAC addresses | None found. Commit authors use GitHub noreply addresses only | None needed |
| Binaries in history | None ever pushed. A stray Python bytecode file was removed before the first push | None needed |
| Hardware and OS details | Apple M2 Pro, 16 GB, macOS 27.2 build | **Kept**: the results depend on them |

## What was kept

Every measurement, error message, tool and compiler version, commit pin and hash (build artefact SHA-256s,
requirement hashes, source commits). Line order and content are unchanged apart from the replacements.

## How the copies were made, and how to check them

```
spikes/sel4-feasibility/sanitize-evidence.py      # raw (local) -> sanitized (public); deterministic
spikes/sel4-feasibility/verify-evidence.py        # re-check the conclusions from the public copies only
```

- [`evidence-manifest.txt`](evidence-manifest.txt) lists, per file, the SHA-256 of the raw original and of the
  sanitized copy. Only the second can be checked by a reader. The first lets the owner prove which raw file a
  public copy came from.
- [`A1/04-brew-drift-summary.txt`](A1/04-brew-drift-summary.txt) replaces the full before/after inventory
  comparison: it records the counts, the two added formulae, and the hashes of both full lists.
- `verify-evidence.py` runs 40 checks on the public copies and on the repository's `Cargo.lock`: the A1 build hashes (three outputs identical, the
  image different), the device-tree seed cause, the `add-payload` determinism, the loader defect numbers, the
  `cargo deny` results and the advisory path, the tool and compiler versions, the A3 boot results under HVF and
  TCG, the ID-register probe (ASIDBits 2 under TCG, 0 under HVF), the pins, the recorded kernel configuration of the two sel4test builds and the PSCI conduit in their device
  trees (A3 41 and 42), the A1 rerun (its hashes, the byte accounting against the original run, the compile-log crate
  versions and the repository's `Cargo.lock`), that the manifest hashes match and the manifest lists exactly the files under
  `A1/`, `A1-rerun/` and `A3/`, and that no home path, user name, host name or scratch path remains. The privacy check does not
  depend on who runs it: it looks for any macOS or Linux home-directory path, an encoded scratch-directory
  name, and the running user's own home path and host name. It checks the running user's name only when that name has at
  least six characters and is not a common service name, so it cannot prove that another person's name is absent:
  removing names is the sanitizer's job.

## Limits

- A sanitized log is not byte-identical to the raw one. Lines that held a path differ, and their text is
  otherwise the same. QEMU serial logs also change from CRLF to LF line endings, which is what Git stores. Hashes of build artefacts inside the logs are untouched.
- Someone without the raw logs cannot confirm the omitted Homebrew formulae. The recorded hash and the drift
  summary let the owner do so.
- The sanitizer reads the user, home and host names from the machine it runs on. Run it on the machine that
  holds the raw logs. Its matching is case-insensitive and does not fire inside a longer alphanumeric
  token, so an unusual name that is glued to other letters or digits would not be redacted, and the
  verifier's path-anchored checks would be the only net. It stops with an error if a Homebrew tap warning is
  not closed, or if a rule would change a file's line count.
- The sanitization was done by an agent. Before pull request 8 it had agent-run scans only. The tracked
  evidence files at `24634be` were byte-identical to a local, unpublished commit (`81a2ca7`) that had no
  independent review, and they differ from the reviewed but unsanitized `c99300d`. The independent review of
  pull request 8 then scanned the tree, the history of the pull-request commits, and the pull-request text.
