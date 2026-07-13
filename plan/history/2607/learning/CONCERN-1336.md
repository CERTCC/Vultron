---
source: CONCERN-1336
timestamp: '2026-07-13T19:56:13.912484+00:00'
title: _read_suggested_roles() silently substitutes default for intentional empty
  role list
type: learning
---

`EmitOfferCaseParticipantToOwnerNode._read_suggested_roles()` uses the guard
`if isinstance(roles, list) and roles:` — treating an empty list as "absent"
and substituting `[CVDRole.VENDOR]`. This is safe for the current prototype
where `EvaluateDefaultRolesNode` always writes a non-empty list (CM-16-003
requires `suggested_roles` to be non-empty), but creates a silent override
hazard for future Evaluator implementations.

**Risk scenario**: A future Evaluator evaluates that no default role can be
determined and intentionally writes `suggested_roles = []` to signal "caller
should prompt the Case Owner for roles rather than pre-populating." The
substitution fallback would silently override this signal with
`[CVDRole.VENDOR]`, defeating the intended semantics.

**Resolution**: Option 1 — enforce non-empty at write time in
`EvaluateDefaultRolesNode` (returns FAILURE if computed list is empty) per
ADR-0032/BT-HELPER-01. CM-16-003 spec amended to clarify MUST (non-empty
list), SHOULD (use VENDOR), MAY (use OTHER for unclassifiable actors).

**Resolved**: 2026-07-13 — implementation tracked in #1383.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1382>.
Spec: `specs/case-management.yaml` CM-16-003.
