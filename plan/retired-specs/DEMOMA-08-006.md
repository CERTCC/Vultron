# DEMOMA-08-006 (retired)

- **Retired**: 2026-10 (audit of unsupervised decisions, #4195)
- **Why**: Carried `deprecated: true`, which MS-09-001 forbids; removed rather than
  marked. The entry's own rationale names its replacement.
- **Last text**:

```yaml
  - id: DEMOMA-08-006
    priority: MUST
    kind: project
    verification_debt: '#2573'
    deprecated: true
    statement: >-
      `OfferCaseParticipantRolePattern`, `AcceptCaseParticipantRolePattern`, and
      `RejectCaseParticipantRolePattern` MUST be registered in `SEMANTIC_REGISTRY`.
      `OfferCaseParticipantRoleReceivedUseCase`,
      `AcceptCaseParticipantRoleReceivedUseCase`, and
      `RejectCaseParticipantRoleReceivedUseCase` MUST be registered as their
      `use_case_class`, so that they appear in the mapping returned by `use_case_map()`.
    rationale: >-
      The requirement stands; only the pattern and use-case names changed. ADR-0039
      (CONCERN-2322) deleted the `CaseManagerRole` patterns and use cases in favour of the
      `CaseParticipantRole` ones registered in `vultron/semantic_registry/actor.py`. The
      statement was restated in terms of the surviving classes because it had been left
      asserting a MUST that three deleted pattern classes be registered, in a registry that
      no longer exists under that name (issue #3022). See SE-08-005.
```
