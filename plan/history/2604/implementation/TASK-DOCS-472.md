---
title: TASK-DOCS-472 — Fix LaTeX Rendering and Versioning Docs
type: implementation
date: 2026-04-30
source: TASK-DOCS-472
---

# TASK-DOCS-472: Fix LaTeX Rendering and Versioning Docs

## Summary

Fixed LaTeX rendering issues across multiple documentation pages and updated
the versioning documentation to accurately describe the CalVer scheme.

## Changes Made

### LaTeX `\label{}` removal (10 occurrences in 4 files)

Removed all `\label{...}` commands from math environments across the
documentation. The MathJax 3 configuration does not include `tags: 'ams'`,
so `\label{}` commands have no effect and can cause silent rendering
failures in some MathJax versions.

Files fixed:

- `docs/reference/ssvc_crosswalk.md` (5 labels: lines 22, 37, 78, 267, 276)
- `docs/reference/formal_protocol/index.md` (1 label: line 23)
- `docs/topics/measuring_cvd/reasoning_over_histories.md` (1 label: line 25)
- `docs/topics/process_models/em/defaults.md` (3 labels: lines 264, 274, 298)

### Indentation fix in ssvc_crosswalk.md

Fixed 8-space indented `$$` block inside an admonition (line 194). In
Python-Markdown, admonition content requires 4 spaces of indent; 8 spaces
creates a literal code block instead of a math block. Fixed by reducing
to 4 spaces with `$$` on its own line.

### Block-math delimiter fix in conclusion.md

The opening `$$` delimiter was fused directly to the LaTeX content
(`$${protocol}_{MPCVD} =`), and the closing `$$` was similarly fused to the
last content line. Fixed by putting both delimiters on their own lines inside
the admonition block (see also P472-LATEX.md). Directly resolves issues #234
and #235 in addition to the indirect `\label{}` fix.

### versioning.md rewrite

Replaced the SemVer description with an accurate CalVer description per
ADR 0006. The page now documents the `YYYY.M.Patch` scheme correctly,
with examples of significant vs. patch releases.

## Validation

- `uv run mkdocs build --strict`: 0 real warnings (13 known false positives
  suppressed by `.github/scripts/mkdocs-build-strict.sh`)
- markdownlint-cli2: 0 errors across all 5 changed files
- No remaining `\label{` occurrences in `docs/`
- No `<pre><code>$$` blocks in rendered HTML (confirmed via site/ inspection)

## Related Issues

Closes GitHub issues #154, #186, #234, #235, #271 (sub-issues of #404).
