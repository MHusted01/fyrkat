---
name: new-adr
description: Draft a new architecture decision record as Proposed from the project template. Use when a decision is expensive to reverse or constrains other components.
argument-hint: "[short title]"
---

Draft ADR "$ARGUMENTS". Follow docs/adr/README.md.

1. Confirm an ADR is needed (see "When one is required" in docs/adr/README.md). Routine implementation choices do not need one.
2. Find the next free number: list `docs/adr/[0-9]*.md` and add one to the highest.
3. Copy `docs/adr/0000-template.md` to `docs/adr/NNNN-short-kebab-title.md`. Fill in every section. Write "None known" instead of deleting a section.
4. Status is **Proposed**. Never write Accepted or Provisional; only the owner does that, and a hook blocks it.
5. Label each supporting claim [Measured], [Documented], [Inferred] or [Speculative]. Do not describe undecided matters as decided.
6. Add a row to the index table in `docs/adr/README.md`.
7. Run `cargo xtask check` so the Markdown links are verified, then report the file path and open questions. Do not commit.
