# IMPLTS-07-013 (retired)

- **Retired**: 2026-10 (audit of unsupervised decisions, #4195)
- **Why**: Carried `deprecated: true`, which MS-09-001 forbids; removed rather than marked. The entry's own rationale names its replacement.
- **Last text**:

```yaml
  - id: IMPLTS-07-013
    priority: MUST
    kind: project
    verification_debt: '#2575'
    deprecated: true
    superseded_by: IMPLTS-07-018
    adr:
    - ADR-0094
    statement: >-
      This requirement is superseded by IMPLTS-07-018; ruff, not flake8, is the linter that
      runs in CI.
    rationale: ADR-0094 retired flake8. The equivalent obligation for ruff is IMPLTS-07-018.
    relationships:
    - rel_type: refines
      spec_id: IMPLTS-07-004
```
