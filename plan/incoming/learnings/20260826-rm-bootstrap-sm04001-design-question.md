---
title: "SM-04-001 guard: bootstrap-forward exemption for START and RECEIVED"
type: learning
timestamp: "2026-08-26"
source: ISSUE-2481
signal: design-question
---

When adding the SM-04-001 precondition guard to `_upgrade_participant_to_accepted()`,
a design decision was required: `is_valid_rm_transition(RM.START, RM.ACCEPTED)` and
`is_valid_rm_transition(RM.RECEIVED, RM.ACCEPTED)` both return `False` because the
function checks strict adjacency in the `_transitions` list. Applying the guard naively
would break the CBT-05-007 bootstrap invariant ("Bootstrap Create upgrades an existing
RM.START participant to RM.ACCEPTED").

**Decision**: treat `RM.START` and `RM.RECEIVED` as explicit bootstrap-forward exemptions
in the guard condition. These states mean "not yet triaged" — the reporter has implicitly
accepted by submitting the report, so jumping forward to `RM.ACCEPTED` is semantically
correct. `RM.INVALID` is excluded because it means "validation failed" — that branch
requires an explicit re-validation step before acceptance.

**Guard pattern**:

```python
if not is_valid_rm_transition(latest_rm, RM.ACCEPTED) and latest_rm not in (
    RM.START,
    RM.RECEIVED,
):
    # block and warn
    return
```

This pattern should be applied consistently to any future SM-04-001 guard that must
permit bootstrap forward jumps while blocking invalid-state bypasses.
