---
title: Lint gate surfaced pre-existing MV-09-001 phantom beyond issue scope
type: learning
timestamp: 2026-08-25T00:00:00Z
source: ISSUE-2468
signal: design-question
---

While implementing the new `_check_phantom_spec_id_citations` lint gate for
ISSUE-2468 (which listed 11 specific phantom IDs), the gate immediately surfaced a
12th phantom — `MV-09-001` — cited in 11 production and test files across
`vultron/errors.py`, outbox adapters, use cases, and wire tests.

**Decision made:** Wrote `MV-09-001` as a real spec in `specs/message-validation.yaml`
(filling the genuine gap in the MV-09 group that already had 002 and 003) rather
than filing a follow-up issue. Rationale: the gate would have blocked CI immediately,
the behavior is real and protocol-visible (outbound activities MUST carry a fully
inline typed object), and writing the spec took less time than filing and triaging
a new bug.

**Takeaway:** When adding a new lint gate, run it against the live codebase before
committing and fix any pre-existing violations in the same PR — a gate that
immediately fails CI on merge is not useful.
