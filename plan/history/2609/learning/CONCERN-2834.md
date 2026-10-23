---
source: CONCERN-2834
timestamp: '2026-09-03T18:11:13.047779+00:00'
title: G06 lifecycle state representation
type: learning
---

Planning group **G06 — lifecycle state representation** (umbrella #2834, parent
epic #2828). Docs PR: <https://github.com/CERTCC/Vultron/pull/3136>

## Outcome

Three live members were resolved as recorded decisions (spec + notes; no ADR —
the two representation verdicts are "keep as-is" and the close rule is a spec
MUST). Three members (#2665, #3008, #3009) had already been planned/closed in
prior sessions (AC-3 and most of AC-6).

### Per-member disposition

- **#2099 — CS representation.** Verdict: **keep the compound `CS` enum**. It is
  already `CompoundState(CS_vfd, CS_pxa)`; new `vultron/core/` code consumes the
  split sub-machine enums; the monolithic `CS` is retained for the legacy
  `vultron/bt/` simulator. No `CaseState(BaseModel)` (ADR-0036 dimension objects
  already decompose status). Recorded in `notes/case-state-model.md`. Follow-on:
  retire the resolved `cs.py` TODO → Task #3138 under #2684.
- **#1912 — transition constructors.** Verdict: **no change; retain the
  field-mutation write path.** ADR-0033 rejected constructors as a second write
  path and set the reopen bar at ≥2 field-mutation error classes found in a
  migration audit; the staged types exist (`staged_case.py`) but no such error
  evidence surfaced, so the bar is unmet. Recorded in
  `notes/lifecycle-staged-types.md`. No Task.
- **#2955 — owner-close with an active embargo.** Verdict: **Option A — the Case
  Actor MUST decline the owner close while an embargo is live**, via `as:Reject`
  ("understood but declined", MSM-05-001). Declining does NOT terminate the
  embargo; the owner must terminate-then-close. Codified as **CM-23-011**
  (`specs/case-management.yaml`), the terminal/case-global strengthening of the
  participant-scoped VP-13-005 / VP-13-009; rationale in
  `notes/embargo-lifecycle.md`. Follow-on: enforce CM-23-011 → Task #3137 under
  #2684. Option B (atomic teardown on close) was rejected as it buries a
  significant protocol event inside the close path.

### Already resolved before this session

- **#2665** (VFD split granularity) — AC-3.
- **#3008 / #3009** (enforcement gaps; `composite_state_violations` rename) — AC-6.

## Implementation issues

- #3137 — enforce CM-23-011 (decline owner-close while embargo live) → #2684
- #3138 — retire resolved CS-representation TODO in cs.py → #2684

Members close on merge of PR #3136 (Closes #2834/#2099/#1912/#2955).
