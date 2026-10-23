---
source: NOTES-embargo-lifecycle--anti-pattern-inline-emadapter
timestamp: '2026-09-17T17:22:58.779634+00:00'
title: 'Anti-Pattern: Inline EMAdapter Instantiation in Use Cases'
type: note
---

**Archived:** 2026-09-17
**Reason:** (a,b) EMAdapter gone from use_cases/; rule in Guidance section + EMB-18-001/002
**Superseded by:** specs/embargo-policy.yaml EMB-18; notes/embargo-lifecycle.md § Guidance for Agents

---

## Anti-Pattern: Inline `EMAdapter` Instantiation in Use Cases

**Do not** instantiate `create_em_machine()` + `EMAdapter` inline inside
trigger or received use-case `execute()` methods. Example of the anti-pattern:

```python
# ❌ WRONG: inline EM machine in execute()
adapter = EMAdapter(em_state)
em_machine = create_em_machine()
em_machine.add_model(adapter, initial=em_state)
try:
    getattr(adapter, "accept")()
except MachineError:
    ...
new_em_state = EM(adapter.state)
```

This pattern appears repeatedly across `triggers/embargo.py` and
`received/embargo.py`. Each repetition is an independent copy of the
transition logic with no shared validation or invariant enforcement.

**Why this is risky:**

- A bug fix or rule change requires updating N copies instead of one.
- The transition validity rules are not documented or enforced by type — a
  typo in the trigger name (e.g., `"accept"` vs `"activate"`) fails silently
  at runtime.
- PEC cascade operations (`_cascade_pec_revise`, `_cascade_pec_reset`) are
  co-located with the EM machine setup but are not guaranteed to run whenever
  the EM state changes.

---
