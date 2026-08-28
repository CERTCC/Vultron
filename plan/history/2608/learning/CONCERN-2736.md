---
source: CONCERN-2736
timestamp: '2026-08-28T15:27:10.147455+00:00'
title: Audit fallback-to-datalayer and inference-from-absence patterns
type: learning
---

## Concern

Defensive coding patterns were masking protocol failures. Specifically, bootstrap
`Create(VulnerabilityCase)` was silently synthesising a reporter participant record
from domain knowledge ("they submitted a report, therefore RM.ACCEPTED") when the
payload carried participants as bare URI strings rather than inline typed objects,
violating CBT-01-007.

## Audit Outcome

Full codebase audit found exactly two confirmed masking patterns, both in the
`_handle_bootstrap` path of `CreateCaseReceivedUseCase`:

1. **`_store_embedded_participants`** — a bare-string `continue` guard that
   silently skipped participants that arrived as URI strings (violating CBT-01-007)
2. **`EnsureReporterParticipantAtAcceptedNode` / `_ensure_reporter_participant`** —
   synthesised a reporter participant at `RM.ACCEPTED` using domain knowledge when
   the wire payload omitted the inline object

All other candidates reviewed (async replication partial views in
`participant_status_effect.py`, CaseActor reading own state, wire→core type
coercions) were confirmed false positives with documented intent.

## Resolution

Implemented CBT-05-008: receivers now raise `VultronProtocolViolationError` on
any bare-URI participant **before** any DataLayer writes (validate-before-persist —
"examine the shipment before shelving"). The two fallback artifacts were deleted.

## Learning

The "validate-before-persist" principle: bootstrap must validate the entire payload
before committing any state. Persisting the case object before validating participants
(the old order) created a window where partial state could be written. The spec
analogy: don't put parts on the shelf until you've confirmed the shipment is correct.

A new error type `VultronProtocolViolationError` — the inbound mirror of
`VultronOutboxObjectIntegrityError` — surfaces these violations explicitly.

## References

- PR: <https://github.com/CERTCC/Vultron/pull/2813>
- Impl issue: #2808
- Spec: `specs/case-bootstrap-trust.yaml` (CBT-05-008)
