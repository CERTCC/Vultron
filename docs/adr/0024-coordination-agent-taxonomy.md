# Coordination Agent Taxonomy

Vultron's Behavior Trees contain **call-out points** — locations where the
protocol cannot determine the correct next action autonomously and must request
input from an external party. We established a canonical taxonomy of agent
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

### Canonical agent shapes

| Shape | Role |
| --- | --- |
| **Sentinel** | Monitors a condition; when met, calls a trigger endpoint |
| **Evaluator** | Receives a situation and options; returns a structured recommendation |
| **Retriever** | Receives a query; returns structured facts from an external source (including boolean/binary results — see below) |
| **Composer** | Receives context; generates a new content artifact |

These are a typology, not exactly singleton agents. A real coordination
agent may embody one shape or combine shapes (e.g., a Participant Discovery
agent composes Retriever + Evaluator).

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

A fifth shape is added:

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

An earlier draft included "message-driven responses" as an additional category of
agent touchpoint. This was rejected: receiving a protocol message is handled
by the protocol's inbox BT, not by a coordination agent. The relevant
call-out point — if any — is the evaluation or decision node that fires
*after* message receipt, which already falls under Evaluator or Retriever.

### Orchestrator deferred

Whether **Orchestrator** constitutes an additional agent shape (an agent that
sequences other agents toward a bounded goal) is unresolved. No concrete
multi-agent sequencing requirement exists yet. The question is tracked in
GitHub issue #1141 and will be revisited when two or more concrete agent
instances exist and a workflow clearly needs to sequence them.

### Boolean external queries are Retrievers, not Sentinels

A Retriever returns structured facts from an external source in response to
an on-demand query. A Sentinel monitors a condition over time and fires a
trigger endpoint when that condition is met.

A node that queries an external system synchronously and returns only a
binary (yes/no) result is still a **Retriever**: a boolean is the simplest
possible structured fact. The defining characteristic is the synchronous
on-demand query pattern, not the richness of the returned data.

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
single-word role nouns (Sentinel, Evaluator, Composer). The definition in
`CONTEXT.md` makes clear that a Retriever returns structured external facts,
not generated content — the qualifier is redundant.
