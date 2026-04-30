---
title: Priority 472 — Docs Batch (LaTeX Fixes and Versioning Updates)
type: priority
date: 2026-04-30
source: Priority 472
---

## Priority 472 — Docs Batch: LaTeX Fixes and Versioning Updates

**Issues closed**: #154, #186, #234, #235, #271, #404, #386

### Docs batch (#404)

Fixed in commit `2c116d57`:

- **#154** — `docs/topics/background/versioning.md` rewritten to describe
  CalVer (YYYY.M.Patch); all SemVer references removed.
- **#186 / #271** — `ssvc_crosswalk.md`: removed `\label{}` commands and fixed
  an 8-space-indented `pva` equation that was rendering as a `<pre><code>` block.
- **#234 / #235** — `conclusion.md` / `transitions.md`: LaTeX rendering issues
  were linked to `\label{}` in `formal_protocol/index.md`; fixing that file
  (part of the same MathJax document context) resolved rendering on the
  conclusion and transitions pages indirectly.
- Repo-wide `\label{}` sweep also fixed `reasoning_over_histories.md` and
  `em/defaults.md`.

**Note**: `conclusion.md` and `transitions.md` were not directly modified.
If LaTeX rendering issues resurface on those pages, they should be
investigated independently.

### BUG-386 (#386)

Resolved by prior work in commit `62cdc48e` ("Fix invite response parsing and
reply links"). The parser now embeds the inline typed object in `Accept`/`Reject`
activities, eliminating the unresolvable-URI dead-letter scenario for
spec-compliant senders.
