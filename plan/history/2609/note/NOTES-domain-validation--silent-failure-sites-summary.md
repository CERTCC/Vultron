---
source: NOTES-domain-validation--silent-failure-sites-summary
timestamp: '2026-09-17T17:22:57.692671+00:00'
title: Summary of Named Silent-Failure Sites (CONCERN-1360)
type: note
---

**Archived:** 2026-09-17
**Reason:** (a,b,c) CONCERN-1360 closed; fixes delivered; normative in ARCH-15-001..004
**Superseded by:** specs/architecture.yaml ARCH-15-001..004

---

## Summary of Named Silent-Failure Sites (CONCERN-1360)

| Site | Old behavior | New behavior |
|---|---|---|
| `_as_id()` in `embargo_lifecycle.py` | Duplicate copy | Removed; moved to `core.models._helpers` (#1428) |
| `_find_case_manager_*` (3 copies) | 3 independent copies returning `None` | 1 canonical function in `use_cases/_helpers`; others removed |
| `_extract_case_id()` in dispatcher | Returns `None`; activity silently not indexed | Raises `UnroutableActivityError` |
| `CommitCaseLedgerEntryNode.update()` | Returns `Status.SUCCESS` on missing `case_id` | Returns `Status.FAILURE` |
| `_read_case_obj()` in communication.py | Swallows `KeyError`; no diagnostic | Sets `feedback_message`; caller returns `Status.FAILURE` |

See `specs/architecture.yaml` ARCH-15-001 through ARCH-15-004 for
normative requirements derived from this concern.

---
