# IMPLTS-07-001 (retired)

- **Retired**: 2026-10 (audit of unsupervised decisions, #4195)
- **Why**: Carried `deprecated: true`, which MS-09-001 forbids; removed rather than marked. The entry's own rationale names its replacement.
- **Last text**:

```yaml
  - id: IMPLTS-07-001
    priority: MUST
    kind: project
    verification_debt: '#2575'
    deprecated: true
    superseded_by: IMPLTS-07-017
    adr:
    - ADR-0094
    statement: >-
      This requirement is superseded by IMPLTS-07-017; `ruff format` replaces Black as the
      formatter.
    rationale: >-
      ADR-0094 replaced Black with `ruff format` so that formatting and linting are performed
      by one tool. `[tool.black]` and the Black dependency are removed; the `line-length = 79`
      setting carries over to `[tool.ruff]`.
    relationships:
    - rel_type: implements
      spec_id: CS-01-001
```
