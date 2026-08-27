# AGENTS.md — `vultron/core/behaviors/sync/`

Agent guidance for sync/replication-related BT nodes in this package.

> For project-wide BT conventions see
> [`vultron/core/behaviors/AGENTS.md`](../AGENTS.md).

---

## Fan-out / SYNC Decomposition: Context Handoff Pattern

(ISSUE-755, 2026-06-10)

For replay/fan-out flows, split nodes along blackboard context boundaries:

1. **Collect context leaf** — reads domain state, writes derived context
   (index, recipient list, current position) to named blackboard keys.
2. **Side-effect leaves** — each reads the context written by step 1 and
   performs a single side effect (emit activity, update record).

**Condition+action hybrid nodes**: If a node checks a condition and then
performs an action, decompose it further into a `Selector` composite:

```python
Selector(
    name="EmitIfRecipientExists",
    memory=False,
    children=[
        CheckRecipientPresent(),   # pure condition; returns FAILURE → fall through
        AlwaysSuccess("skip"),     # no-op when condition already met
    ],
)
```

This preserves the original guard semantics without embedding conditional
logic inside a single `update()`.
