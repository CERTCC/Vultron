---
title: "DOCS-2 \u2014 Fix broken inline code examples in `docs/` (2026-03-18)"
type: implementation
date: '2026-03-18'
source: DOCS-2
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 2143
legacy_heading: "DOCS-2 \u2014 Fix broken inline code examples in `docs/`\
  \ (2026-03-18)"
date_source: git-blame
legacy_heading_dates:
- '2026-03-18'
---

## DOCS-2 — Fix broken inline code examples in `docs/` (2026-03-18)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:2143`
**Canonical date**: 2026-03-18 (git blame)
**Legacy heading**

```text
DOCS-2 — Fix broken inline code examples in `docs/` (2026-03-18)
```

**Legacy heading dates**: 2026-03-18

Updated `docs/reference/code/as_vocab/*.md` to replace all `vultron.as_vocab.*`
autodoc directives with the correct `vultron.wire.as2.vocab.*` paths that were
introduced in P60-1. Affected files: `index.md`, `as_base.md`, `as_activities.md`,
`as_links.md`, `as_objects.md`, `v_activities.md`, `v_objects.md`.

`mkdocs build` succeeds with no module-not-found errors in
`docs/reference/code/as_vocab/`.

### Test results

982 passed, 5581 subtests (unchanged from baseline).
