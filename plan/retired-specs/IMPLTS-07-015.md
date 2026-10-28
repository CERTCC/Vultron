# IMPLTS-07-015 (retired)

- **Retired**: 2026-10-28 (#5282)
- **Replacement**: IMPLTS-07-016
- **Why**: Its precondition is met: filterwarnings = ["error"] is active in pyproject.toml; IMPLTS-07-016 holds the standing rule
- **Last text**:

```yaml
  - id: IMPLTS-07-015
    priority: MUST
    kind: project
    verification_debt: '#2575'
    statement: >-
      Existing warnings MUST be resolved before the `filterwarnings = ["error"]`
      setting is activated.
    rationale: >-
      Unresolved pre-existing warnings must be cleared to avoid a broken CI state
      when the filterwarnings gate is enabled.
    relationships:
    - rel_type: refines
      spec_id: IMPLTS-07-006
```
