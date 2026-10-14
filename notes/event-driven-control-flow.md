---
title: Event-Driven Control Flow Design Notes
status: active
kind: guidance
description: >
  Rules for event-driven control flow: gate demo steps on their cause, not
  their order; external decision points ask and terminate; cascades run
  inside the tree, never in a demo.
related_specs:
  - specs/event-driven-control-flow.yaml
  - specs/multi-actor-demo.yaml
  - specs/demo-ci.yaml
  - specs/protocol-asks.yaml
related_notes:
  - notes/bt-integration.md
  - notes/bt-composability.md
  - notes/protocol-event-cascades.md
  - notes/protocol-asks.md
  - notes/demo-ci-diagnostics.md
  - notes/demo-scenario-authoring.md
  - notes/ownership-transfer.md
  - notes/use-case-behavior-trees.md
  - notes/demo-future-ideas.md
  - notes/case-communication-model.md
relevant_packages:
  - vultron/core
  - vultron/demo
---

# Event-Driven Control Flow Design Notes

The model — each actor a worker with an inbox and an outbox, primary events
versus cascades, causal rather than temporal order — is explained for readers in
`docs/topics/protocol_flow.md`. Requirements: EDF-01 to EDF-06. The queue/worker
framing is a reasoning tool: it does not ask for a message broker in the
prototype.

A demo supplies only primary events. If a demo must inject an intermediate step,
a cascade is not automated yet — fix the cascade, do not copy the demo pattern.

---

## Temporal Sequence vs. Causal Sequence

A scenario script reads as *A, then B, then C*; the protocol it drives is *A,
therefore B, therefore C*. A trigger returns 202 and the effect commits later in
a background task on another container, so every place the two readings differ
is a race (ADR-0058; EDF-06, DEMOMA-22).

A cross-actor step is a chain — A sends, B's inbox receives, B processes, B
commits — and only the last link proves the next step's precondition. Gate at
Committed; `notes/demo-ci-diagnostics.md` uses the same Sent / Received /
Committed layers to read a failed run.

1. **Gate on the effect, observed where it lands.** Read the predicate from the
   container of the actor that commits it; a sender-side observation proves only
   that something was sent (EDF-06-002).
2. **A synchronous observable is not evidence of an asynchronous effect.** "The
   case exists" resolves during `validate-report`; "this participant reached
   `RM.VALID`" commits after the 202 (EDF-06-003, #2134).
3. **Find a caused object by what it is, not by its cause's ID.** A forwarded
   activity has a new id (CM-21-005); scan by type, target and object as
   `find_case_invite_for_actor`, `find_cp_offer_for_case` and
   `find_ownership_transfer_offer_for_actor` do (EDF-06-004).

### A gate must actually gate

`demo_check` records a failure and returns, so the dependent step runs anyway and
its secondary failures bury the real one. Use `demo_gate` (`vultron/demo/utils.py`)
for a causal precondition and `demo_check` for a verification assertion; both
accumulate failures (DEMOCI-01-003, DEMOCI-01-007, EDF-06-005). Test a gate with
the real context manager — patching it with `contextlib.nullcontext` proves
nothing (`TestDemoGate` in `test/demo/test_demo_context_managers.py`).

### Not every wait is a defect

Liveness probes, protocol deadlines such as embargo expiry, and transport retry
backoff are irreducibly temporal: name them as temporal at the call site so
nobody "fixes" them into meaningless causal gates (EDF-06-006). Processing a
delivery leaves no completion record, so a "processed" gate is always inferred
from a downstream effect. When a precondition has no observable predicate, record
the gap instead of adding a `sleep` (EDF-06-007).

### Which side owns a race

If a wired recovery path eventually guarantees the effect, the harness may wait
for it. If the effect can be *lost*, the actor must buffer it, and a demo guard
is hiding a production bug (ADR-0037, ADR-0059 for pre-genesis ledger entries).

### Scenario narratives are the ordering oracle

A gate proves the harness waited for the right thing, not that the ordering is
the one CVD requires. The narratives under `docs/topics/scenarios/` state each
step's antecedent in domain terms, independently of the code, and their causal
edges are checked against the observed ledger's `log_index` order (ADR-0079,
CLP-14-001, DEMOMA-22-003 to DEMOMA-22-006).

---

## External Decision Nodes

An external decision node is where a cascade needs input the actor does not have:
a human judgment, a policy decision, or external data. In the `vultron/bt/`
simulation it is a fuzzer node; in the prototype it is a call-out point.

When the input must come later, the node **asks and terminates**. It never returns
`RUNNING` and never waits (EDF-04-002, ADR-0080): `BTBridge` treats root
`RUNNING` as "keep ticking", exhausts its budget, returns `FAILURE`, and shuts the
tree down, so there is nothing to resume. The answer arrives as a trigger or an
inbox message and starts a fresh evaluation that first finds where the exchange
stands (EDF-04-003, ASK-02-001). Asking another actor is the protocol-ask
primitive: emit the ask, return `SUCCESS` meaning *I asked* (ASK-01-002); see
`notes/protocol-asks.md`.

A terminal status with no request emitted is the silent failure EDF-04-005
forbids. The reference shape is `create_recommend_actor_to_case_received_tree`
(`vultron/core/behaviors/case/suggest_actor_tree.py`): its Selector routes on
where the exchange stands and the fresh branch emits `Offer(CaseParticipant)` to
the owner.

An external decision node is never:

- an excuse to implement a cascade step procedurally outside the tree;
- a place where a demo bridges two behaviors that should be connected;
- a stand-in for a deterministic step. If the actor always does the same thing
  given the same inputs, it is a cascade step to automate.

---

## Anti-Pattern: the demo does the cascade

```python
# WRONG: the demo performs steps the actor's tree should cascade into
post_to_trigger(client, vendor_id, "validate-report", body=report_params)
post_to_trigger(client, vendor_id, "create-case", body=case_params)

# RIGHT: trigger the primary event, then observe the settled state
post_to_trigger(client, vendor_id, "validate-report", body=report_params)
wait_for_case_on_container(...)
```

A scenario demo drives actors only through trigger endpoints and never posts to
another actor's inbox; see `vultron/demo/AGENTS.md` § "Puppeteer Actors via
Trigger Endpoints, Never Spoof via Inbox Injection". The cascade-after-the-tree
anti-pattern inside a use case is in `notes/use-case-behavior-trees.md`.
