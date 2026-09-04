---
title: "AC-1 promotions extracted to _apply_ac1_promotions() to stay under C901 limit"
type: learning
timestamp: "2026-08-31T00:00:00Z"
source: ISSUE-2479
signal: design-question
---

Adding AC-1 pX/vP promotion logic inline in `CreateParticipantStatusNode.update()` pushed McCabe
complexity to 14 (limit: 12, C901). Extracted the 4-branch promotion block into
`_apply_ac1_promotions(eff_vf, eff_pxa)` helper returning `(CS_vf | None, CS_pxa)`.

This keeps `update()` under the limit and makes the promotion logic independently testable.
The oversize backlog entry for `status.py` (525 lines) notes that `_check_compound_transition()`
is a natural candidate for a future `_compound_guards.py` submodule.

## Audit disposition (2026-09-02)

Closed decision, no promotion owed (BW-07-008). The decision was made, applied, and shipped in its originating PR; the commit and PR body are its record. Archived without promotion.
