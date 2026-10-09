# IMPLTS-07-007 (retired)

- **Retired**: 2026-10 (audit of unsupervised decisions, #4195)
- **Why**: Carried `deprecated: true`, which MS-09-001 forbids; removed rather than
  marked. The entry's own rationale names its replacement.
- **Last text**:

```yaml
  - id: IMPLTS-07-007
    priority: MUST
    kind: project
    verification_debt: '#2575'
    deprecated: true
    superseded_by: IMPLTS-07-008
    statement: This requirement is superseded by IMPLTS-07-008; the active cyclomatic complexity threshold is ≤ 10.
    rationale: >-
      The ≤ 15 threshold established here was an intermediate target. The active gate
      is now ≤ 10 as specified in IMPLTS-07-008.
    relationships:
    - rel_type: refines
      spec_id: IMPLTS-07-004
```
