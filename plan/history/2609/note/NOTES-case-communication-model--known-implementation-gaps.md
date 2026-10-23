---
source: NOTES-case-communication-model--known-implementation-gaps
timestamp: '2026-09-17T17:10:51.627613+00:00'
title: Known Implementation Gaps (case communication)
type: note
---

**Archived:** 2026-09-17
**Reason:** (a) all three gaps resolved: note.py routes to CASE_MANAGER; triggers/embargo.py and triggers/case.py removed
**Superseded by:** vultron/core/use_cases/triggers/note.py:74

---

## Known Implementation Gaps

| Gap | Location | Status |
|---|---|---|
| Notes trigger sends to all participants | `triggers/note.py:102` | Open |
| Embargo triggers send to all participants | `triggers/embargo.py` | Open |
| Engage/defer-case triggers send to all participants | `triggers/case.py:84,132` | Open |
