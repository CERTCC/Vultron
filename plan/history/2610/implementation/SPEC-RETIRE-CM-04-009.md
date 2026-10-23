---
source: SPEC-RETIRE-CM-04-009
timestamp: '2026-10-08T17:58:31.173960+00:00'
title: Retired requirement CM-04-009
type: implementation
---

Retired CM-04-009 from `specs/case-management.yaml` (#4292).

Why: ADR-0122 rev 2 retires the two-audience rule: an Accept(Invite(EmbargoEvent)) writes only the sender's consent row (MSM-07-003), and the case owner's Accept(EmbargoEvent, target=Case) writes the register and the owner's row together (MSM-07-008), so 'at most one per accept event' no longer describes either message.

Replacement: MSM-07-008

Final text: `plan/retired-specs/CM-04-009.md`.
