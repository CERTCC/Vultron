# IMPLTS-07-004 (retired)

- **Retired**: 2026-10 (audit of unsupervised decisions, #4195)
- **Why**: Carried `deprecated: true`, which MS-09-001 forbids; removed rather than marked. The entry's own rationale names its replacement.
- **Last text**:

```yaml
  - id: IMPLTS-07-004
    priority: MUST
    kind: project
    verification_debt: '#2575'
    deprecated: true
    superseded_by: IMPLTS-07-017
    adr:
    - ADR-0094
    statement: >-
      This requirement is superseded by IMPLTS-07-017; ruff replaces flake8 as the linter.
    rationale: >-
      ADR-0094 replaced flake8 with ruff, which covers flake8's rule set, subsumes isort's
      import ordering, and gates several `CS-*` requirements flake8 could not see. `.flake8`
      and the flake8 dependency are removed.
    relationships:
    - rel_type: implements
      spec_id: CS-01-001
```
