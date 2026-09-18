---
title: Capability Shapes Design Notes
status: active
description: >
  Design guidance for capability shapes — the four abstract interface contracts that
  characterise how call-out points interact with the protocol. Covers the three-level
  taxonomy (shape / capability / capability implementation), the two-surface integration
  model, the core-declared typed-port contract, the call-out-versus-protocol-ask rule,
  shape patterns, trust/execution authority, and composite capability design. Records
  why Sentinel is a call-in pattern rather than a fifth shape.
related_notes:
  - notes/bt-fuzzer-nodes.md
  - notes/bt-integration.md
  - notes/agentic-workflow.md
  - notes/call-out-configuration.md
  - notes/protocol-asks.md
related_specs:
  - specs/behavior-tree-integration.yaml
relevant_packages:
  - vultron/core/behaviors/call_out
  - vultron/demo/fuzzer
  - vultron/core/use_cases/triggers
  - vultron/core/behaviors
---

# Capability Shapes Design Notes

Vultron's Behavior Trees contain **call-out points** — nodes where the protocol
cannot determine the correct next action autonomously and must request external
input before it can continue. The four **capability shapes** characterise the
interface contracts that answer those call-out points: **Evaluator**,
**Retriever**, **Composer**, and **Actuator**.

See `CONTEXT.md` § Capability Shapes for the canonical definitions of
*call-out point*, *capability shape*, *Evaluator*, *Retriever*, *Composer*, and
*Actuator*.
See ADR-0024 for the original taxonomy and ADR-0097 for the current one.

> **Sentinel is not one of them.** ADR-0097 (planning group G07) demoted Sentinel
> out of the capability-shape taxonomy: it is a **call-in integration pattern**,
> tracked under the Agentic Participants epic (#2450), not a call-out shape. See
> [The Sentinel pattern is call-in, not a shape](#the-sentinel-pattern-is-call-in-not-a-shape)
> below for why, and BT-18-013 for the normative statement.

---

## The Two Integration Surfaces

Vultron has two distinct surfaces where external capabilities connect to the
protocol. Understanding which surface you are working with is the first step
in any capability shape design.

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

All four capability shapes are called from the call-out surface. The Sentinel
pattern operates exclusively on the call-in surface (it watches, then calls a
trigger endpoint) — which is why it is a pattern rather than a shape.

> **Key implication**: the Sentinel pattern has **no BT call-out point**. Nodes
> that perform on-demand binary condition checks when the BT tick reaches them
> are Retrievers (or ProtocolInternal if they check data the BT already owns).
> Per BT-18-013, Sentinel is not an available call-out classification at all, so
> Retriever is the only answer for a synchronous external query. See ADR-0024 §
> "Boolean external queries are Retrievers, not Sentinels" and issue #1266
> (FUZZ-08a-quart) for the reclassification audit.

---

## Which surface a question belongs on

Three surfaces, and choosing wrongly produces a seam that cannot work. The
discriminator is **who can answer, and when** (BT-18-014):

| The question… | Surface | Mechanism |
|---|---|---|
| can be answered by a service *this actor operates*, within one tick | call-out | a capability, injected as a `CallOutBackendFactory` |
| needs a decision from *another actor in the case* | neither — it is an **ask** | `Offer` + terminate; route on conversation state (ADR-0080) |
| is "has the moment to act arrived yet?", asked by nobody | call-in | a monitor that decides for itself and calls a trigger endpoint (the Sentinel pattern) |

Modelling an ask as a call-out point produces a gate that **can only ever answer
no**, because at the moment of asking no answer exists. This is not hypothetical:
ADR-0080 found exactly this defect in ADR-0076's assignment of the Case Owner
approval gates to the Evaluator shape, and amended it. `RequireCaseOwnerApprovalNode`
returning unconditional `FAILURE` is the fossil of that mistake.

Before adding a call-out point, ask which row you are in. If the answer has to
come from a peer, you want `notes/protocol-asks.md`, not this file.

---

## The capability's contract is core-owned typed ports

A capability declares its blackboard contract as **py_trees typed ports**
(`input_ports()` / `output_ports()`, ADR-0044) on a declaration owned by the core
layer — **not** as a docstring, and **not** as an `output_keys` dict in
`vultron/demo/fuzzer/` (BT-18-012).

This is not a new mechanism. ADR-0044 already makes typed ports *"the standard
base for all nodes in `vultron/core/behaviors/`"*; the capability layer uses the
same one rather than a registry of its own. What a contract declared outside core
costs is recorded in `notes/call-out-configuration.md` § "A data-producing
capability's default must write its outputs".

Two consequences worth internalising:

- **The docstring is description, not authority.** BT-18-001 still requires it —
  a reader should not have to open two files — but a test reads the declared
  ports. A docstring that disagrees with the ports is a doc bug, not a contract
  change.
- **The shape base classes are core, and named for capabilities.** They live in
  `vultron/core/behaviors/call_out/` as `EvaluatorCapability`,
  `RetrieverCapability`, `ComposerCapability`, and `ActuatorCapability`
  (ADR-0097 decision 6). The simulation layer re-exports the older
  `*CallOutPoint` names so existing fuzzer subclasses keep working; new code uses
  the capability names.

### A capability answers fast, or it is not a capability

A call-out backend answers within one tick (BT-18-011, guarded by
`SynchronousCallOut`) **and** within a bounded, configurable time budget
(BT-18-015). The budget lives in `ActorConfig`, not in the spec and not in a
literal: it is local to one actor and observable by no peer, so two deployments
choosing different values is not divergence. Contrast an ask deadline, which
travels on the wire in `end_time` precisely so both parties read the same number
(ASK-03-003).

The failure this prevents is easy to miss. Nothing suspends, so a backend that
makes a slow HTTP call does not *look* broken — it blocks a `BackgroundTasks`
worker while the bridge ticks toward `max_iterations`, and then fails without
naming the offending node. That is the same opaque failure BT-18-011 was written
to prevent, reached by a different route. Work that cannot meet the budget is an
ask or a call-in monitor.

---

## Fuzzer Nodes as Call-Out Point Discovery

Every fuzzer node in `vultron/demo/fuzzer/` is a **known call-out point
candidate**. Fuzzer nodes make randomized choices precisely because the real
capability logic has not been identified or implemented. Each one represents
an open question: "What information should actually drive this choice?"

### Discovery methodology

For each fuzzer node, ask:

1. What decision or fact is actually needed here?
2. Is the answer deterministic given data already in the case (no external call)?
   → ProtocolInternal (no capability needed)
3. Does it require data from an external system (including binary queries)?
   → **Retriever** call-out point
4. Does it require judgment/evaluation? → **Evaluator** call-out point
5. Does it require a side effect in an external system (notification, queue, API)?
   → **Actuator** call-out point
6. Does it require content to be drafted? → **Composer** call-out point
7. Does it require a **decision from another actor in the case**?
   → not a call-out point at all — it is a **protocol ask** (ADR-0080,
   BT-18-014); see `notes/protocol-asks.md`
8. Does it require a condition to be monitored continuously over time, such that
   the monitoring should trigger a protocol action when fired?
   → the **Sentinel pattern** on the call-in surface (no call-out point, no
   capability shape; tracked under #2450)

The fuzzer node's `Input category` docstring annotation
(`Human decision`, `Environmental check`, `System integration`, etc.) and
`Automation potential` rating (`High` / `Medium` / `Low`) give a starting
assessment. `High` automation potential with `Environmental check` = no
capability needed. `Low` automation potential with `Human decision` = Evaluator
(or human) call-out point.

---

## The Sentinel pattern is call-in, not a shape

A Sentinel runs independently — it is not called by the protocol. It monitors a
condition (a timestamp, a case flag, an external system state) and, when the
condition fires, calls a Vultron trigger endpoint.

ADR-0024 listed it as a fifth capability shape. ADR-0097 removed it, because
**every property that makes the capability layer work is inapplicable to it**:

| | Evaluator / Retriever / Composer / Actuator | Sentinel |
|---|---|---|
| `CallOutBackendFactory` | yes | no |
| Domain bundle field | yes | no |
| Blackboard contract | yes | none |
| `SynchronousCallOut`, BT-18-011 | yes | not applicable |
| Ceiling/floor rule (BT-23-002) | yes | not applicable |
| Surface | call-out | call-**in** |

A taxonomy whose fifth member shares none of the machinery of the other four is
sorting two different things. The clearest evidence was the code: three
`SentinelCallOutPoint` subclasses existed as py_trees Behaviours carrying a
`success_rate`, wired into no bundle and instantiated nowhere, while
`CheckNoNewDeploymentInfoNode` read a blackboard flag documented as written by a
Sentinel that never ran. The class hierarchy asserted "this is a BT node" and the
docstring asserted "this is not a BT node" in the same file.

### The discriminator is who initiates, not where the data comes from

Do not define a Sentinel as "the one that reads external data" — it is wrong in a
way that will mislead you. A Sentinel may be a **case participant**: an Actor
admitted through the ordinary Invite/Accept path, most naturally holding
`CVDRole.OBSERVER` (the base role, no vendor-fix-deployment obligations —
ADR-0057, CM-25). It then receives `Announce(CaseLedgerEntry)` like any
participant, so what it watches can be **the case's own state**, arriving by
ordinary replication. #1856 observes case state; #1845 posts
`Add(ParticipantStatus)` into the case. Neither is externally sourced in any
meaningful sense.

The real discriminator is **who initiates**:

- A **capability is consulted.** The protocol reaches a call-out point, asks, and
  uses the answer inside that tick.
- A **Sentinel is never consulted.** It decides for itself that the moment has
  come, and acts.

That is the whole call-in/call-out axis, and it holds whether the trigger
condition came from a threat feed or from the ledger.

It is also the strongest reason for the demotion. A participant Sentinel holds
protocol identity, a roster seat, a role, and a case replica, and it acts by
emitting ordinary protocol messages. That is a **peer**, not an interface contract
at a BT seam.

> **Terminology hazard.** The glossary lists "monitor" and "watcher" among the
> aliases to *avoid* for the **Observer** role. Keep Sentinel and Observer
> distinct: Observer is a **role a participant holds**; Sentinel is a
> **behavioural pattern**. A participant Sentinel holds the one by enacting the
> other.

### Two deployment shapes, with different protocol visibility

| | Participant Sentinel | Operator-side Sentinel |
|---|---|---|
| Case identity | an Actor on the roster, typically `CVDRole.OBSERVER` | none — not a participant |
| Sees case state by | `Announce(CaseLedgerEntry)` replication | whatever its host actor already knows |
| Acts by | emitting protocol messages (`Note`, `Add(ParticipantStatus)`) | calling its host actor's trigger endpoints |
| Visible to other participants | yes — observations and actions replicate | no — messages appear to come from the host actor |
| Admission | Invite / Accept | deployment credentials |

Neither form is preferred in general, and the choice is a **protocol-visibility**
decision rather than a convenience one. A threat-intelligence monitor that should
be accountable to the case wants the participant form; an embargo timer that is
merely how one organisation operates its own actor wants the operator-side form.
Expect to answer this per monitor, not once for all of them.

**Where the work went.** The Sentinel pattern is tracked under the Agentic
Participants epic (#2450). Nothing was cancelled; #1143 and the four Sentinel
Ideas (#1845, #1856, #1893, #1943) moved there. ADR-0080's `reap-expired-asks`
trigger (ASK-05-002) is the canonical example of the pattern's seam: core exposes
a trigger endpoint, and a watcher calls it.

The pattern's open design questions are unchanged by the demotion — invocation
model, authentication to trigger endpoints, per-case versus global scope, failure
behaviour when the endpoint is unreachable, audit visibility, and whether a
monitor joins the case as a participant or drives one from outside. They are just
no longer capability-layer questions.

## Capability Shape Integration Patterns

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
or presented for human confirmation (advisory mode) is **orthogonal to
capability shape**. The same Evaluator implementation can run in either mode
depending on deployment configuration.

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

## Composite Capability Pattern

Some coordination tasks require more than one capability shape. The worked
example from the session design is **Participant Discovery** (issue #1142):

1. **Retriever** phase — search CPE data, supply chain graphs, product
   documentation, web sources, and GitHub for indicators that a vendor or
   product is affected. Output: candidate list with sources.
2. **Evaluator** phase — winnow candidates: is this vendor actually affected?
   worth notifying? Output: recommended notification set with rationale.
3. **Affinity group** (memory layer) — record which participants were notified
   for similar past cases so future cases can bootstrap from prior experience.
   Bias toward overnotification; adds are more important than deletes.

A composite capability coordinates these steps internally. Its external
interface remains a single call-out point: input is case context, output is a
recommended participant set. The internal Retriever + Evaluator structure is
an implementation detail.

This pattern — a bounded, single-purpose workflow that composes two or more
capability shapes — is the appropriate scope for a composite capability. It is
NOT the same as an autonomous Actor that manages an entire case (see the
Agentic Participants epic, #2450).

---

## Terminology Note

`notes/bt-fuzzer-nodes.md` and the per-domain fuzzer notes
(`bt-fuzzer-nodes-embargo.md`, `bt-fuzzer-nodes-report-management.md`, etc.)
use the phrase **"external dependency touchpoints"** for what we now call
**call-out points**. These notes predate the canonical term. The terminology
should be aligned when those notes are next edited; do not introduce new
uses of "touchpoint" to mean call-out point.
