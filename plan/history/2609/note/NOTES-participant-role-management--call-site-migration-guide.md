---
source: NOTES-participant-role-management--call-site-migration-guide
timestamp: '2026-09-17T17:32:54.430184+00:00'
title: Call-Site Migration Guide
type: note
---

**Archived:** 2026-09-17
**Reason:** (a) delivered
**Superseded by:** action_rules.py migrated to roles API (PR #1443)

---

## Call-Site Migration Guide

### `action_rules.py`

Current code:

```python
roles = [r.value for r in (participant.case_roles or [])]
```

Updated code:

```python
roles = [r.value for r in participant.roles]
```

The `roles` property always returns a list (never `None`), so the `or []`
guard can be dropped.

---
