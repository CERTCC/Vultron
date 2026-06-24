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
*call-out point*, *Sentinel*, *Evaluator*, *Retriever*, and *Composer*.
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
calls a trigger endpoint). An Evaluator, Retriever, and Composer are called
from the call-out surface.

---

## Fuzzer Nodes as Call-Out Point Discovery

Every fuzzer node in `vultron/demo/fuzzer/` is a **known call-out point
candidate**. Fuzzer nodes make randomized choices precisely because the real
decision logic has not been identified or implemented. Each one represents
an open question: "What information should actually drive this choice?"

### Discovery methodology

For each fuzzer node, ask:

1. What decision or fact is actually needed here?
2. Is the answer deterministic given data already in the case? → Traditional
   automation (no coordination agent required)
3. Does it require data from an external system? → **Retriever** call-out point
4. Does it require judgment/evaluation? → **Evaluator** call-out point
5. Does it require a condition to be monitored over time? → **Sentinel** on the
   call-in surface
6. Does it require content to be drafted? → **Composer** call-out point

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

**BT integration**: None. Sentinels bypass the call-out surface entirely.
They need a way to authenticate and call trigger endpoints, and a way to know
which cases to monitor.

**Open design question**: Should Sentinels register in the DataLayer as
actors? If so, their protocol actions become attributable and auditable.

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

## Terminology Note

`notes/bt-fuzzer-nodes.md` and the per-domain fuzzer notes
(`bt-fuzzer-nodes-embargo.md`, `bt-fuzzer-nodes-report-management.md`, etc.)
use the phrase **"external dependency touchpoints"** for what we now call
**call-out points**. These notes predate the canonical term. The terminology
should be aligned when those notes are next edited; do not introduce new
uses of "touchpoint" to mean call-out point.
