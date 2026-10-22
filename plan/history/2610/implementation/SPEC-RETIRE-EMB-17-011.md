---
source: SPEC-RETIRE-EMB-17-011
timestamp: '2026-10-22T13:40:06.775625+00:00'
title: Retired requirement EMB-17-011
type: implementation
---

Retired EMB-17-011 from `specs/em-behavior.yaml` (#5039).

Why: Its premise is reversed: the re-invite has no semantic type of its own. ADR-0152 makes it a relayed Invite(EmbargoEvent), attributedTo the embargo's proposer and committed as invite_to_embargo_on_case, which a replica applies through the relay slot; EMB-17-003 now states that.

Replacement: EMB-17-003

Final text: `plan/retired-specs/EMB-17-011.md`.
