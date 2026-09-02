---
title: "VFD-complete baseline required when constructing compound CS state in pX/vP guards"
type: learning
timestamp: "2026-08-31T00:00:00Z"
source: ISSUE-2524
signal: design-question
---

When wiring `required_next_cs_events()` into the ephemeral-state guard
(`CheckCsEphemeralStateNode`), the compound CS state must be constructed with a
VFD-complete baseline (`cs_from_dimensions(CS_vfd.VFD, pxa)`), not the vfd
baseline (`CS_vfd.vfd`).

With `vfd` as the VFD part, the compound state for PXA=pxa is `CS.vfdpxa`.
`required_next_cs_events(vfdpxa)` returns `{CSEvent.V}` (vP constraint), causing
false positives that block every CaseStatus when V has not been observed locally.
`CaseStatus` carries only PXA data — VFD completion is not knowable from it.

With `VFD` as the VFD part, `required_next_cs_events` only returns `{CSEvent.P}`
for pX states (`pXa`, `pXA`), which is exactly what `CaseStatus` can validate.

The same reasoning applies to `is_valid_cs_history_prefix`: using `CS.VFDpxa` as
the start state means the prefix check only validates PXA-axis ordering (P≺X),
not the full VFD×PXA ordering.

**Implementation**: `cs_from_dimensions(CS_vfd.VFD, current_pxa)` in both guard
nodes in `vultron/core/behaviors/status/nodes/cs_invariant_guards.py`.

## Audit disposition (2026-09-02)

Closed decision, no promotion owed (BW-07-008). The decision was made, applied, and shipped in its originating PR; the commit and PR body are its record. Archived without promotion.
