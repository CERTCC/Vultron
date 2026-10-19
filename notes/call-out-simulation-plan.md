---
title: "Call-Out Simulation Plan — Personality Bundles, Config Surface, Multi-Actor Fuzzing"
status: active
kind: plan
tracks:
  - "#1646"   # personality/bias bundles
  - "#1147"   # Capability Shapes (parent of #1646; also owns the config surface)
  - "#1732"   # FUZZ-08e in-process fuzz simulation scenario
  - "#1161"   # Background Behaviors and External Event Simulation (parent of #1732)
description: >
  Designs not yet built on top of the call-out bundle model: personality/bias
  bundles, a YAML/CLI configuration surface for backends, and the fully-fuzzed
  in-process multi-actor simulation scenario.
related_specs:
  - specs/behavior-tree-integration.yaml
  - specs/multi-actor-demo.yaml
related_notes:
  - notes/call-out-configuration.md
  - notes/demo-future-ideas.md
relevant_packages:
  - vultron/core/behaviors/call_out
  - vultron/demo/fuzzer
---

# Call-Out Simulation Plan

Builds on the three-mode model and domain bundles in
`notes/call-out-configuration.md`. None of this exists in the code yet.

## Personality / Bias Bundles (#1646)

A **personality bundle** is a domain bundle instantiated with factories that
have a *biased* probability distribution, giving actors behavioural
differences in multi-actor simulation:

```python
PESSIMISTIC_EMBARGO = EmbargoCallOutBundle(
    want_to_propose_embargo_factory=lambda n: AlwaysFail(n),      # never proposes
    current_embargo_acceptable_factory=lambda n: UsuallyFail(n),  # rarely accepts
    ...
)
```

This enables scenarios such as a "recalcitrant embargo negotiator" paired with
a "cooperative embargo negotiator". The existing bundle dataclasses support
personality variants without modification; no new mechanism is needed.

## YAML/CLI Configuration Surface (#1147)

A production configuration surface maps domain names plus mode strings to
bundle singletons or factory class paths. The bundle dataclass structure is the
natural target for that mapping. No issue scopes it yet beyond the Capability
Shapes epic.

## Multi-Actor In-Process Simulation (#1732, DEMOMA-18)

A fully-fuzzed in-process scenario built on STOCHASTIC bundles.

**In-process delivery via direct DataLayer injection**, chosen over:

- *ASGIEmitter loopback* — a more realistic wire path, but needs a FastAPI ASGI
  app per actor and the full HTTP pipeline; too much setup for a simulation
  tool.
- *In-memory message queue* — closest to the worker model in
  `docs/topics/protocol_flow.md`, but needs new infrastructure (a queue
  type and delivery scheduler) with no benefit over direct injection.

When actor A's BT emits an activity to actor B, the controller intercepts A's
outbox and calls B's dispatcher with the activity object: no network, no
serialisation round-trip, but the full trigger→BT→outbox→peer-inbox cascade.

**Finder + Coordinator + Vendor (3 actors)** is the minimum meaningful
configuration; `rv` omits coordinator interactions.

**Fresh in-memory DataLayer per iteration**, so each iteration is an
independent probabilistic sample.

**Termination**: the controller calls a trigger on one actor (Finder submits a
report), processes each outbox emission as an inbound activity on its target,
and repeats until every actor reaches `RM.CLOSED` or no state changes over a
configurable number of rounds (stall detection). A tick-count limit was
rejected: most use-case BTs only activate on incoming activities, so progress is
measured by RM state advancement.

**Multi-container variant**: out of scope; a containerised fuzz scenario needs
container reset and STOCHASTIC bundle configuration via environment variables
designed first.
