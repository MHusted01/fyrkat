# Evidence privacy: what is public and how to check it

The logs under [A1/](A1/) and [A3/](A3/) are **sanitized copies**. The unredacted originals ("raw") are kept
only on the machine that produced them, in a gitignored directory, and are not published. This note says
what was removed, what was kept, and how to re-check the conclusions from the public copies alone.

## Status of earlier publication

Before this review, the raw logs were pushed in the commits `e778e29`, `7e763f0`, `f835b21` and `c99300d` of
branch `spike/s1-workspace` (pull request 7, not merged). **They remain in that history and in GitHub's
pull-request refs until the owner decides otherwise.** Adding sanitized copies on top does not remove them.
Nothing was rewritten, force-pushed or deleted. `main` (pull requests 5 and 6) contains none of this.

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
- `verify-evidence.py` runs 29 checks on the public copies: the A1 build hashes (three outputs identical, the
  image different), the device-tree seed cause, the `add-payload` determinism, the loader defect numbers, the
  `cargo deny` results and the advisory path, the tool and compiler versions, the A3 boot results under HVF and
  TCG, the ID-register probe (ASIDBits 2 under TCG, 0 under HVF), the pins, the manifest hashes, and that no
  home path, user name, host name or scratch path remains.

## Limits

- A sanitized log is not byte-identical to the raw one. Lines that held a path differ, and their text is
  otherwise the same. QEMU serial logs also change from CRLF to LF line endings, which is what Git stores. Hashes of build artefacts inside the logs are untouched.
- Someone without the raw logs cannot confirm the omitted Homebrew formulae. The recorded hash and the drift
  summary let the owner do so.
- The sanitizer reads the user, home and host names from the machine it runs on. Run it on the machine that
  holds the raw logs.
