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
DataLayer (outbox or domain objects), not a module-level in-memory set or dict —
those are per-process, do not survive restarts, and are invisible to the BT audit
trail. The adapter-level `ValueError` on duplicate `dl.create()` is a safety net;
the BT-level guard is authoritative. Why, and the race it caused:
`notes/bt-pitfalls.md` § "Use DataLayer Outbox for Idempotency".

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

`py_trees.Blackboard.get(key)` raises `KeyError` — it does not return `None` —
when a key is registered `READ` but not yet written. An `update()` that calls
`blackboard.get()` MUST wrap it in `try/except KeyError`, set
`feedback_message`, and return an explicit `Status` (SUCCESS or FAILURE per
best-effort vs. fail-fast). Audit `register_key(..., access=Access.READ)` sites
when adding a node.

Mechanism, the silent node-shadowing variant, and the full rules:
`notes/bt-pitfalls.md` § "py_trees `blackboard.get()` Raises KeyError".

---

## PEC Consent Writes — Never Direct-Assign `embargo_consent_state`

(CM-18-005, CM-18-006; CONCERN-1970)

```python
# WRONG — plain Pydantic write; skips PEC validation and status sync
participant.embargo_consent_state = PEC.SIGNATORY

# CORRECT — validates the trigger, advances the machine, syncs metadata
participant.apply_pec_transition(PEC_Trigger.ACCEPT)
dl.save(participant)
```

Both steps are required: the machine write alone is not sufficient without the
persist. A direct assignment leaves the ledger snapshot's `emConsentState` stale
while `embargoAdherence` reports the new value — a self-contradicting record.
See `notes/participant-embargo-consent.md` § "Pitfall: Never Set
`embargo_consent_state` by Direct Assignment".

---

## Compose Before Create: Node Discovery Gate

Before writing any new BT emit, send, or state-transition node in this
package, run the BT Domain section of
`.agents/skills/shared/compose-before-create.md` (node inventory grep,
then return here), then apply these BT-specific checks
(BTND-07-005, BTND-07-009, BTND-07-010):

1. **Use the domain base class**: for emit/send nodes, subclass the
   appropriate base from the table below and override only `_call_factory()`
   and the hook methods. Do not write a new `update()` from scratch.

   | Domain | Base class | File |
   |--------|-----------|------|
   | Report | `_EmitCaseActorReportActivityBase` | `report/nodes/emit.py` |
   | Embargo | `_SendEmbargoActivityBase` | `embargo/nodes/emit.py` |
   | Participant-status | `_EmitParticipantStatusActivityBase` | `report/nodes/develop_fix.py` |
   | Single-activity (invite, ownership, other case domains) | `_EmitSingleActivityBase` | `helpers.py` |

   **If no base exists for your domain: create it first, then write the
   concrete node.** Do not implement `update()` inline in a concrete node
   class unless you have confirmed no existing base covers your
   guard+emit+outbox pattern.

2. **AC-1 compliance**: any node reading EM/RM/CS state MUST go through
   `Read*StateNode`; any node writing it MUST go through `Write*StateNode`.
   Inline reads/writes are AC-1 violations.

Specs: BTND-07-005, BTND-07-009, BTND-07-010, BTC-01-001.

---

## EM State Reads Must Use ReadEmStateNode; Writes Route Through EmbargoLifecycle

**Never read `case.current_status.em` inline inside a BT node.**
All EM state reads MUST go through `ReadEmStateNode`
(`vultron/core/behaviors/embargo/nodes/em_state.py`).

**Never write `case.current_status.em` directly inside a BT node** (EMB-18-001).
All EM state writes MUST route through `EmbargoLifecycle`
(`vultron/core/services/embargo_lifecycle.py`) — the service owns the write.

Direct field access (`case.current_status.em.state`) bypasses the canonical
channel: the read is invisible to the BT audit trail and creates paths where
state can diverge from what the canonical nodes report.
`ReadEmStateNode` was introduced to centralize EM reads (AC-1, issue #1474);
`WriteEmStateNode` was retired in issue #2712 — all writes now go through the
service.

**Pattern for reading EM state in an action node:**

```python
result_out: dict[str, object] = {}
read_node = ReadEmStateNode(case_id=case_id, result_out=result_out)
read_node.datalayer = self.datalayer
if read_node.update() != Status.SUCCESS:
    self.feedback_message = read_node.feedback_message
    return Status.FAILURE
current_em = result_out["em_before"]
assert isinstance(current_em, EM)
```

Source: CONCERN-2559

---

## Port `data_type` Is Enforced — `object` Makes It Inert

py_trees checks `data_type` on **both** sides — `_set_output()` and `get_input()`
each raise `TypeError` — so the declaration *is* the enforcement.
**Declare the concrete class whenever the writer guarantees one.** `object`
accepts anything and turns the check off; reserve it for Protocol-typed
injections (`datalayer`, `actor_id`, `trigger_activity_factory`, `sync_port`,
`wire_render_port`) and polymorphic `activity` payloads. Elsewhere it is a latent
bug: the node narrows with `cast(Foo, ...)`, so a wrong-typed value surfaces as an
`AttributeError` inside `update()` instead of at the port.

Two consequences before tightening one: a violation fails the **whole tree**, not
the one node (`_try_get_input()` does not catch `TypeError`), and a contract test
MUST discover its roster reflectively via `test/core/behaviors/port_contract.py`
— a hard-coded list cannot police a shared key. Details in `notes/bt-pitfalls.md`
§ "`NoDataAvailable` Surfaces in `initialise()`"; worked examples in the two
`test_typed_ports.py` files; ADR-0044 § Consequences; BTND-03-009.
*Source: ISSUE-2907, ISSUE-3011*

---

## See Also

- `notes/bt-integration.md` — architecture decisions, actor isolation,
  concurrency model
- `notes/bt-canonical-reference.md` — subtree map, BT-IDM anti-patterns
- `notes/bt-pitfalls.md` — blackboard, idempotency, role guards
- `notes/bt-design-patterns.md` — idiomatic BT construction patterns
- `specs/behavior-tree-integration.yaml` — BT-06 through BT-22 requirements
- `specs/behavior-tree-node-design.yaml` — BTND node design requirements
