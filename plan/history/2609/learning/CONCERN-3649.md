---
source: CONCERN-3649
timestamp: '2026-09-25T13:45:21.047003+00:00'
title: metadata fence detection misses admonition-indented fences
type: learning
---

## Problem

`vultron/metadata/markdown_tables.py`'s `_FENCE_RE` (`^ {0,3}` followed by a fence run) follows CommonMark, which reads a fence indented four or more spaces as indented code. In `docs/`, though, mkdocs-material nests a fenced block inside an admonition or content tab at four spaces. 24 `docs/` files do this; for example, `docs/topics/case_lifecycle/ownership_transfer.md:165`.

For those blocks, `iter_sections` and `iter_tables` treat the fenced content as live Markdown:

- a `#` comment inside the block is read as a heading;
- a pipe table inside the block is read as a real table.

That is the hazard the module docstring says it absorbs.

`vultron/metadata/docs/landing_pages.py` also carries its own separate `_FENCE_RE = r"^\s*(```|~~~)"`. That copy ignores run length and fence character, so a shorter run inside a longer fence closes the block.

## Context

PR #3648 (issue #3529) added `fenced_lines(text, *, nested=False)` to `markdown_tables` and used `nested=True` for the level-order prose scan. It did not change the default, because every existing caller parses plain `specs/`, `notes/` and glossary Markdown where the CommonMark reading may be the intended one.

## Suggested resolution

- Decide per caller whether the input is mkdocs-rendered (then pass `nested=True`) or plain CommonMark.
- Replace `landing_pages._FENCE_RE` with `fenced_lines` (CS-22-001).
- Add a regression test with a table inside an indented admonition fence.

Governing specs: CS-22-001 (DRY); MS-17 is unaffected.

**Resolved**: 2026-09-25 — implementation tracked in #3685.

Decision: one fence rule, tracked at any indentation, rather than a per-caller
`nested` switch. The strict CommonMark reading also misses fences in nested list
items. The only case it gets right, an indented code block whose content starts
with three backticks, does not occur in the repository. Measured on `origin/main`:
only `docs/` files have fences indented four or more spaces, and the nested reading
changes no table or heading any current caller sees. So the defect is latent, not
live.
