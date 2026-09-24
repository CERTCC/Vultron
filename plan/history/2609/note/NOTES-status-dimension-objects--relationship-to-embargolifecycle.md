---
source: NOTES-status-dimension-objects--relationship-to-embargolifecycle
timestamp: '2026-09-17T17:32:55.247492+00:00'
title: Relationship to EmbargoLifecycle
type: note
---

**Archived:** 2026-09-17
**Reason:** (a) delivered
**Superseded by:** dimension-object migration shipped

---

## Relationship to EmbargoLifecycle

`EmbargoLifecycle` currently mutates `em_state` and `em_consent_state` fields
directly on `CaseStatus`/`ParticipantStatus`. After this migration, it MUST
use the dimension-object transition pattern:

```python
# Before
case_status.em_state = new_em_state

# After
updated_em = EmDimension(state=new_em_state)
# ... or via transition():
updated_em = case_status.em.transition(EM_Trigger.ACTIVATE)
case_status = case_status.model_copy(update={"em": updated_em})
```

This is the single most complex migration site (`embargo_lifecycle.py` has
~17 flat-field accesses). The impl agent should prioritize this file.

---
