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

**Expected**: Update `em_state` on the current `CaseStatus` object.
For example: `self.case_status[0].em_state = EM.ACTIVE` (or a helper that
returns the current `CaseStatus`).

**Impact**: BT-5 embargo handlers will fail when calling `case.set_embargo()`.
Fix before implementing BT-5 embargo handlers.

**Priority**: HIGH — blocks BT-5 implementation.

---

