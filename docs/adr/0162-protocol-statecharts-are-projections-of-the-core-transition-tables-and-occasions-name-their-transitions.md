---
status: proposed
date: 2026-10-27
created: 2026-10-27
updated: 2026-10-27
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0060, ADR-0122, ADR-0128, ADR-0130; specs/state-machine.yaml
  SM-02, SM-10; specs/message-semantics-mapping.yaml MSM-06, MSM-08;
  specs/em-behavior.yaml EMB-18; issue #5172
informed: []
stakeholder_type: [project-contributor]
---

# Protocol Statecharts Are Projections of the Core Transition Tables, and Occasions Name Their Transitions

## Context and Problem Statement

Each occasion in the semantic registry states the sender's situation and the wire activity that conveys it ([ADR-0128](0128-message-vocabulary-docs-are-projections-of-the-semantic-registry.md)).
It does not name the RM, EM, CS or PEC transition it carries.
Its effect ("moves the sender's RM state to Valid") is prose in its description, so the effect can drift from the transition tables in `vultron/core/states/` and no check sees it.
The state diagrams under `docs/topics/process_models/` and on the protocol specification pages are hand-written mermaid, and no check holds them to the tables either.

How do the protocol's state machines get a representation that the occasions can refer to and the documentation can be generated from, without giving the protocol's state behaviour a second owner?

## Decision Drivers

- Every fact has one owner, and documentation is a projection of the code ([ADR-0128](0128-message-vocabulary-docs-are-projections-of-the-semantic-registry.md)).
- The transition tables in `vultron/core/states/` are what receivers enforce, including the EM table that the embargo register is checked against (EMB-18-006).
- A statechart is a standard notation for `event [condition]` transitions, and a chart file could later describe the protocol outside this codebase.
- The core layer must not depend on the message vocabulary, which sits above it in the semantic registry.
- Conformance checking and running the charts are out of scope for now.

## Considered Options

- Charts generated from the core tables; occasions name their transitions
- Hand-written charts as the source; the core tables checked against them or generated from them
- No charts; occasions name their transitions and the docs are generated from the tables directly

## Decision Outcome

Chosen option: "Charts generated from the core tables; occasions name their transitions", because it keeps the transition tables the single owner of the protocol's state behaviour, gives the occasions a target to refer to, and yields a chart file in a standard notation as a by-product.

### The pipeline runs one way

Core transition tables → generated statecharts → occasions that name chart transitions → generated documentation.
No later stage writes an earlier one.

### Charts are generated and committed

A generator writes one statechart per machine in Sismic's YAML format: RM, the vendor fix path (VF), the deployer path (D), the public state (PXA), EM, and PEC.
One PEC chart describes one consent row, since consent is held per (participant, embargo register entry) ([ADR-0122](0122-per-embargo-participant-consent.md)).
The embargo register is the stored data EM is computed from ([ADR-0130](0130-em-is-computed-from-the-embargo-register-under-the-em-transition-table.md)), not a machine of its own, so it gets no chart.
The charts are committed and gated by a `--check` hook that regenerates them and fails on any difference, as the occasion YAML is.
They hold states, the initial and final states, and transitions with an event, a target and, where needed, a named condition.
They hold no send actions: which message a transition carries is the occasion's fact, read when the documentation is generated.

### EM's register-dependent moves are named conditions

The EM table is not deterministic on its trigger alone: from Proposed, a rejection returns to None only when it removes the last open proposal, and otherwise EM stays in Proposed; acceptance and Revise behave the same way.
The EM chart charts every move of the table, telling the alternatives apart by a named condition such as "last open proposal".
A named condition is a name defined in prose, not an expression in any language, so the chart stays independent of this implementation.

### Occasions name their transitions

An occasion that moves a machine declares the transition it carries, by the machine's trigger, and whose state moves: the sender's, the receiver's, or the case's.
"Whose" is declared rather than derived, because no rule on the machine alone gives it: a report submission moves the receiver's RM, not the sender's, and a participant's public-state observation is adopted into the case's state.
A declaration is checked against the table (the trigger exists on that machine) and against the scoping rules (a participant-specific machine never moves the case's state, and a participant-agnostic machine never moves a participant's).
An occasion that moves no machine, such as a note or a ledger replication, declares none.

### Documentation is generated from the charts and the occasions

Each occasion's section gains an effect line generated from its declared transition, which replaces the effect wording typed into its description.
The state diagrams on the process-model and protocol specification pages are generated from the charts as mermaid, with each transition labelled by the messages whose occasions name it.

### Tooling

Sismic is a dev-only dependency, used by a test that loads every generated chart, so a key the generator writes wrong fails a test.
The `transitions` library stays the runtime state-machine library (SM-02-001).
An export to SCXML, the W3C statechart format, is left for later; the charts' vocabulary has a one-to-one SCXML form.

### Consequences

- Good, because an occasion's effect and the state diagrams can no longer drift from the tables receivers enforce.
- Good, because the protocol's state behaviour gets a file in a standard notation that a later decision can publish.
- Good, because the core layer stays independent of the message vocabulary.
- Bad, because a chart cannot be read on its own to learn which message a transition carries; that needs the occasions.
- Bad, because the Sismic YAML schema is held only by a dev-only test, not by the generator's types.
- Neutral, because Sismic is LGPL-3.0, which a dev-only tool that nothing ships with leaves without effect on what is distributed.

## Validation

- The `--check` hook fails when a committed chart differs from a fresh generation.
- A test loads every generated chart with Sismic.
- A test fails when an occasion names a trigger its machine does not have, or declares whose state moves against the scoping rules.
- The generated effect lines and diagrams are committed fragments under the same `--check` gate.

## Pros and Cons of the Options

### Charts generated from the core tables; occasions name their transitions

- Good, because the tables stay the one owner, as ADR-0128 requires of every fact.
- Good, because the charts cost nothing to keep current.
- Bad, because the charts describe only what the tables describe; a chart cannot lead the code.

### Hand-written charts as the source

The issue's prototype: an RM chart written by hand, with the Python table checked against it.

- Good, because a chart could be authored and versioned apart from this implementation.
- Bad, because the protocol's state behaviour then has two owners, a chart and the table receivers enforce, and one of them is checked against the other instead of derived.
- Bad, because the EM table's register-dependent moves are hard to hand-write correctly and easy to leave out.

### No charts

- Good, because it adds no file format and no dependency.
- Bad, because the documentation generators would each read the Python tables in their own way, and no representation would exist that could describe the protocol outside this codebase.

## More Information

This decision extends [ADR-0128](0128-message-vocabulary-docs-are-projections-of-the-semantic-registry.md): the charts are one more projection, and the occasion gains one more human-supplied fact.
Running the charts, and checking an implementation against them, are left for a later decision.

Generated spec requirements: `message-semantics-mapping.yaml` MSM-08-012, MSM-08-013, MSM-08-014; `state-machine.yaml` SM-11-001 through SM-11-005.
