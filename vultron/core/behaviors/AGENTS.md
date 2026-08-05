# AGENTS.md — `vultron/core/behaviors/`

Agent guidance for implementing and reviewing BT nodes and subtrees in this
package.

---

## No God Nodes (BT-IDM-03)

A BT leaf node's `update()` method MUST NOT exceed ~20–30 lines. If it does,
it is doing too much.

**What belongs in the tree structure, not in a node:**

- Precondition checks (use `DataLayerCondition` subclasses)
- Routing guards (use condition nodes before state-mutation nodes;
  see BT-19-001)
- Idempotency checks (use a `DataLayerCondition` that queries the DataLayer
  for existing outbox or state records — not a module-level in-memory set)
- Multi-step action sequences (compose as a `Sequence` of simple leaf nodes)

**References:**

- `notes/bt-canonical-reference.md` § "BT-IDM-03: God BT nodes"
- `specs/behavior-tree-node-design.yaml` BTND-02-001 through BTND-02-004
- `notes/bt-pitfalls.md` — per-pitfall debugging notes

**Violation example** — the `AutoCloseBranchNode` prior to #1677 buried
`_all_participants_closed()`, `_claim_close()`, `_resolve_case_manager_id()`,
and `_emit_close_case()` all inside `update()`. Each should be a separate
leaf node in a `Sequence`. See DEMOMA-07-006.

---

## Idempotency — DataLayer over Process State

BT condition nodes that guard "has this action already fired?" MUST query the
DataLayer (outbox or domain objects), not a module-level in-memory set or dict.
Process-level sets do not survive restarts and are invisible to the BT audit
trail.

The adapter-level `ValueError` on duplicate `dl.create()` provides a safety
net, but the BT-level guard should be authoritative.

---

## Precondition Pattern — Condition Before Action

Use the Sequence-with-precondition pattern, not the "skip-unless" Selector
framing:

```text
# PREFERRED
Sequence
  ├─ AllParticipantsRMClosedConditionNode   # FAILURE → whole Sequence skips
  ├─ CloseNotYetEmittedConditionNode        # FAILURE → whole Sequence skips
  ├─ ResolveCaseManagerNode                 # routing guard
  └─ EmitCloseCaseNode                      # action

# AVOID — hides the skip logic
Selector
  ├─ SkipUnlessConditionNode (SUCCESS = skip)
  └─ ActionNode
```

The Sequence framing keeps all conditions readable left-to-right in the tree.

**Reference:** BTND-08-001, BTND-08-002,
`notes/bt-design-patterns.md` § "Negative-Guard Anti-Pattern".

---

## Routing Guards Must Precede State Mutation

Resolve routing prerequisites (e.g., Case Manager ID) in a read-only condition
or guard node BEFORE any state-mutation or emit node. See BT-19-001, BT-19-002.

---

## `Blackboard.get()` Raises `KeyError` on Unset READ Keys

`py_trees.Blackboard.get(key)` raises `KeyError` (not returns `None`) when a
key has been registered with `READ` access but has not yet been written by any
node. `update()` methods that call `blackboard.get()` MUST wrap the call in
`try/except KeyError` or check for prior writes.

**Pattern:**

```python
try:
    value = self.blackboard.get("key")
except KeyError:
    self.feedback_message = "key not yet on blackboard"
    return Status.SUCCESS  # or FAILURE depending on best-effort vs fail-fast
```

Any `DataLayerAction.setup()` that registers `READ` keys and whose `update()`
calls `blackboard.get()` is at risk. Audit `register_key(..., access=Access.READ)`
sites in `behaviors/` when adding new BT nodes.

See `notes/bt-pitfalls.md` for related blackboard pitfalls.

---

## PEC Consent Writes — Never Direct-Assign `embargo_consent_state`

**Pitfall** (CM-18-005, CM-18-006; CONCERN-1970):

```python
# WRONG — bypasses state machine and does not sync ParticipantStatus
participant.embargo_consent_state = PEC.SIGNATORY
```

This is a plain Pydantic field write. It skips the PEC state machine validation
**and** `_sync_latest_status_metadata()`, so the canonical ledger snapshot
retains the stale `emConsentState` while `embargoAdherence` reports the new
value — a self-contradicting record.

**Always use `apply_pec_transition()` and persist the resulting
`ParticipantStatus`:**

```python
# CORRECT
apply_pec_transition(participant, PEC_Trigger.ACCEPT)
dl.save(participant)
```

`apply_pec_transition()` validates the trigger, advances the machine, and syncs
`_latest_status_metadata`. Both steps are required: the machine write alone is
not sufficient without the persist. See `notes/participant-embargo-consent.md`
§ "Pitfall: Never Set `embargo_consent_state` by Direct Assignment".

---

## See Also

- `notes/bt-integration.md` — architecture decisions, actor isolation,
  concurrency model
- `notes/bt-canonical-reference.md` — subtree map, BT-IDM anti-patterns
- `notes/bt-pitfalls.md` — blackboard, idempotency, role guards
- `notes/bt-design-patterns.md` — idiomatic BT construction patterns
- `specs/behavior-tree-integration.yaml` — BT-06 through BT-22 requirements
- `specs/behavior-tree-node-design.yaml` — BTND node design requirements
