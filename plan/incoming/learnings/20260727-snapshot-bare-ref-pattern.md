---
title: "Snapshot bare-ref pattern (_drop_bare_inline_refs) must be applied to all model_dump() payloads"
type: learning
timestamp: 2026-07-27T00:00:00Z
source: ISSUE-1689
signal: design-question
---

`_validate_canonical_entry` rejects any `object`, `object_`, or `target` field
whose value is a bare ID string rather than an inline object dict. Factory
methods (e.g. `add_participant_to_case`) serialize `target=case_id` as a
bare URI string in the activity dict.

The canonical pattern for building a payloadSnapshot from a stored activity is:

```python
raw = stored.model_dump(mode="json", by_alias=True, serialize_as_any=True, exclude_none=True)
snapshot = _snapshot_with_context(raw, case_id)
```

`_snapshot_with_context` calls `_drop_bare_inline_refs` (strips bare strings
from `object`, `object_`, `target` keys recursively) and sets `context=case_id`.

Code review for #1689 caught one place (`EmitAddCaseParticipantNode._build_snapshot`)
that used raw `model_dump` without this step — fixed before PR opened.

This pattern should be documented as a project convention and enforced via
an architecture lint or spec entry so future ledger emit nodes don't repeat
the mistake.

**Promoted**: 2026-07-28 — already in notes/case-ledger-authority.md § snapshot-bare-ref pattern.
Docs PR: TBD.
