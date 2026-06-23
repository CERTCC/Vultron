---
source: ISSUE-1085
timestamp: '2026-06-23T15:56:47.476128+00:00'
title: 'CaseProposal wire foundation: as_CaseProposal vocab, MessageSemantics, extractor
  patterns'
type: implementation
---

## Issue #1085 — CaseProposal wire foundation

Implemented the wire-layer foundation for the CaseProposal protocol (ADR-0023),
which separates "requesting case initialization" from "creating the case" using
an `as_CaseProposal` negotiation object.

### Deliverables

- `as_CaseProposal(VultronAS2Object)` vocab type with required `attributed_to`,
  inline `VulnerabilityReport` `object_`, `target`, optional `summary`
- `VultronObjectType.CASE_PROPOSAL` enum value
- `CREATE_CASE_PROPOSAL`, `ACCEPT_CASE_PROPOSAL`, `REJECT_CASE_PROPOSAL`
  `MessageSemantics` values
- `CreateCaseProposalPattern`, `AcceptCaseProposalPattern`,
  `RejectCaseProposalPattern` extractor patterns
- Three `SemanticEntry` items in `semantic_registry/case.py`
- Stub received use-case classes (raise `NotImplementedError`)
- Vocab examples module
- 6 new unit tests

### Pattern matching improvement

Refined `_match_activity_field` with a strict/permissive split:
`object_` is now strict (bare string refs cannot match typed patterns);
`context_`, `to_`, `target_` remain permissive (string URIs accepted).
This fixes a latent overmatching bug where `Accept("bare-string")` would
have matched scalar `VOtype` patterns.

PR: <https://github.com/CERTCC/Vultron/pull/1132>
