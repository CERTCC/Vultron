---
status: accepted
status_override: >-
  Decided by the maintainer in the planning interview for #6336 on 2026-11-12.
date: 2026-11-12
created: 2026-11-12
updated: 2026-11-12
revision: 2
amended: "2026-11-13"
deciders: Allen D. Householder
consulted: Vultron maintainers
informed: Vultron implementers
stakeholder_type: [project-contributor]
# CaseReader is the port this record decides; it is named before it exists.
lint_suppress: [phantom_symbol_ref]
---

# An Outside System Reaches the Core Through a Read-Only Case Reader Port

## Context and Problem Statement

The shadow ([ADR-0190](0190-shadow-mode-is-a-standalone-read-only-advisor-that-translates-a-case-on-request.md)) reads a case from an outside system, such as VINCE, and reasons about it with the Vultron engine.
The engine reasons about a case as a case ledger and the snapshot projected from it, so the outside system's case must arrive in that form.

The connector plugin interface assumes a two-way connector that the outside system pushes events into and that Vultron pushes events out of.
A reader that a caller asks for one case, and that must have no write path, cannot satisfy it (#6337).
The plan for #6337 (#6357) split that interface into three directions, a polled source of changes since a bookmark, a push source and an event sink, on the premise that a Sentinel would poll VINCE for a running shadow node.
Under ADR-0190 nothing polls for changes: the shadow reads one whole case on request, which none of the three directions does.
Later work will add a two-way gateway, and other outside systems will add readers of their own.

**Through what interface does an outside system's case reach the core, and what does it arrive as?**

## Decision Drivers

- A case is its ledger and the projection of that ledger. A snapshot alone loses the order and timing the CVD desiderata are about.
- A reader must not be able to write to its outside system.
- Each insight must trace back to the outside-system record it rests on.
- A translation is regenerated whenever it is needed, so it is not stored ([ADR-0190](0190-shadow-mode-is-a-standalone-read-only-advisor-that-translates-a-case-on-request.md)).
- The later gateway, and readers for other systems, should build on this interface rather than replace it.

## Considered Options

Interface:

- One two-way connector interface, which a reader satisfies by refusing every outbound call.
- A read-only case reader port, with a read-write port kept for the later gateway.

Target model:

- Translate the outside system's data into wire activities, then parse them.
- Translate it straight into core domain objects.

Who a translated entry credits:

- The participant who acted in the outside system, with each entry citing its source record.
- The translator, as an observer, with the participant named as the act's subject.
- The participant, inside a ledger marked as a whole as translated.

## Decision Outcome

1. **A read-only case reader port.** The core declares a `CaseReader` port. Given an outside system's case identifier, it returns that case translated. It has no method that writes to the outside system. A read-write port, for the later gateway, is a separate interface and a separate decision. Adapters that implement both may share translation components.
2. **Straight to core.** An adapter translates into core domain objects directly. The core and wire classes are the same classes for domain types ([ADR-0099](0099-one-object-model-as2-is-a-serialization.md)), so a detour through wire adds a parse step and no protection. Where a ledger entry stores an activity payload, the payload is rendered from the core object.
3. **A ledger, projected by the core.** The translation is a case ledger. The snapshot is the core's projection of that ledger, never a second model the adapter builds alongside it.
4. **Entries credit the participant who acted, and cite their source.** A translated entry names as its actor the participant who performed the act in the outside system, and cites the outside-system record it was translated from. The ledger carries no mark that it is a translation, because in this version a translation is not stored and does not enter a protocol path ([ADR-0190](0190-shadow-mode-is-a-standalone-read-only-advisor-that-translates-a-case-on-request.md)).
5. **Nothing untranslatable is dropped.** A fact the adapter cannot translate is returned with the result and shown, never silently left out.
6. **Adapters stay outside the core.** An adapter is a connector plugin: it translates and holds no case logic, and the core never imports it.
7. **A connector's directions are the core ports it implements.** `CaseReader` is the only one today. The three directions #6357 named are removed until a caller needs one; #6357's rules that a connector declares only what it implements, carries no stub for the rest, and is refused by the loader when it implements nothing all stand.

### Consequences

- Good, because the projection and the measures run on a translated case exactly as on a native one, with no second path to keep in step.
- Good, because a reader with no write method cannot write, whatever its adapter does.
- Good, because the later gateway can translate in both directions over the same core model, which is what lets two outside systems reach each other through Vultron.
- Bad, because a translated ledger cannot be told from a native one by looking at it. That is safe only while translations stay ephemeral and outside protocol paths. Persisting one, or feeding one to a protocol path, reopens point 4.
- Good, because a Vultron node can stand behind the same port. An adapter that reads a CASE_MANAGER's case ledger returns native entries, untranslated, so the shadow can show a live Vultron case the same way it shows an outside system's.
- Neutral, because a ledger entry carries a commit stamp and a claimed publication time. Which outside-system field fills each is part of the mapping decision (#5964).

## Validation

`specs/case-reader.yaml` states the checkable rules, each citing this record.
A test of the port asserts it declares no write method.

## Pros and Cons of the Options

### One two-way connector interface

- Good, because there is one interface to discover and document.
- Bad, because a read-only reader must carry an outbound method that refuses every call, which is a write path in the interface.

### A read-only port, with a read-write port kept for later

- Good, because "cannot write" is a property of the type.
- Bad, because the gateway adds a second interface.

### Translate into wire, then parse

- Good, because the parse edge would validate the translation.
- Bad, because core models validate at construction anyway, so the detour adds a step and no check.

### Translate into core directly

- Good, because the translation produces what the engine reads.

### Credit the participant, citing the source record

- Good, because the projection and the measures read the entry with no special case.
- Bad, because the entry's actor did not send it through Vultron, which is acceptable only while the ledger is ephemeral.

### Credit the translator as an observer

- Good, because every entry is literally true of who produced it.
- Bad, because the projection must learn to apply an observed act as the subject's own transition, a second path through the same logic.

### Credit the participant, inside a ledger marked as translated

- Good, because code could refuse a translated ledger on a protocol path.
- Bad, because nothing reads the mark while translations are ephemeral, so it is built ahead of any need.

## Amendment — 2026-11-13

Point 4's last sentence was replaced.
It read: "The ledger carries no mark that it is a translation, because a translation is never stored and never enters a protocol path."
It now reads: "The ledger carries no mark that it is a translation, because in this version a translation is not stored and does not enter a protocol path ([ADR-0190](0190-shadow-mode-is-a-standalone-read-only-advisor-that-translates-a-case-on-request.md))."

The record states what this version does. A later version that stores a translation or feeds one to a protocol path reopens point 4, as the Consequences already say.

- Source: #6336 (PR #6364 review)

## More Information

Planned in #6336, with the maintainer, on 2026-11-12. Revises the connector directions planned for #6337 in #6357.
A narrowing projection the core owns in front of a port is [ADR-0186](0186-one-participant-suggestion-port-narrowed-by-a-core-projection-serves-both-call-out-and-call-in.md).
The measures read a case ledger as JSONL ([ADR-0174](0174-cvd-measures-read-a-case-ledger-through-a-read-only-event-history.md)).

Generated spec requirements: `case-reader.yaml` CRD-01; `architecture.yaml` ARCH-05-004.
