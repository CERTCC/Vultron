---
source: NOTES-actor-knowledge-model--detecting-violations-audit-checklist
timestamp: '2026-10-12T20:11:15.720682+00:00'
title: 'Detecting Violations: Audit Checklist'
type: note
---

**Archived:** 2026-10-12
**Reason:** audit checklist duplicated the inline-object rule; the outbox guard enforces it
**Superseded by:** vultron/adapters/driven/outbox_delivery.py (VultronOutboxObjectIntegrityError)

---

## Detecting Violations: Audit Checklist

When auditing for AKM violations, search for these patterns:

1. **`object_=<model>.id_`** — check any `.id_` assignment to an `object_`
   field in activity construction:

   ```bash
   grep -rn "object_=.*\.id_" vultron/ --include="*.py"
   ```

2. **`target=<model>.id_`** — similar pattern for `target` fields:

   ```bash
   grep -rn "target=.*\.id_" vultron/ --include="*.py"
   ```

3. **`actor=.*\.id_`** — `actor` is generally an ID reference (correct), but
   confirm it is the *sender's own* ID, not a reference to a third-party object:

   ```bash
   grep -rn "actor=.*\.id_" vultron/ --include="*.py"
   ```

4. **String-typed `object_` in demo scripts** — demos may build activities
   using dict literals; check that `"object"` values are serialized full
   objects, not bare IDs:

   ```bash
   grep -rn '"object".*:.*id_\|"object".*id_' vultron/demo/ --include="*.py"
   ```

5. **`outbox_handler` expansion path** — any `logger.warning(... "bare string
   object_"...)` in the outbox handler indicates an AKM violation at runtime.
   These log lines are the smoke signal.

---
