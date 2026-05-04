---
title: "Fix block-math opening delimiter in conclusion.md (#234, #235)"
type: implementation
timestamp: '2026-04-30T14:16:11+00:00'

source: P472-LATEX
type: implementation
---

The opening `$$` delimiter in `docs/reference/formal_protocol/conclusion.md`
was fused directly to the LaTeX content (`$${protocol}_{MPCVD} =`), and the
closing `$$` was similarly fused to the last content line. This is non-canonical
for pymdownx.arithmatex `generic: true`.

Fixed by putting both the opening and closing `$$` on their own lines inside the
`!!! note "Formal Protocol Definition"` admonition block. `transitions.md` was
examined and found clean — all its `$$...$$` blocks are single-line with delimiters
already separated from content.

Docs build produces the same 13 pre-existing warnings (plugin ordering + citation
keys) and no new errors after the fix. Issues #234 and #235 are now directly
addressed in addition to the indirect `\label{}` fix from commit `2c116d57`.
