---
title: Protocol Event Cascades
status: active
kind: guidance
description: >
  Rules for protocol cascades: only primary events are triggered, every
  consequence is a BT subtree, and a missing cascade is diagnosed apart from
  a harness race.
related_specs:
  - specs/behavior-tree-integration.yaml
  - specs/case-management.yaml
  - specs/triggerable-behaviors.yaml
  - specs/multi-actor-demo.yaml
related_notes:
  - notes/activitystreams-semantics.md
  - notes/bt-integration.md
  - notes/event-driven-control-flow.md
  - notes/case-joining.md
relevant_packages:
  - vultron/core/use_cases
  - vultron/core/behaviors
---

# Protocol Event Cascades

## Trigger Only Primary Events

A caller (demo runner, operator, or agentic client) triggers only **primary
events** — actor decisions such as submit-report, validate-report, add-note,
propose-embargo, terminate-embargo, suggest-actor-to-case. Every consequence
(case creation on report receipt, engagement on invite acceptance, broadcasts
of case updates per CM-06-001) cascades from the actors' own BTs.

A demo step that triggers a consequence by hand shows puppeteered behavior,
not the protocol working (DEMOMA-05-001). Each such step marks a gap: a
missing BT cascade, an unconnected outbox delivery path, or a missing `to`
field on an outgoing activity.

---

## Cascades MUST Be BT Subtrees

Fix a cascade gap by adding the consequence as a child subtree of the parent
behavior's BT, at the place the parent→child relationship appears in the
reference trees (`docs/topics/behavior_logic/`; subtree map in
`notes/bt-integration.md`). Never call the consequence procedurally after
`bridge.execute_with_setup()` returns (BT-06-005, BT-06-006): a post-BT call
is invisible in the tree, so the implementation diverges from the protocol
model and the causal chain cannot be audited.

A cascade step that needs a human or policy decision may expose a trigger
(e.g., `accept-case-invite`) for an operator, but the automated path must not
depend on it.

---

## Missing Cascade vs. Harness Race

Both show up in CI as a scenario step that did not see its effect; diagnose
which one you have before fixing it.

- **Missing cascade** (this note): the consequence never fires. Fix: a BT
  subtree.
- **Harness race**: the consequence fires asynchronously and the scenario
  advances before it lands. Fix: gate the step on evidence its antecedent
  committed (`notes/event-driven-control-flow.md` § "Temporal Sequence vs.
  Causal Sequence", EDF-06, ADR-0058), or, when the effect can be lost rather
  than delayed, actor-side buffering (ADR-0037, ADR-0059).
