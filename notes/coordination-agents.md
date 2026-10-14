---
title: Capability Shapes Design Notes
status: active
kind: plan
tracks:
  - "#1142"
  - "#1143"
  - "#1147"
  - "#1845"
  - "#1856"
  - "#1893"
  - "#1943"
  - "#2450"
  - "#3421"
  - "#3423"
  - "#3427"
description: >
  Design for the capability layer's unbuilt work: core-owned typed-port
  contracts and renamed shape base classes (#3421), the call-out latency budget
  (#3423), open per-shape questions (#3427), composite capabilities (#1142), and
  the Sentinel call-in pattern (#2450). Also states which surface a question
  belongs on and why Sentinel is not a fifth shape.
related_notes:
  - notes/bt-integration.md
  - notes/agentic-workflow.md
  - notes/call-out-configuration.md
  - notes/protocol-asks.md
related_specs:
  - specs/behavior-tree-node-design.yaml
  - specs/behavior-tree-integration.yaml
relevant_packages:
  - vultron/core/behaviors/call_out
  - vultron/demo/fuzzer
  - vultron/core/use_cases/triggers
  - vultron/core/behaviors
---

# Capability Shapes Design Notes

A **call-out point** is a BT node where the protocol cannot decide the next action
itself and must ask an external party inside the tick. The four **capability
shapes** — **Evaluator**, **Retriever**, **Composer**, **Actuator** — are the
interface contracts that answer them. Definitions: `CONTEXT.md` § Capability
Shapes; taxonomy: ADR-0097 (superseding ADR-0024's five shapes).

The call-in and call-out surfaces are defined in
`notes/call-out-configuration.md` § "Two Integration Surfaces: Call-In and
Call-Out"; all four shapes live on the call-out surface.

## Which Surface a Question Belongs On

The discriminator is **who can answer, and when** (BT-18-014):

| The question… | Surface | Mechanism |
|---|---|---|
| can be answered by a service *this actor operates*, within one tick | call-out | a capability, injected as a `CallOutBackendFactory` |
| needs a decision from *another actor in the case* | neither — it is an **ask** | `Offer` + terminate; route on conversation state (ADR-0080) |
| is "has the moment to act arrived yet?", asked by nobody | call-in | a monitor that decides for itself and calls a trigger endpoint (the Sentinel pattern) |

An ask modelled as a call-out point is a gate that can only ever answer no,
because no answer exists at the moment of asking (ADR-0080). If the answer must
come from a peer, see `notes/protocol-asks.md`. A synchronous boolean query of an
external system is a **Retriever**, never a Sentinel (BT-18-013).

## Core-Owned Typed-Port Contracts (#3421)

Target state set by ADR-0097 and BT-18-012; today the mixins are still in
`vultron/demo/fuzzer/call_out_point.py` and declare `output_keys`.

- Each named capability gets a **core-owned declaration** carrying py_trees typed
  ports (`INPUT_PORTS` / `OUTPUT_PORTS`, ADR-0044). The shape base class cannot
  hold a per-capability contract, because many capabilities share a shape.
- The probabilistic fuzzer stand-in stays in `vultron/demo/fuzzer/` (BT-16-001)
  and binds to that declaration instead of restating it.
- The docstring is description, not authority: BT-18-001 still requires it, but a
  test reads the ports, and a disagreeing docstring is a doc bug.
- The shape bases move to `vultron/core/behaviors/call_out/` as
  `EvaluatorCapability`, `RetrieverCapability`, `ComposerCapability`,
  `ActuatorCapability`; the fuzzer layer re-exports the old `*CallOutPoint` names
  and new code uses the capability names.

Why a contract declared outside core fails: `notes/call-out-configuration.md` §
"A data-producing capability's default must write its outputs".

## A Capability Answers Fast, or It Is Not a Capability (#3423)

A backend answers within one tick (BT-18-011, `SynchronousCallOut`) **and** within
a bounded time budget (BT-18-015) configured in `ActorConfig`.

- The budget is local configuration because no peer can observe it, so
  deployments choosing different values do not diverge. An ask deadline differs
  because it travels on the wire in `endTime` so both parties read one number
  (ASK-03-004), not because it is less configurable (ASK-03-005).
- Without a budget, a slow backend blocks a `BackgroundTasks` worker until the
  bridge hits `max_iterations` and fails without naming the node.
- A seam guard **detects** an overrun and names the node; interrupting the
  backend means running it off the ticking thread. The implementation must state
  which one it provides.
- Work that cannot meet the budget is an ask or a call-in monitor.

## Fuzzer Nodes Are Call-Out Point Candidates

Each fuzzer node in `vultron/demo/fuzzer/` stands in for logic not yet identified.
For each, ask what actually drives the choice:

1. Deterministic from data the case already holds → ProtocolInternal, no
   capability.
2. External data, including a binary query → **Retriever**.
3. Judgment → **Evaluator**.
4. A side effect in an external system → **Actuator**.
5. Drafted content → **Composer**.
6. A decision from another case actor → a **protocol ask** (ADR-0080).
7. A condition watched over time that should trigger an action → the **Sentinel
   pattern** on the call-in surface.

The docstring's `Input category` and `Automation potential` give a first guess:
`High` + `Environmental check` needs no capability; `Low` + `Human decision` is an
Evaluator (or human). Say **call-out point**, never "touchpoint" (ADR-0025).

## The Sentinel Pattern Is Call-In, Not a Shape (#2450)

A Sentinel runs on its own: it watches a condition and, when it fires, calls a
trigger endpoint. None of the capability machinery applies to it — no
`CallOutBackendFactory`, no bundle field, no blackboard contract, no
`SynchronousCallOut`, no ceiling/floor rule (BT-23-002) — so ADR-0097 removed it
from the taxonomy (BT-18-013).

- **The discriminator is who initiates, not where the data comes from.** A
  capability is consulted at a call-out point; a Sentinel is never consulted, it
  decides the moment has come. A Sentinel may watch the case's own replicated
  state (#1856) and post into the case (#1845).
- **Observer is a role; Sentinel is a pattern.** A participant Sentinel usually
  holds `CVDRole.OBSERVER` (ADR-0057) by enacting the pattern; keep the terms
  distinct.
- **Two deployment shapes, chosen per monitor for protocol visibility:**

| | Participant Sentinel | Operator-side Sentinel |
|---|---|---|
| Case identity | an Actor on the roster, typically `CVDRole.OBSERVER` | none — not a participant |
| Sees case state by | `Announce(CaseLedgerEntry)` replication | whatever its host actor already knows |
| Acts by | emitting protocol messages (`Note`, `Add(ParticipantStatus)`) | calling its host actor's trigger endpoints |
| Visible to other participants | yes | no — messages appear to come from the host actor |
| Admission | Invite / Accept | deployment credentials |

A monitor accountable to the case wants the participant form; an embargo timer
that is just how one organisation runs its actor wants the operator-side form.
ADR-0080's `reap-expired-asks` trigger (ASK-05-002) is the canonical seam: core
exposes a trigger, and a watcher calls it.

Open questions for #2450 (Sentinel Ideas stay parented under #1147): invocation
model, authentication to trigger endpoints, per-case versus global scope,
behaviour when the endpoint is unreachable, audit visibility, and participant
versus external monitor.

## Per-Shape Integration

All four shapes share one convention: synchronous, in-process,
`name: str → Behaviour`; `SynchronousCallOut` raises `CallOutContractError` on a
`RUNNING` return (BT-18-011). Nothing suspends.

- **Evaluator** — receives case context and the decision; returns a structured
  answer that routes the BT. SSVC decision points (decision point + enumerated
  answers) are a natural input/output schema.
- **Retriever** — returns external facts. Should not re-query a fact already in
  the DataLayer; caching is also how a slow lookup meets the BT-18-015 budget.
  Caching and staleness policy is open (#3427).
- **Composer** — produces a content artifact (notification body, advisory draft)
  written to its output port; it does not steer control flow unless it fails.
  Auto-send versus human review is deployment policy. Open (#3427): which nodes
  consult a Composer, how it relates to `vultron/core/behaviors/note/`, and
  whether reusing prior advisory text makes it a composite with a Retriever.
- **Actuator** — causes an external side effect (e.g. `OnEmbargoExit`,
  `InjectParticipant`, `RemoveRecipient` hooks) and returns SUCCESS/FAILURE
  only, writing no outputs. Open (#3427): FAILURE and partial-success policy, the
  authentication model for the foreign system it writes to, and which systems it
  may reach. A hook that cannot confirm promptly is an ask or call-in monitor.

## Trust / Execution Authority

Auto-execute versus advisory (human confirms) is orthogonal to shape: one
Evaluator can run in either mode by deployment configuration, so a call-out point
must handle both. Recording each recommendation with its outcome (accepted as-is
or overridden) is what lets an Evaluator earn promotion to auto-execute.

## Composite Capabilities (#1142)

A composite is a bounded, single-purpose workflow composing two or more shapes
behind **one** call-out point. Worked example, Participant Discovery:

1. **Retriever** — search CPE data, supply-chain graphs, product docs, the web,
   and GitHub for affected vendors/products; output candidates with sources.
2. **Evaluator** — winnow to a recommended notification set with rationale.
3. **Affinity memory** — record who was notified on similar cases to bootstrap
   future ones; bias toward over-notification.

Input is case context; output is a recommended participant set. A composite is
not an autonomous Actor managing a whole case (#2450).
