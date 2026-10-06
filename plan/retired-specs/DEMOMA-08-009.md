# DEMOMA-08-009 (retired)

- **Retired**: 2026-10 (audit of unsupervised decisions, #4195)
- **Why**: Carried `deprecated: true`, which MS-09-001 forbids; removed rather than
  marked. The entry's own rationale names its replacement.
- **Last text**:

```yaml
  - id: DEMOMA-08-009
    priority: MUST
    kind: project
    verification_debt: '#2573'
    deprecated: true
    statement: >-
      Unit and integration tests MUST cover the full CASE_MANAGER delegation handshake:
      (1) Vendor offers role via `_OfferCaseManagerRoleActivity`,
      (2) Case Actor auto-accepts via `OfferCaseManagerRoleReceivedUseCase`,
      (3) Vendor receives `_AcceptCaseManagerRoleActivity` and triggers
      trust bootstrap `Create(VulnerabilityCase)` to Reporter.
    rationale: >-
      Superseded by ADR-0039 (CONCERN-2322). `_OfferCaseManagerRoleActivity` and
      `OfferCaseManagerRoleReceivedUseCase` were deleted. Test coverage for the
      replacement flow (`Offer(CaseParticipantRole)` handshake) is in
      `test/core/behaviors/case/nodes/test_delegation.py` and
      `test/adapters/driven/trigger_activity_adapter/test_actors.py`.
```
