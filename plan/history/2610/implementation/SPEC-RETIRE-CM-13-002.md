---
source: SPEC-RETIRE-CM-13-002
timestamp: '2026-10-08T17:57:50.478319+00:00'
title: Retired requirement CM-13-002
type: implementation
---

Retired CM-13-002 from `specs/case-management.yaml` (#4292).

Why: ADR-0122 rev 2 retires the two-audience rule: the case owner's decision for the case is Accept(EmbargoEvent, target=Case) (MSM-07-008), and Accept(Invite(EmbargoEvent)) is always the sender's own consent (MSM-07-003), so no handler branches on whether the sender is the owner.

Replacement: MSM-07-008

Final text: `plan/retired-specs/CM-13-002.md`.
