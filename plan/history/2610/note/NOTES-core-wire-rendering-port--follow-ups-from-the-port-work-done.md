---
source: NOTES-core-wire-rendering-port--follow-ups-from-the-port-work-done
timestamp: '2026-10-02T16:20:18.394508+00:00'
title: Follow-ups from the port work (done)
type: note
---

**Archived:** 2026-10-02
**Reason:** delivered — every follow-up listed is done; #1991 and #2940 closed
**Superseded by:** ADR-0099 detail 2; ARCH-12-003; ARCH-20-005

---

## Follow-ups from the port work (done)

- `test_no_core_object_has_to_camel_alias_generator` and its `xfail` are gone:
  ADR-0099 detail 2 reversed the premise, and every `CoreObject` now inherits
  `alias_generator=to_camel` on purpose. #1991 is closed.
- `CaseParticipant._reject_wire_spelled_keys` and its known-deviation
  docstring were deleted in #2940; `extra="forbid"` on `CoreObject` is the
  guard (ARCH-12-003).
- `CoreActor.to_json()` is gone, so core offers no bypass of the port seam
  (ARCH-20-005).
- The six core actor classes register in `CORE_VOCABULARY` only; no core
  docstring claims a `VOCABULARY["Person"]` entry.
- `_NORMALIZE_WIRE_TO_CORE` in `db_record.py` has been deleted, as ADR-0082
  planned once `extra="forbid"` landed.
