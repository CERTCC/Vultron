---
source: NOTES-case-state-model--case-lifecycle-stages-caterpillar-butterfly
timestamp: '2026-10-12T19:32:58.154635+00:00'
title: 'Case Lifecycle Stages: Caterpillar / Butterfly (RM-state framing)'
type: note
---

**Archived:** 2026-10-12
**Reason:** vocabulary metaphor, not a rule; its superseded-lifecycle notice is history
**Superseded by:** ADR-0041; notes/case-proposal.md

---

## Case Lifecycle Stages: Caterpillar / Butterfly (RM-state framing)

A durable metaphor for the RM-state progression of a case:

- **Caterpillar** = `RM.RECEIVED` or `RM.INVALID` — the case/work exists but has
  not yet been validated.
- **Butterfly** = `RM.VALID`, `RM.ACCEPTED`, or `RM.DEFERRED` — validated and
  actionable.
- **Terminal** = `RM.CLOSED` (regardless of path).

Work genuinely happens in both stages, and participants exist in both.

> Note: the earlier "Implemented Lifecycle (per ADR-0015)" description — which
> created a `VulnerabilityCase` at report receipt — is superseded by ADR-0041
> (the receiver holds no interim `VulnerabilityCase`). See
> [notes/case-proposal.md](case-proposal.md) and
> [notes/case-bootstrap-trust.md](case-bootstrap-trust.md) § "ADR-0041 Update".
