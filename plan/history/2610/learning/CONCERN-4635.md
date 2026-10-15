---
source: CONCERN-4635
timestamp: '2026-10-15T13:44:19.647921+00:00'
title: Should the protocol support both a direct Add and a separate Create then Add
  for statuses, embargo events and participant records?
type: learning
---

## Summary

Issue #4598 removed four received routes from this implementation: `Create(CaseStatus)`, `Create(ParticipantStatus)`, `Create(EmbargoEvent)` and a direct `Create(CaseParticipant)`. Each stored the object it carried with no ledger entry, and nothing in the system sent them except one demo. The demos now send the status inline on the `Add` that attaches it, and an embargo proposal carries its `EmbargoEvent` inline on the `Invite`

That is a choice this prototype made, not a requirement of the protocol. The maintainer's decision on #4598 is explicit: removing the routes does not disallow the mechanism. Docs say "not supported by this implementation", never "invalid".

## Surface symptom vs. underlying problem

- **Surface reading:** the routes were dead code, so they were removed.
- **Underlying question:** whether the Vultron protocol should let a participant mint an object with `Create` and attach it later with `Add` (two messages), as well as attach it directly with one `Add` that carries it inline. ActivityStreams allows both. The `Create(Note)` then `Add(Note)` pair already works this way, and `Create(Note)` is ledgered.

## What a "yes" would need

If the protocol should support the separate `Create`, each `Create(X)` for a case record is a change to the case file, so it needs its own committed ledger entry (CLP-07-013) and a replica apply node or a declared no-replica-effect row (RSH-08-004), and the `Add` that follows must resolve a reference to the stored object. A "no" means the docs can state the single-`Add` form as the protocol's, not only this implementation's.

## Evidence

- `docs/topics/future_work/_oq-create-then-add.md` records this open question, included on the Open Questions page and on Activity Vocabulary Design.
- Retired specs: VAM-05-001, VAM-06-001, VAM-08-001, VAM-08-003 (`plan/retired-specs/`).

Category: protocol design. Severity: low; nothing in the system needs the separate `Create` today.

Governing specs: CLP-07-013, RSH-08-004

**Resolved**: 2026-10-15 — implementation tracked in #4678.
The maintainer decided at the project level: this prototype attaches each of
these objects by a single `Add` (or the `Invite`) and the removed `Create`
routes do not come back (VAM-01-010). At the protocol level the choice between
single `Add` only, `Create` then `Add`, and a `Create` whose case `context`
attaches the object stays open, tracked as Idea #4676.

Docs PR: <https://github.com/CERTCC/Vultron/pull/4677>.
Spec: `specs/vultron-as2-mapping.yaml`.
