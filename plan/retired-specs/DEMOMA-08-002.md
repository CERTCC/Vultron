# DEMOMA-08-002 (retired)

- **Retired**: 2026-10 (audit of unsupervised decisions, #4195)
- **Why**: Carried `deprecated: true`, which MS-09-001 forbids; removed rather than marked. The entry's own rationale names its replacement.
- **Last text**:

```yaml
  - id: DEMOMA-08-002
    priority: MUST
    kind: project
    verification_debt: '#2573'
    deprecated: true
    statement: >-
      Case-participant role delegation MUST be implemented as a protocol mechanism distinct
      from `OFFER_CASE_OWNERSHIP_TRANSFER`, so that the Vendor can retain `CASE_OWNER` while
      delegating operational authority to a service actor. The three-message handshake
      (Offer/Accept/Reject) MUST use the distinct `MessageSemantics` values
      `OFFER_CASE_PARTICIPANT_ROLE`, `ACCEPT_CASE_PARTICIPANT_ROLE`, and
      `REJECT_CASE_PARTICIPANT_ROLE`.
    rationale: >-
      The requirement stands; only the semantics names changed. ADR-0039 (CONCERN-2322)
      removed the original `CASE_MANAGER`-specific wire format and all supporting
      infrastructure, replacing it with the self-describing
      `Offer(CaseParticipantRole, target=Actor, context=VulnerabilityCase)` shape, which
      also eliminates the ambiguity with `OFFER_CASE_OWNERSHIP_TRANSFER`. The statement was
      restated in terms of the surviving semantics because it had been left asserting a MUST
      about three deleted enum members (issue #3022). See SE-08-005.
```
