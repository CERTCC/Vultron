# DEMOMA-08-007 (retired)

- **Retired**: 2026-10 (audit of unsupervised decisions, #4195)
- **Why**: Carried `deprecated: true`, which MS-09-001 forbids; removed rather than
  marked. The entry's own rationale names its replacement.
- **Last text**:

```yaml
  - id: DEMOMA-08-007
    priority: MUST
    kind: project
    verification_debt: '#2573'
    deprecated: true
    statement: >-
      A trigger-side use case `SvcOfferCaseManagerRoleUseCase` MUST be implemented in
      `vultron/core/use_cases/triggers/actor.py` (or a new module in that package).
      It MUST build an `_OfferCaseManagerRoleActivity` addressed to the target Case Actor
      and enqueue it to the offering Vendor's outbox.
    rationale: >-
      Superseded by ADR-0039 (CONCERN-2322). `SvcOfferCaseManagerRoleUseCase` was deleted;
      the replacement is the `offer_case_participant_role` adapter method and
      `SvcOfferCaseParticipantRoleUseCase`. See SE-08-005.
```
