---
source: CONCERN-5172
timestamp: '2026-10-27T15:07:39.562059+00:00'
title: Occasions don't reference the state-machine transitions they carry
type: learning
---

## Summary

Each occasion in the semantic registry describes the sender's situation and the wire activity that carries it, but does not reference the RM, EM or CS transition it causes. Its guard and effect live only in prose or in `vultron/core/states/*.py`. Evaluate representing the protocol machines as statecharts (candidate: [Sismic](https://github.com/AlexandreDecan/sismic) YAML, restricted to a small guard and action vocabulary), with occasions pointing to their transitions.

## Surface Symptom vs. Underlying Problem

**Surface:** the occasion tables could use a more standard notation, such as event-condition-action (ECA) rules or a statechart.

**Underneath:** an occasion is the bridge from a formal communicating finite state machine (Brand–Zafiropulo) message to its AS2 wire form, and it has no link to the machine. So the effects it describes ("moves the sender's RM state to Valid") can drift from the code unchecked, and the protocol's state behaviour can't be shared apart from our Python code. ECA is the weaker fit: it renames the table's columns and has no idea of who owns which state. Statechart transitions (`event [guard] / action`) map directly, and `StateContext` is already a guard.

**Leave alone:** the human-readable "When… / Send / Send to" tables, the typed distinguishers (`FieldValue`, `StateContext`, `SenderStanding`), and ADR-0128's rule that the docs are generated from the registry. The glossary's "an occasion is not an event" stays: the chart's event is the trigger, and the occasion is the send it causes.

## Category

- [ ] Top risk
- [x] Technical debt
- [ ] Security
- [ ] Performance / scaling
- [ ] Fragile / high-churn area
- [ ] Other

## Severity

low

## Evidence

- `vultron/semantic_registry/_occasion.py` — `Occasion` (no transition reference; effect only in `description`), `StateContext` (source-state guard, used only to tell occasions apart)
- `vultron/core/states/rm.py` — `_transitions`; no `SemanticEntry` or `Occasion` refers to `RM_Trigger` or `EM_Trigger`
- `docs/reference/formal_protocol/protocol_definition.md` — the protocol is defined as communicating finite state machines
- `docs/topics/process_models/**` — hand-written mermaid `stateDiagram` pages
- docs/adr/0128 — "every fact has one owner"; the drift it fixed for shorthands can recur for effects
- Prototype (Sismic 1.6.11, run with `uv run --with sismic`, no dependency added): an RM chart written as YAML matched `rm._transitions` in both directions; `send('RV')` actions plus `Interpreter.bind()` produced `['RV','RA','RC']` for receive → validate → accept → close; an illegal `accept` from RECEIVED was not consumed; `export_to_plantuml` works (no mermaid export).

<details><summary>Prototype RM chart</summary>

```yaml
statechart:
  name: RM (one participant)
  root state:
    name: RM
    initial: START
    states:
      - name: START
        transitions:
          - {target: RECEIVED, event: receive}
      - name: RECEIVED
        transitions:
          - {target: VALID, event: validate, action: "send('RV')"}
          - {target: INVALID, event: invalidate, action: "send('RI')"}
          - {target: CLOSED, event: close, action: "send('RC')"}
      - name: INVALID
        transitions:
          - {target: VALID, event: validate, action: "send('RV')"}
          - {target: CLOSED, event: close, action: "send('RC')"}
      - name: VALID
        transitions:
          - {target: ACCEPTED, event: accept, action: "send('RA')"}
          - {target: DEFERRED, event: defer, action: "send('RD')"}
      - name: ACCEPTED
        transitions:
          - {target: DEFERRED, event: defer, action: "send('RD')"}
          - {target: CLOSED, event: close, action: "send('RC')"}
      - name: DEFERRED
        transitions:
          - {target: ACCEPTED, event: accept, action: "send('RA')"}
          - {target: CLOSED, event: close, action: "send('RC')"}
      - name: CLOSED
        type: final
```

</details>

## Impact if Ignored

Occasion descriptions and the state machines can disagree silently. State diagrams stay hand-written. Other implementers get no portable model of the protocol's state behaviour, only our Python code.

## Suggested Action

Analysis before any tasks. Answer:

1. How many occasions map to exactly one machine transition, and how many carry none (create report, notes, ledger replication, acknowledgments)?
2. Which machines can be charted (RM, EM, CS VFD/PXA) and which can't (append-only embargo register, per-entry participant consent)? Per-participant machines become one chart with one interpreter per participant.
3. Should the chart be the source for `_transitions`, or checked against it? A chart can't be the source if the behavior trees rely on paths the formal model lacks (e.g. `rm_closure_path`).
4. Guard and action vocabulary: restrict to `send('X')`, `active('State')` and named predicates so charts stay implementation-independent and runnable under `DummyEvaluator`. Is a later SCXML export (the W3C standard; Sismic doesn't read or write it) a requirement?
5. Dependency: Sismic is LGPL-3.0. Approve it as a dev/docs-only dependency, keeping `transitions` at runtime?

Then draft an ADR amending ADR-0128 (who owns the protocol charts, and how occasions refer to them) and split the work into tasks: RM chart plus conformance test → occasions refer to transitions → generated effect text → mermaid projections → EM/CS charts → optional checks of protocol properties.

**Resolved**: 2026-10-27 — implementation tracked in #5258, #5259, #5260, #5261, #5262.
Docs PR: <https://github.com/CERTCC/Vultron/pull/5257>.
ADR: `docs/adr/0162-protocol-statecharts-are-projections-of-the-core-transition-tables-and-occasions-name-their-transitions.md`.
Spec: `specs/state-machine.yaml` (SM-11), `specs/message-semantics-mapping.yaml` (MSM-08-012 to MSM-08-014).

Decisions from the interview: charts are generated from the core transition tables (presentation path, not a second source of truth); Sismic YAML now, SCXML later; EM register-dependent moves are named conditions; occasions own the transition link and declare whose state moves; charts hold no send actions; Sismic is dev-only; conformance checking is out of scope.
