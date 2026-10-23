---
source: NOTES-case-state-model--case-object-documentation-vs-implementation-gap
timestamp: '2026-10-02T16:24:11.617843+00:00'
title: 'Case Object: Documentation vs. Implementation Gap'
type: note
---

**Archived:** 2026-10-02
**Reason:** delivered/confusion-resolved — docs/howto/case_object.md is now a moved stub pointing to docs/topics/case_lifecycle/case_model.md, which documents the AS2-based case model
**Superseded by:** docs/topics/case_lifecycle/case_model.md

---

## Case Object: Documentation vs. Implementation Gap

### Original Design (`docs/howto/case_object.md`)

The how-to doc describes a UML class diagram for a `Case` object with:

- `em_state: EMStateEnum` (embargo management state)
- `pxa_state: PXAStateEnum` (public/exploit/attack state)
- `Participant` with `rm_state: RMStateEnum` and `vfd_state: VFDStateEnum`
- `VendorParticipant` and `DeployerParticipant` subclasses
- `Message`, `LogEvent`, `Report` associations

This design was written before the ActivityStreams vocabulary was adopted.

### Current Implementation (`vultron/core/models/case.py`)

`VulnerabilityCase` is a Pydantic model extending `CoreObject`, the one AS2
object root of the core model (ADR-0099 detail 4, ARCH-12-002). There is no
separate wire class: `as_VulnerabilityCase` in
`vultron/wire/as2/vocab/objects/vulnerability_case.py` is an alias of the core
class (ADR-0099 detail 3). It incorporates:

- `case_participants` — `CaseParticipant` objects or their IDs
- `case_statuses` — `CaseStatus` objects or their IDs (append-only history)
- `active_embargo` — an inline `EmbargoEvent` (or its ID), plus
  `proposed_embargoes` as IDs
- `vulnerability_reports` — `VulnerabilityReport` objects or their IDs
- `case_activity` and `notes` — activity and note IDs

The VFD/PXA state tracking is embedded in `CaseStatus` and `CaseParticipant`
objects, not directly on the case. This reflects the ActivityStreams-first
design.

**Documentation debt**: `docs/howto/case_object.md` needs updating to reflect
the ActivityStreams-based implementation. Not high priority, but should be
addressed before the prototype is considered stable. When updating, preserve
the UML diagram concept while replacing the class names with their
ActivityStreams equivalents.

---
