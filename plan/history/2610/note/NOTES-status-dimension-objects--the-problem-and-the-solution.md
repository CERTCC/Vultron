---
source: NOTES-status-dimension-objects--the-problem-and-the-solution
timestamp: '2026-10-12T19:34:07.408940+00:00'
title: 'The Problem / The Solution: Dimension Objects'
type: note
---

**Archived:** 2026-10-12
**Reason:** rationale for the delivered ADR-0036 design; the ADR records it
**Superseded by:** docs/adr/0036-status-dimension-objects.md; vultron/core/models/case_status.py

---

## The Problem

`CaseStatus` and `ParticipantStatus` pack several independent state machines
into flat enum fields:

```python
# CaseStatus (before)
em_state: EM = EM.NONE
pxa_state: CS_pxa = CS_pxa.pxa

# ParticipantStatus (before)
rm_state: RM = RM.START
vfd_state: CS_vfd = CS_vfd.vfd
em_consent_state: PEC | None = None
```

These machines are genuinely independent, but callers must know:

- *which external service* handles each transition (EM + PEC → `EmbargoLifecycle`;
  RM/vfd → BT nodes or `EmbargoLifecycle` indirectly; PXA → BT lifecycle nodes).
- *which guards apply* before calling (P/X/A embargo-eligibility checks, RM
  terminal guards, etc.).

There is no single, self-describing owner per machine. Bugs fixed in
`EmbargoLifecycle` do not automatically close gaps in BT nodes that
independently mutate `em_state`.

---

## The Solution: Dimension Objects

Decompose each machine into a small Pydantic `BaseModel` — a *dimension object*
— that holds one state enum field and owns:

- An immutable `transition(trigger)` method that validates the trigger,
  applies the machine rules, and returns a **new** dimension object.
- Guard predicates as methods (`is_validated()`, `is_active()`, etc.).

```python
# CaseStatus (after)
em: EmDimension = Field(default_factory=EmDimension)
pxa: PxaDimension = Field(default_factory=PxaDimension)

# ParticipantStatus (after — ADR-0036 original; ADR-0075 then split vfd into vf+d)
rm: RmDimension = Field(default_factory=RmDimension)
vf: VfDimension | None = None   # non-None for VENDOR participants
d: DDimension | None = None     # non-None for DEPLOYER participants
# No consent field: participant embargo consent is per-embargo rows on CaseParticipant (ADR-0122)
```

---
