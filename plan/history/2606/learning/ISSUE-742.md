---
source: ISSUE-742
timestamp: '2026-06-11T18:35:53.654939+00:00'
title: Subpackage splits must preserve import surfaces for use-case classes and request
  models
type: learning
---

## 2026-06-09 ISSUE-742 — Subpackage splits should preserve import surfaces explicitly

- When replacing a flat use-case module with a subpackage, add explicit
  `__init__.py` re-exports for both use-case classes and any request models
  callers previously imported transitively from the old module.
- Mirror the source split in test layout with a matching subdirectory to keep
  file organization aligned and reduce future merge-conflict hotspots.

**Promoted**: 2026-06-11 — captured in `AGENTS.md` pitfall "Use-Case
Subpackage Splits Must Re-Export Both Classes and Request Models".
Docs PR: <https://github.com/CERTCC/Vultron/pull/900>.
