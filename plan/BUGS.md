# Bugs to fix

Items in this file supersede IMPLEMENTATION_PLAN.md.

---

## BUG: `VulnerabilityCase.set_embargo()` does not update `em_state`

**File**: `vultron/as_vocab/objects/vulnerability_case.py`, line 100

**Description**: `set_embargo()` does `self.case_status.em_state = EM.ACTIVE`,
but `case_status` is `list[CaseStatusRef]` — setting an attribute on a list
silently no-ops (Python allows arbitrary attribute assignment to list
subclasses... actually no, it raises `AttributeError` at runtime because
`list` does not allow arbitrary attribute assignment).

**Design Notes**: the `case_status` field is intended to be an append-only 
list of `CaseStatus` objects that represent the history of status changes to 
the case. The most recent `case_status` is the one with the latest updated 
timestamp. Items may arrive out of order, so sorting
by timestamp is necessary to determine the current status. It is an error for
updates to arrive from the future.

**Expected**: Update `em_state` on the current `CaseStatus` object.
For example: `self.case_status[0].em_state = EM.ACTIVE` (or a helper that
returns the current `CaseStatus`).

**Impact**: BT-5 embargo handlers will fail when calling `case.set_embargo()`.
Fix before implementing BT-5 embargo handlers.

**Priority**: HIGH — blocks BT-5 implementation.

---

