---
source: ISSUE-702
timestamp: '2026-06-03T20:48:57.014921+00:00'
title: Split semantic_registry.py into domain-split package
type: implementation
---

## Issue #702 — Refactor semantic_registry into domain-split package

Replaced the 783-line `vultron/semantic_registry.py` with a package under
`vultron/semantic_registry/` split into nine domain sub-modules:

| Module | Entries | Domain |
|---|---|---|
| `report.py` | 6 | Report lifecycle |
| `case.py` | 5 | Case lifecycle (open/update/engage/defer/add-report) |
| `actor.py` | 13 | Actor/role negotiation |
| `embargo.py` | 7 | Embargo lifecycle |
| `sync.py` | 3 | Case close + case-log sync |
| `case_participant.py` | 3 | Case participant management |
| `note.py` | 3 | Note management |
| `status.py` | 4 | Case/participant status |
| `unknown.py` | 2 | Fallback sentinels (UNKNOWN last) |

The assembly order in `__init__.py` preserves the exact original dispatch
sequence (46 entries). All public API symbols are re-exported from
`__init__` for zero-change caller compatibility. The architecture boundary
test was updated to allow imports from the new package directory.

Documentation updated: `notes/semantic-registry.md`, `notes/README.md`,
`docs/reference/two-actor-demo-protocol.md`,
`docs/reference/codebase/CONCERNS.md`.

2615 passed, 12 skipped — no regressions.

PR: <https://github.com/CERTCC/Vultron/pull/732>
