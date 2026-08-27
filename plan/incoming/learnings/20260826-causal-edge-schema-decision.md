---
title: "Causal-edge schema: YAML frontmatter format decided for ISSUE-2204"
type: learning
timestamp: 2026-08-26
source: ISSUE-2204
signal: design-question
---

ADR-0058 left the causal-edge serialization format as "provisional — schema still
converging." In ISSUE-2204 the following schema was chosen and documented in
`docs/topics/scenarios/index.md`:

```yaml
causal_edges:
  - antecedent: <eventType>      # string — eventType in the ledger
    consequent: <eventType>      # string — eventType in the ledger
    consequent_actor: <name>     # documentary label for the committing actor
    note: <text>                 # optional human-readable explanation
    observable: true             # optional; false = skip ordering check
```

**Check semantics chosen**: for each observable edge (A, B), check that
`min(all A log_indices) < max(all B log_indices)`. This is the weakest valid
interpretation of "there exists a valid (antecedent, consequent) pair in the
ledger." A stricter interpretation (every B is preceded by some A) was
considered but deemed unnecessary for the conformance-oracle use case.

ADR-0058 should be updated to mark the schema `accepted` and reference the
index page as the authoritative source.
