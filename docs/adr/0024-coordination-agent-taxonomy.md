# Coordination Agent Taxonomy

Vultron's Behavior Trees contain **call-out points** — locations where the
protocol cannot determine the correct next action autonomously and must request
input from an external party. We established a canonical taxonomy of four agent
shapes that answer those call-out points, and chose "call-out point" as the
term for those locations.

## Decisions

### "Call-out point" as the canonical term

We evaluated six alternatives: *touchpoint*, *integration point*, *hold point*,
*extension point*, *deferral point*, and *decision point* (already reserved by
SSVC). "Call-out point" was chosen because it makes the direction of flow
explicit (protocol → external party → protocol), implies the workflow pauses
and waits for a response, and cleanly contrasts with *trigger endpoint* (the
call-*in* surface where external parties invoke the protocol).

### Four canonical agent shapes

| Shape | Role |
| --- | --- |
| **Sentinel** | Monitors a condition; when met, calls a trigger endpoint |
| **Evaluator** | Receives a situation and options; returns a structured recommendation |
| **Retriever** | Receives a query; returns structured facts from an external source |
| **Composer** | Receives context; generates a new content artifact |

These are a typology, not exactly four singleton agents. A real coordination
agent may embody one shape or combine shapes (e.g., a Participant Discovery
agent composes Retriever + Evaluator).

### Message-Driven Responses excluded from the taxonomy

An earlier draft included "message-driven responses" as a fifth category of
agent touchpoint. This was rejected: receiving a protocol message is handled
by the protocol's inbox BT, not by a coordination agent. The relevant
call-out point — if any — is the evaluation or decision node that fires
*after* message receipt, which already falls under Evaluator or Retriever.

### Orchestrator deferred

Whether **Orchestrator** constitutes a fifth agent shape (an agent that
sequences other agents toward a bounded goal) is unresolved. No concrete
multi-agent sequencing requirement exists yet. The question is tracked in
GitHub issue #1141 and will be revisited when two or more concrete agent
instances exist and a workflow clearly needs to sequence them.

### "Retriever" over "Data Retriever"

The qualifier "Data" was dropped to achieve parallel naming with the other
single-word role nouns (Sentinel, Evaluator, Composer). The definition in
`CONTEXT.md` makes clear that a Retriever returns structured external facts,
not generated content — the qualifier is redundant.
