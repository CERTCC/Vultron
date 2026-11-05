---
source: CONCERN-5856
timestamp: '2026-11-05T15:07:50.185977+00:00'
title: MV-10-010 supersedes MV-10-009 but its rationale says it does not, and it overlaps
  AKM-05-017
type: learning
---

Theme: theme:requirements-traceability — the actor-reference rule is stated once, and its relation to the partial-object rule says what the text says.

## Summary

- MV-10-009 (MUST): for an object type other than a case not inlined in full, the sender MUST reference it by URI or an AS2 `Link`, not by a partial inline object.
- MV-10-010 (MAY): a sender MAY send an actor known only by URI as an inline object with exactly its `id` and `type` (AKM-05-017).
- AKM-05-017 (MUST): a sender holding only an actor's URI MUST carry an actor reference (an inline object with exactly `id` and `type`).

The SR-13 audit (PR #5853, #5212) recorded MV-10-010 `supersedes` MV-10-009, following #5843's AKM-05-017 `supersedes` MV-10-009. But MV-10-010's rationale says an actor reference "is not a partial object under MV-10-009", which says MV-10-009 never applied, so nothing is superseded. MV-10-010 (MAY) also covers the same case as AKM-05-017 (MUST) at a weaker priority.

## Surface Symptom vs. Underlying Problem

Surface: a link type that disagrees with one sentence of rationale.
Underlying: two readings of whether an actor reference is a partial object, and two requirements with different priorities for one sender behavior. The AKM-05-017 rule (the MUST) looks correct and should stay.

## Category

Spec contradiction / duplicate requirement.

## Severity

Low to medium. The MAY and the MUST give different answers to "may a sender send the bare URI?".

## Evidence

- `specs/message-validation.yaml`: MV-10-009, MV-10-010.
- `specs/actor-knowledge-model.yaml`: AKM-05-017.
- PR #5853 body, "Open questions for the maintainer".

## Impact if Ignored

An implementer reads MV-10-010 as permission to send a bare URI where AKM-05-017 requires an actor reference, and the `supersedes` edges describe a relation the rationale denies.

## Suggested Action

Decide whether an actor reference is an exception to MV-10-009 or outside it. Then align MV-10-010's rationale with its link (or retype the link), and retire MV-10-010 in favor of AKM-05-017 or state what MV-10-010 adds.

**Resolved**: 2026-11-05. The docs PR carries the whole fix; no implementation issues were needed. MV-10-009 now names the actor reference (AKM-05-017) as its one exception: its `type` lets a receiver route the activity, and the receiver fetches the profile before processing it (AKM-05-007). AKM-05-017 keeps `supersedes` MV-10-009. MV-10-010 is retired, with AKM-05-017 as its replacement.

Docs PR: https://github.com/CERTCC/Vultron/pull/5905.
