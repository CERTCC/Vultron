---
source: CONCERN-2535
timestamp: '2026-09-24T14:34:52.008105+00:00'
title: 'A priority gate must name a tier: MUST_NOT needs verification like MUST'
type: learning
---

Docs PR: <https://github.com/CERTCC/Vultron/pull/3615> (planned under umbrella #2840)

Concern: `MUST_WITHOUT_VERIFICATION` was MUST-only. The pinning test
`test_lint_must_not_without_verification_no_warn` came from #2466's AC wording,
not from any decision.

Resolution: MUST_NOT is the same tier as MUST.

- MS-02-003 makes the negative keyword the same tier, and MS-02-004 requires one
  shared `RFC2119Priority` tier definition.
  `backstop/_model.py` already hand-codes it.
- MS-10-003 now covers MUST_NOT.
- The same principle extends SR-11-004 to SHOULD_NOT.

Lesson: when a rule selects on priority, gate on the tier, not the literal
keyword. When a ratchet is introduced, give it an owner and a terminal state
(zero, then hard error), not only a guarantee that it never rises. Recorded in
`notes/spec-authoring-rules.md`.

The code change is #3522. The backfills are #3612, #2569, #2571, #2573, #2574
and #2575.
