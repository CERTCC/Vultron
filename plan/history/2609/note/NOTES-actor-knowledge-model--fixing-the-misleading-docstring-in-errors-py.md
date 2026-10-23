---
source: NOTES-actor-knowledge-model--fixing-the-misleading-docstring-in-errors-py
timestamp: '2026-09-17T17:08:14.870932+00:00'
title: Fixing the Misleading Docstring in errors.py
type: note
---

**Archived:** 2026-09-17
**Reason:** (a) docstring already corrected
**Superseded by:** vultron/errors.py:146

---

## Fixing the Misleading Docstring in `errors.py`

`VultronOutboxObjectIntegrityError` previously had this docstring:

```python
# ❌ OLD (misleading)
"""...so that recipients can determine the semantic type without a round-trip
to the sender's DataLayer."""
```

The phrase "without a round-trip" implies DataLayer access is *possible* but
*avoided for efficiency*. This is incorrect.

The corrected version (see commit):

```python
# ✅ NEW (accurate)
"""...because the recipient has no access to the sender's DataLayer."""
```

---
