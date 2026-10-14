---
title: "Triggerable Behaviors: Design Notes"
status: active
kind: guidance
tags: [triggers, bt-design, call-out-points]
description: "Rules for designing triggerable behaviors: classifying BT nodes into condition checks, evaluation tasks, and execution tasks; capturing side effects the reference diagrams omit; keeping placeholder nodes as integration seams."
related_specs:
  - specs/triggerable-behaviors.yaml
  - specs/behavior-tree-integration.yaml
  - specs/datalayer.yaml
related_notes:
  - notes/bt-integration.md
  - notes/datalayer-design.md
  - notes/do-work-behaviors.md
  - notes/protocol-event-cascades.md
relevant_packages:
  - vultron/adapters/driving/fastapi
  - vultron/core/use_cases/triggers
  - vultron/core/behaviors
---

# Triggerable Behaviors: Design Notes

A triggerable behavior is initiated by the local actor's own decision, not by
an inbound message; it is the counterpart of the received-message pipeline.
The trigger API contract is `specs/triggerable-behaviors.yaml`; the
general-purpose vs. demo-only classification rules are in
`vultron/core/use_cases/triggers/AGENTS.md`. The reference trees these
behaviors implement are under `docs/topics/behavior_logic/`.

---

## Per-Actor DataLayer

A trigger endpoint resolves the acting actor's own DataLayer from `actor_id`
through dependency injection (`get_trigger_dl` in
`vultron/adapters/driving/fastapi/deps.py`), never a shared store, because the
actor id is the store name (DL-07-004).

---

## Classify Each Node Before Mapping It to a Trigger

When deciding which nodes of a reference BT become triggerable behaviors,
classify each node; only execution tasks are natural trigger units.

- **Condition checks** — a boolean fact about current state ("is report
  valid?", "timer expired?"). They map to DataLayer queries or computed
  properties and are never triggers on their own.
- **Evaluation tasks** — judgment that available data cannot fully automate
  ("evaluate credibility", "current terms ok?"). They become call-out points
  (ADR-0025): a human-in-the-loop interface, an LLM-assisted evaluator, or a
  policy rule. The simulator stubs for them are cataloged in
  `docs/developer/reference/bt-fuzzer/index.md`.
- **Execution tasks** — a concrete action with observable side effects
  (emitting a protocol message, updating case state, creating objects).

The `docs/topics/behavior_logic/` diagrams were drawn by hand; when a diagram
and its text disagree, the text is authoritative.

---

## Capture Side Effects the Diagrams Omit

The reference diagrams draw "emit FOO" as a single message, but each emit has
cascading effects (state transitions, case-object updates, participant
notifications). A trigger's BT MUST model every protocol-relevant side effect,
even ones the diagram omits, and the trigger tree's module docstring lists
them. Cascades into downstream behaviors are BT subtrees, not procedural calls
after the tree runs (BT-06-005).

---

## Keep Placeholder Nodes as Integration Seams

Some reference-tree nodes stand for local processes outside the prototype's
scope ("exit embargo", "accept"/"defer" in the priority queue, "gather
info"). Keep them: they are where real integrations (task queues, webhooks,
ITSM) attach. Each one logs at INFO when it runs, returns `SUCCESS` so it
never blocks the tree, and is labeled a placeholder in its docstring.
