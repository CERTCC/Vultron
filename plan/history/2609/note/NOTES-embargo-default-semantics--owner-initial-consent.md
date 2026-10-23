---
source: NOTES-embargo-default-semantics--owner-initial-consent
timestamp: '2026-09-17T17:22:57.964298+00:00'
title: Case Owner Initial Embargo Consent (BUG-26042204)
type: note
---

**Archived:** 2026-09-17
**Reason:** (a) implemented; owner seeded as SIGNATORY at embargo.py:377 (code cites CM-14-003)
**Superseded by:** vultron/core/behaviors/case/nodes/embargo.py; specs/case-management.yaml CM-14-003

---

## Case Owner Initial Embargo Consent (BUG-26042204, 2026-04-22)

When a case is created with an active embargo (i.e., after the
`InitializeDefaultEmbargoNode` runs and the case reaches `EM.ACTIVE`), the
**case owner** MUST also be seeded as a `SIGNATORY` on the embargo at case
creation.

**Rationale**: The case creator is the case owner by default. It makes no
sense for the case owner to create an active embargo and then be locked out of
their own embargo as a non-signatory until a separate accept step occurs.

**Implementation**: After the default embargo is initialized (EM reaches
`ACTIVE` via the atomic PROPOSE+ACCEPT sequence in `InitializeDefaultEmbargoNode`),
the case owner's `CaseParticipant.embargo_adherence` consent state MUST be
transitioned to `SIGNATORY`. The PROPOSE+ACCEPT transition is an **internal**
atomic operation — it does not go through the receive-side `AcceptEmbargoReceivedUseCase`
path. The participant consent update MUST be applied in the same BT node or an
immediately following sibling node in the same subtree.

**Spec reference**: See `specs/case-management.yaml` CM-13 for the formal
requirement.
