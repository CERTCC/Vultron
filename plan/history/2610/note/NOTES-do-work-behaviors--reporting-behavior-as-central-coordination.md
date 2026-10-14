---
source: NOTES-do-work-behaviors--reporting-behavior-as-central-coordination
timestamp: '2026-10-12T19:35:49.407981+00:00'
title: Reporting Behavior as Central Coordination
type: note
---

**Archived:** 2026-10-12
**Reason:** superseded — party identification and invitation moved to suggest-actor-to-case and a Sentinel capability; the report-to-others tree was removed
**Superseded by:** ADR-0047; `specs/embargo-policy.yaml`; suggest-actor-to-case trigger

---

## Reporting Behavior as Central Coordination

Reporting — sending case information to other actors, inviting them to
participate, and negotiating embargo terms — is the central coordination
activity in CVD and the primary use case for Vultron's protocol messaging.
It is not fully automatable but is well-supported by flows such as:

- Inviting actors to cases (`invite_actor_to_case`)
- Negotiating embargo duration (`invite_to_embargo_on_case`)
- Asking actors to confirm agreement before receiving sensitive details

A key underspecified area is **embargo policy compatibility evaluation**:
before inviting an actor to an embargo, the system should evaluate whether
the actor's declared policy (minimum/maximum duration, preferences) is
compatible with the proposed embargo terms. See `specs/embargo-policy.yaml`
for the specification of the embargo policy record format, and the "Prior Art"
section below for external references.
