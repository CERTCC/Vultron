# DEMOMA-08-008 (retired)

- **Retired**: 2026-10 (audit of unsupervised decisions, #4195)
- **Why**: Carried `deprecated: true`, which MS-09-001 forbids; removed rather than
  marked. The entry's own rationale names its replacement.
- **Last text**:

```yaml
  - id: DEMOMA-08-008
    priority: SHOULD
    kind: project
    deprecated: true
    statement: >-
      A trigger-side use case `SvcAcceptCaseManagerRoleUseCase` SHOULD be implemented
      for the Case Actor to explicitly accept (rather than auto-accepting via the received
      use case). This allows manual override of the auto-accept behavior for deployments
      that require explicit operator approval before the Case Actor assumes the role.
    rationale: >-
      Superseded by ADR-0039 (CONCERN-2322). `SvcAcceptCaseManagerRoleUseCase` was deleted;
      auto-acceptance is now handled by `AutoAcceptCaseParticipantRoleNode` in the received
      tree. See SE-08-005.
```
