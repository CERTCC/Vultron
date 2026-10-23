---
title: "SPEC-AUDIT-2 \u2014 RFC 2119 strength keyword migration (2026-03-30)"
type: implementation
timestamp: '2026-03-31T00:00:00+00:00'
source: SPEC-AUDIT-2
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 3737
legacy_heading: "SPEC-AUDIT-2 \u2014 RFC 2119 strength keyword migration (2026-03-30)"
date_source: git-blame
legacy_heading_dates:
- '2026-03-30'
---

## SPEC-AUDIT-2 — RFC 2119 strength keyword migration (2026-03-30)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:3737`
**Canonical date**: 2026-03-31 (git blame)
**Legacy heading**

```text
SPEC-AUDIT-2 — RFC 2119 strength keyword migration (2026-03-30)
```

**Legacy heading dates**: 2026-03-30

**Task**: Ensure every requirement line in `specs/` has an RFC 2119 keyword
on its first line, and remove keyword suffixes from section headers.

**Changes**:

- **176 keyword additions**: Requirement lines missing a keyword on the first
  line (keyword was on a wrapped continuation line, absent, or only in the
  section header) now have the keyword inserted immediately after the ID.
  Prefix-style keywords are parenthesised: `` `ID` (MUST) text ``.
  Naturally-embedded keywords (e.g. `All handlers MUST ...`) are left as-is.
- **293 header cleanups**: `## Section (MUST)` / `(SHOULD)` / `(MAY)` etc.
  suffixes removed from all `##` and `###` headers across 37 spec files.
  Removing headers that had identical base names (e.g. two `## Embargo Rules`
  sections previously separated by `(MUST)`/`(SHOULD)`) also resulted in
  31 duplicate-header merges in `vultron-protocol-spec.md` and `code-style.md`.
- **171 format fixes**: A second pass converted bare prefix keywords
  (`MUST text`) to the parenthesised form (`(MUST) text`) for visual
  clarity and to distinguish them from sentence-embedded keywords.

**Verification**:

- ``grep -rn "^\- `[A-Z]" specs/*.md | grep -v "MUST\|SHOULD\|..." → 0 hits``
- `grep -rh "^## \|^### " specs/*.md | grep "(MUST)\|(SHOULD)\|(MAY)"` → 0 hits
- `markdownlint-cli2`: 0 errors

**Tests**: 1080 passed, 5581 subtests (no code changes; docs only).
