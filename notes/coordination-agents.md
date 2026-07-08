---
title: Coordination Agents Design Notes
status: active
description: >
  Design guidance for coordination agents — external capabilities (human, skill, or
  LLM agent) that answer Vultron call-out points. Covers the two-surface integration
  model, agent type patterns, trust/execution authority, and composite agent design.
related_notes:
  - notes/bt-fuzzer-nodes.md
  - notes/bt-integration.md
  - notes/agentic-workflow.md
related_specs:
  - specs/behavior-tree-integration.yaml
relevant_packages:
  - vultron/demo/fuzzer
  - vultron/core/use_cases/triggers
  - vultron/core/behaviors
---

# Coordination Agents Design Notes

Vultron's Behavior Trees contain **call-out points** — nodes where the protocol
cannot determine the correct next action autonomously and must request external
input before it can continue. Coordination agents are the capabilities that
answer those call-out points.

See `CONTEXT.md` § Coordination Agents for the canonical definitions of
*call-out point*, *Sentinel*, *Evaluator*, *Retriever*, *Composer*, and *Actuator*.
See ADR-0024 for the decisions behind that taxonomy.

---

## The Two Integration Surfaces

Vultron has two distinct surfaces where external capabilities connect to the
protocol. Understanding which surface you are working with is the first step
in any coordination agent design.

### Trigger endpoints (call-in surface)

`vultron/core/use_cases/triggers/` contains use cases that external parties
invoke when they have already decided to take a protocol action. The decision
has already been made; the use case executes it.

```text
External party → POST /actors/{id}/triggers/{action} → SvcXxxUseCase.execute()
```

This is the **call-in** surface: the agent drives the protocol.

### Call-out points (call-out surface)

Inside `vultron/core/behaviors/`, individual BT nodes reach points where
they cannot proceed without external judgment — a decision, a fact, or
generated content. These are call-out points: the protocol pauses and waits.

```text
BT node → call-out point → external party → response → BT continues
```

This is the **call-out** surface: the protocol drives the agent.

A Sentinel operates exclusively on the call-in surface (it watches and then
calls a trigger endpoint). An Evaluator, Retriever, Composer, and Actuator are
called from the call-out surface.

> **Key implication**: A Sentinel has **no BT call-out point**. Nodes that
> perform on-demand binary condition checks when the BT tick reaches them are
> Retrievers (or ProtocolInternal if they check data the BT already owns) —
> not Sentinels. See ADR-0024 § "Boolean external queries are Retrievers, not
> Sentinels" and issue #1266 (FUZZ-08a-quart) for the reclassification audit.

---

## Fuzzer Nodes as Call-Out Point Discovery

Every fuzzer node in `vultron/demo/fuzzer/` is a **known call-out point
candidate**. Fuzzer nodes make randomized choices precisely because the real
decision logic has not been identified or implemented. Each one represents
an open question: "What information should actually drive this choice?"

### Discovery methodology

For each fuzzer node, ask:

1. What decision or fact is actually needed here?
2. Is the answer deterministic given data already in the case (no external call)?
   → ProtocolInternal (no coordination agent required)
3. Does it require data from an external system (including binary queries)?
   → **Retriever** call-out point
4. Does it require judgment/evaluation? → **Evaluator** call-out point
5. Does it require a side effect in an external system (notification, queue, API)?
   → **Actuator** call-out point
6. Does it require content to be drafted? → **Composer** call-out point
7. Does it require a condition to be monitored continuously over time, such that
   the monitoring should trigger a protocol action when fired?
   → **Sentinel** on the call-in surface (no call-out point; see #1143)

The fuzzer node's `Input category` docstring annotation
(`Human decision`, `Environmental check`, `System integration`, etc.) and
`Automation potential` rating (`High` / `Medium` / `Low`) give a starting
assessment. `High` automation potential with `Environmental check` = no agent
needed. `Low` automation potential with `Human decision` = Evaluator (or
human) call-out point.

---

## Agent Type Integration Patterns

### Sentinel

A Sentinel runs independently — it is not called by the protocol. It monitors
a condition (a timestamp, a case flag, an external system state) and, when the
condition fires, calls a Vultron trigger endpoint.

**BT integration**: None. Sentinels bypass the call-out surface entirely. A
Sentinel has no BT call-out point. If you are looking at a BT node that checks
a binary condition when the tree reaches it, that is a Retriever (on-demand
external query) or ProtocolInternal (data the BT already owns) — not a Sentinel.

They need a way to authenticate and call trigger endpoints, and a way to know
which cases to monitor.

**Open design questions** (tracked in #1143):

- What is the Sentinel's invocation model? (polling interval, event subscription, webhook)
- How does a Sentinel authenticate to call Vultron trigger endpoints?
- Can a Sentinel be configured per-case, or is it a global service that monitors all cases?
- What is the expected failure behavior if the Sentinel cannot reach the trigger endpoint?
- How does a Sentinel signal that it has fired, for audit/ledger purposes?
- Should Sentinels register in the DataLayer so they appear as actors?

### Evaluator

An Evaluator is called at a call-out node inside a BT. It receives the
current case context and a description of the decision to be made, and
returns a structured answer that guides the BT's next branch.

**BT integration**: The call-out node blocks (or queues) BT execution,
dispatches to the Evaluator, and routes the BT based on the response.
The exact async pattern — synchronous HTTP call, queue-based dispatch,
webhook callback — is an open design question (see issue #1144).

**SSVC reuse**: SSVC decision-point structures (decision point +
enumerated answer set) are a natural schema for Evaluator input/output.
This reuse is explicitly called out in CONTEXT.md § SSVC and in the
WIP notes.

### Retriever

A Retriever is called at a call-out node that needs external facts. It
receives a query and returns structured data from an external source.

**BT integration**: Same async pattern question as Evaluator. The key
additional design consideration is caching and staleness: the same external
fact may be queried multiple times across a case lifetime; the Retriever
should not be called redundantly if the answer is already in the DataLayer.

### Composer

A Composer is called when the BT needs to attach a new content artifact to
the case — a notification body, an advisory draft, an invitation message.
Unlike Evaluators and Retrievers, a Composer's output does not affect BT
control flow; it is attached to the case or placed in the outbox.

**BT integration**: The call-out node suspends, dispatches to the Composer,
receives the artifact, and attaches it. The BT then continues regardless of
content (unless the Composer signals failure).

**Human-review gate**: Whether Composer output auto-sends or requires human
review before dispatch is a per-deployment policy question, not a protocol
question.

### Actuator

An Actuator is called at a call-out node that needs to cause a side effect in
an external system — firing a notification API, writing to a case management
system, mutating a queue, calling a timer service. Unlike Evaluators and
Retrievers, an Actuator does not return structured data for the BT to reason
with; unlike Composers, it does not produce a content artifact placed on the
blackboard. It confirms the side effect was executed.

**BT integration**: The call-out node dispatches to the Actuator and receives
a simple SUCCESS (side effect confirmed) / FAILURE (side effect failed). No
output blackboard keys are written. The BT may branch on FAILURE, but the
Actuator's job is execution, not decision.

**Examples**: `OnEmbargoExit`, `OnEmbargoAccept`, `OnEmbargoReject`,
`SetRcptQrmR`, `InjectParticipant`, `RemoveRecipient` — all nodes that fire
integration hooks when protocol state transitions occur.

**Added in**: ADR-0024 amendment, 2026-07-07 (issue #1239, PR #1195).

---

## Trust / Execution Authority

Whether an Evaluator's recommendation is immediately acted on (auto-execute)
or presented for human confirmation (advisory mode) is **orthogonal to agent
type**. The same Evaluator implementation can run in either mode depending on
deployment configuration.

This means the BT call-out point should be designed to handle both modes:

```text
call-out node → dispatch to Evaluator
  → response arrives:
      if auto-execute mode: use response directly to route BT
      if advisory mode: present to human, await confirmation, then route BT
```

Trust builds over time: an Evaluator that consistently produces recommendations
that humans confirm is a candidate for promotion to auto-execute mode.
Recording recommendations alongside outcomes (recommendation made vs.
recommendation accepted as-is / overridden) enables this trust-building.

---

## Composite Agent Pattern

Some coordination tasks require more than one agent type. The worked example
from the session design is **Participant Discovery** (issue #1142):

1. **Retriever** phase — search CPE data, supply chain graphs, product
   documentation, web sources, and GitHub for indicators that a vendor or
   product is affected. Output: candidate list with sources.
2. **Evaluator** phase — winnow candidates: is this vendor actually affected?
   worth notifying? Output: recommended notification set with rationale.
3. **Affinity group** (memory layer) — record which participants were notified
   for similar past cases so future cases can bootstrap from prior experience.
   Bias toward overnotification; adds are more important than deletes.

A composite agent coordinates these steps internally. Its external interface
remains a single call-out point: input is case context, output is a
recommended participant set. The internal Retriever + Evaluator structure is
an implementation detail.

This pattern — a bounded, single-purpose workflow that composes two or more
agent types — is the appropriate scope for a coordination agent. It is NOT
the same as an "uber-agent" that manages an entire case.

---

## Call-Out Point Abstraction Layer

> **Provisional design — formed in sand**: The pattern described here
> reflects the intent after the #867 planning session. It will be validated
> by #1151 (one exemplar per agent shape) and may be refined as the
> shape-based implementation issues (FUZZ-08d through FUZZ-08g) work through
> the full 93-node inventory. See ADR-0025 for the full decision record.

### Core concept: fuzzer as adapter

Every fuzzer node in `vultron/demo/fuzzer/` is a **call-out point adapter**
— a probabilistic stand-in for logic that has not yet been implemented. The
goal of the abstraction layer is to make the adapter *swappable* at tree
construction time, so that real implementations can replace the fuzzer
incrementally (node by node, scenario by scenario) without changing the BT
tree structure.

### Factory-based injection

The mechanism is **factory-based injection**, consistent with how BT trees
are already constructed elsewhere in the codebase:

- Each call-out point is expressed as a **backend factory**: a callable
  that produces a `py_trees.behaviour.Behaviour` node honouring the
  call-out point's blackboard contract.
- The fuzzer factory is the default for each call-out point.
- Tree-building functions that contain call-out points accept the factory
  (or a mapping of factories) as a parameter, with the fuzzer as the
  default. Swapping is a construction-time operation.

### Blackboard contracts

Every call-out point has a **blackboard contract**:

- **Input keys**: blackboard keys the node reads before dispatching
- **Output keys + types**: blackboard keys the node writes on `SUCCESS`
- **Signal**: `SUCCESS` or `FAILURE` to the tree

The fuzzer backend MUST honour the same contract as a real backend: on
`SUCCESS`, it writes synthetic data to the declared output keys. This ensures
downstream nodes are unaffected by the fuzzer-vs-real swap.

Blackboard contract requirements are specified in
`specs/behavior-tree-integration.yaml` BT-18-001 through BT-18-004.

### Shape base classes

Each of the five agent shapes (Evaluator, Retriever, Sentinel, Composer, Actuator)
defines a **lifecycle pattern** for how the node reads input, dispatches, and
writes output. Concrete call-out point nodes subclass the appropriate shape
base class. The shape base class is NOT a generic reusable class; it
documents the lifecycle pattern and defines the hook points for subclasses.

Note: Sentinel has **no call-out point base class** — it operates exclusively
on the call-in surface and has no BT node. The base classes below are for the
four shapes that appear at call-out points.

- **Evaluator**: reads situation context from the blackboard; writes a
  structured recommendation to a declared output key; `SUCCESS` = answer
  available, `FAILURE` = cannot evaluate
- **Retriever**: reads a query from the blackboard; writes structured facts
  to a declared output key (including boolean/binary results — see ADR-0024
  § "Boolean external queries are Retrievers, not Sentinels"); `SUCCESS` =
  facts retrieved, `FAILURE` = not found or unavailable
- **Composer**: reads composition context from the blackboard; writes a
  generated artifact to a declared output key; `SUCCESS` = artifact ready,
  `FAILURE` = generation failed
- **Actuator**: reads trigger context from the blackboard; invokes an external
  system; no output keys written; `SUCCESS` = side effect confirmed, `FAILURE`
  = side effect failed

### Implementation chain

```text
#1150 — Update catalog: add cross-refs (vultron/bt/ → demo/fuzzer/) +
         agent-shape classification per node [DONE]

#1151 — Design exemplar: one call-out point per shape [DONE]
         Delivered:
         - CallOutBackendFactory type alias (vultron.core.behaviors.call_out_point)
         - Five shape mixin classes (vultron.demo.fuzzer.call_out_point):
             EvaluatorCallOutPoint, RetrieverCallOutPoint, ComposerCallOutPoint,
             ActuatorCallOutPoint, SentinelCallOutPoint
         - Exemplar nodes (with blackboard contract docstrings + output_keys):
             EvaluateReportCredibility (Evaluator) — validate.py
             GatherValidationInfo (Retriever) — validate.py
             OnAccept / OnDefer (Actuator) — prioritize.py
             PrepareReport (Composer) — publication.py
             NewValidationInfoSentinel (Sentinel) — call_out_point.py (illustrative)
         - Factory injection into:
             create_validate_report_tree (credibility_factory, validity_factory,
               gather_info_factory [Phase 2 reserved])
             create_prioritize_subtree (on_accept_factory, on_defer_factory)
             create_publication_tree (prepare_report_factory) [new Phase 1 stub]
         - ADR-0025 advanced from proposed → accepted

#1152 — Wire demo BTs: audit BTs for implicit policy nodes; externalize
         as call-out points with deterministic (AlwaysSucceed/AlwaysFail)
         backends; add one randomized demo

FUZZ-08a-quart (#1266) — Reclassify remaining 17 Sentinel-labeled nodes
                           (likely all become Retriever or ProtocolInternal)

FUZZ-08d — All Evaluator-shaped call-out points (cross-domain)
FUZZ-08e — All Retriever-shaped call-out points (cross-domain)
FUZZ-08f (#1175) — All Sentinel-shaped call-out points (cross-domain)
                   [scope likely zero after FUZZ-08a-quart]
FUZZ-08g — All Composer-shaped call-out points (cross-domain)
(FUZZ-08h covers Actuator per the revised 5-shape taxonomy)

Domain sweep audits — verify completeness per domain after shape rollout
```

---

## Terminology Note

`notes/bt-fuzzer-nodes.md` and the per-domain fuzzer notes
(`bt-fuzzer-nodes-embargo.md`, `bt-fuzzer-nodes-report-management.md`, etc.)
use the phrase **"external dependency touchpoints"** for what we now call
**call-out points**. These notes predate the canonical term. The terminology
should be aligned when those notes are next edited; do not introduce new
uses of "touchpoint" to mean call-out point.
