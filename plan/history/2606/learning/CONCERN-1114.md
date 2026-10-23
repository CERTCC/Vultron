---
source: CONCERN-1114
timestamp: '2026-06-22T20:27:07.566892+00:00'
title: 'Spec quality gaps from 2026-05-06 review: 6 bugs and 7 incomplete/vague items'
type: learning
---

## Summary

A systematic review of all spec files changed since 2026-05-06 found 6 definite errors (priority mismatches, contradictions, truncated content) and 7 instances of vagueness or incomplete coverage.

## Category

Documentation / Specification Quality

## Severity

Medium — most are fixable without design changes; two (CLP-02-006, CP-01-004) could actively mislead an implementer.

## Evidence

### Bugs / Definite Problems

1. **`CLP-02-006` priority mismatch**: Marked `priority: MUST_NOT` but the statement says "MUST include a `log_index` field … MUST NOT be assigned by external parties". The first clause requires MUST; a MUST_NOT priority causes an implementer to skip the field entirely.
2. **`CP-01-004` contradicts `AKM-03-001`**: Permits a URI reference in `as_CaseProposal.object_`, which directly contradicts `AKM-03-001` ("outbound activities MUST include full inline objects, never bare URIs").
3. **`SYNC-06-004` truncated statement**: Statement ends mid-sentence with "This is a distinct replication tier from participant replication:" — the continuation has been missing since the original spec migration commit (`2cacc05c`).
4. **`SYNC-05-002` priority inconsistency**: `priority: MUST` wraps a statement that says "SHOULD be configurable; default values MUST be documented" — conflicting normative levels within a single spec.
5. **`DEMOMA-06-002` missing M3**: Milestone list jumps M1 → M2 → M4 with M3 absent and no explanation.
6. **`CLP` description typo**: "local case audit **ledgerging**" — should be "ledgering" or just "ledger".

### Vagueness / Incomplete Specs

1. **`CBT-03-004` undefined vocabulary**: Specifies "send a generic `Question`" but `Question` is not defined in the Vultron AS2 vocabulary — not implementable as written.
2. **`CBT-03-001/-003` unspecified timeout**: Requires a "short bounded interval" / "bounded pre-bootstrap queue" with no default value, configuration pointer, or cross-reference to a `CFG-*` spec (contrast with `CLP-06-003`, which does).
3. **`DEMOMA-08-002` dangling requirement**: Introduces `OFFER_CASE_MANAGER_ROLE` and `ACCEPT_CASE_MANAGER_ROLE` `MessageSemantics` values with no corresponding wire vocab, extractor pattern, or use-case specs — a dangling requirement with no downstream specs to implement against.
4. **`ARCH-13-005` incomplete interface**: Requires `ActorScopedDataLayer` Protocol type but does not specify its method interface or cross-reference the DL spec.
5. **`CP-05-003` no atomicity/failure spec**: The two-activity response sequence (`Accept(CaseProposal)` then `Create(VulnerabilityCase)`) has no atomicity, failure, or idempotency coverage.
6. **`PCR-08-009` missing positive counterpart**: Prohibits the case owner from emitting invitee RM state-change activities but never explicitly states who is responsible (the Case Actor) — the positive duty is implied but unspecified.
7. **`PD-09-004` vague scoping criterion**: "Changes to the canonical CaseLedgerEntry commit path" is too vague to apply consistently — needs specific file/class anchors.

## Resolution

All 13 items resolved in planning session on 2026-06-22.

**Resolved**: 2026-06-22 — spec fixes in docs PR #1124; implementation tracked in #1125, #1126, #1127.

Docs PR: <https://github.com/CERTCC/Vultron/pull/1124>.
Spec: `specs/multi-actor-demo.yaml`, `specs/case-ledger-processing.yaml`, `specs/case-proposal.yaml`,
`specs/sync-ledger-replication.yaml`, `specs/case-bootstrap-trust.yaml`, `specs/architecture.yaml`,
`specs/participant-case-replica.yaml`, `specs/project-documentation.yaml`.
