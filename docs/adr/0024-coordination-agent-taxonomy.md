---
status: accepted
date: 2026-07-07
deciders: [adh]
---

# Capability Shape Taxonomy

Vultron's Behavior Trees contain **call-out points** — locations where the
protocol cannot determine the correct next action autonomously and must request
input from an external party. We established a canonical taxonomy of capability
shapes that answer those call-out points, and chose "call-out point" as the
term for those locations. The taxonomy began with four shapes and was extended
to five by the Actuator amendment (2026-07-07).

## Decisions

### "Call-out point" as the canonical term

We evaluated six alternatives: *touchpoint*, *integration point*, *hold point*,
*extension point*, *deferral point*, and *decision point* (already reserved by
SSVC). "Call-out point" was chosen because it makes the direction of flow
explicit (protocol → external party → protocol), implies the workflow pauses
and waits for a response, and cleanly contrasts with *trigger endpoint* (the
call-*in* surface where external parties invoke the protocol).

### Canonical capability shapes

| Shape | Role |
| --- | --- |
| **Sentinel** | Monitors a condition; when met, calls a trigger endpoint |
| **Evaluator** | Receives a situation and options; returns a structured recommendation |
| **Retriever** | Receives a query; returns structured facts from an external source (including boolean/binary results — see below) |
| **Composer** | Receives context; generates a new content artifact |

These are a typology of interface contracts, not implementations. A concrete
capability may embody one shape or combine shapes (e.g., a Participant
Discovery capability composes Retriever + Evaluator).

### Three-level taxonomy

The taxonomy operates at three levels of specificity:

| Level | Term | Definition |
| --- | --- | --- |
| 1 | **Capability shape** | One of the five abstract interface contracts (Sentinel, Evaluator, Retriever, Composer, Actuator); characterises the interaction pattern without prescribing the implementation |
| 2 | **Capability** | A specific named call-out point with its own blackboard contract (e.g., `EvaluateReportCredibility`); implements a capability shape for a particular domain context |
| 3 | **Capability implementation** | The factory backend fulfilling a capability at runtime; may be a Python function, a human workflow, a rules engine, or an LLM agent |

**"Coordination Agent" is retired.** The term implied a specific kind of
implementor (an autonomous AI entity) when the shapes are actually abstract
interface contracts. A capability implementation may be anything that honours
the blackboard contract. The implementation choice is made at deployment time,
not at design time.

### Amendment (2026-07-07): Fifth canonical shape — Actuator

During the FUZZ-08a-ter audit (PR #1195, issue #1239), 11 nodes classified
as `Composer` were found not to generate content artifacts in the ADR-0024
sense. They are **side-effect executors** — integration hooks that fire when
a protocol state transition occurs and invoke external systems (notification
APIs, timer services, case management writes, queue mutations). The Composer
lifecycle (reads context → dispatches → writes artifact to blackboard) does
not map to these nodes: there is no content artifact placed on the blackboard.
Expanding the Composer definition to cover side-effect invocation was
considered and rejected — it would obscure the seam and complicate the
abstraction layer design (ADR-0025 / issue #1151), which needs an invocation
interface for Actuators, not a content-generation interface.

A fifth capability shape is added:

| Shape | Role |
| --- | --- |
| **Actuator** | Receives a trigger and context; invokes an external system to cause a side effect (notification dispatch, state write, queue mutation, API call); returns SUCCESS when the side effect is confirmed, FAILURE otherwise. Does not produce a content artifact. |

The updated five-shape taxonomy:

| Shape | Role |
| --- | --- |
| **Sentinel** | Monitors a condition; when met, calls a trigger endpoint |
| **Evaluator** | Receives a situation and options; returns a structured recommendation |
| **Retriever** | Receives a query; returns structured facts from an external source (including boolean/binary results — see below) |
| **Composer** | Receives context; generates a new content artifact |
| **Actuator** | Receives a trigger and context; invokes an external system to cause a side effect |

### Message-Driven Responses excluded from the taxonomy

An earlier draft included "message-driven responses" as an additional category.
This was rejected: receiving a protocol message is handled by the protocol's
inbox BT, not by a call-out point. The relevant call-out point — if any — is
the evaluation or decision node that fires *after* message receipt, which
already falls under Evaluator or Retriever.

### Orchestrator deferred (moved to Agentic Participants epic)

Whether **Orchestrator** constitutes an additional capability shape (a
capability that sequences other capabilities toward a bounded goal) is
unresolved. However, an Orchestrator is more like an autonomous Actor with
judgment than a narrow call-out point fulfiller — its design is tracked in
the Agentic Participants epic (#2450, GitHub issue #1141) rather than here.

### Boolean external queries are Retriever capabilities, not Sentinels

A Retriever returns structured facts from an external source in response to
an on-demand query. A Sentinel monitors a condition over time and fires a
trigger endpoint when that condition is met.

A capability that queries an external system synchronously and returns only a
binary (yes/no) result is still a **Retriever** capability: a boolean is the
simplest possible structured fact. The defining characteristic is the
synchronous on-demand query pattern, not the richness of the returned data.

Nodes such as `MitigationDeployed`, `MitigationAvailable`, and `HaveExploit`
fit the Retriever shape: they receive a query (implicitly, "is X the case?"),
call an external system to retrieve the current status, and return
SUCCESS/FAILURE based on that status. They do not monitor continuously or fire
a trigger — they answer a point-in-time question when the BT reaches them.

A **Sentinel**, by contrast, runs continuously (or is invoked by an external
event) and calls a *trigger endpoint* when a condition becomes true. The
flow direction is reversed: Sentinel → trigger endpoint → protocol, not
protocol → query → external system.

### "Retriever" over "Data Retriever"

The qualifier "Data" was dropped to achieve parallel naming with the other
single-word shape nouns (Sentinel, Evaluator, Composer). The definition in
`CONTEXT.md` makes clear that a Retriever returns structured external facts,
not generated content — the qualifier is redundant.
