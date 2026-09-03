---
title: "AC-3 compound-transition check runs on REQUESTED state, before AC-1 promotion"
type: learning
timestamp: "2026-08-31T00:00:00Z"
source: ISSUE-2479
signal: spec-ambiguity
---

Issue #2479 AC-3 said to validate compound transitions with `is_valid_cs_transition()`, but was
silent on whether the validation uses the requested value or the post-promotion (AC-1) value.

**Interpretation adopted**: validate the REQUESTED compound state first (before promotion), then
apply AC-1 promotion to the value that gets written. Rationale: the transition `pxa → pXa` (X
fires) must be structurally valid before the system promotes `pXa → PXa`. If we promoted first,
`pxa → PXa` would look like a 2-dimension simultaneous jump and be rejected incorrectly.

This ordering is tested explicitly by `test_ephemeral_pXa_promoted_before_write`.

---

**Archived**: 2026-09-03 — already captured. Validating the ephemeral/requested compound state before promotion-to-forced-form-for-storage is the two-boundary model in `specs/cs-behavior.yaml` CSB-17-003 (refines SM-09-001) — the pX→PX case this entry describes. No new promotion needed.
