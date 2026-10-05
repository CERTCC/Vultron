---
source: NOTES-structured-logging--discover-actors-trim-to-id-only
timestamp: '2026-10-02T16:28:29.962289+00:00'
title: '`discover_actors()` — trim to ID only'
type: note
---

**Archived:** 2026-10-02
**Reason:** delivered — discover_actors() logs IDs only via_log_discovered_actor
**Superseded by:** vultron/demo/utils.py

---

## `discover_actors()` — trim to ID only

```python
# Before
logger.info(f"Found finder actor: {logfmt(finder)}")
# After
logger.info("Found finder actor: %s", finder.get("id", "<unknown>"))
```

Full `logfmt()` actor object output belongs at DEBUG; only the actor ID is
meaningful at INFO. The "after" form is also the SL-01-005 shape: a literal
template with the value as a lazy argument.

---
