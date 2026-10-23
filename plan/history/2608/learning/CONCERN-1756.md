---
source: CONCERN-1756
timestamp: '2026-08-05T21:25:30.896377+00:00'
title: invited participants must follow full RM lifecycle from RM:RECEIVED
type: learning
---

## Summary

Participants who join a case via invite-and-accept go directly to participation status without running the RM lifecycle from RM:RECEIVED. The protocol requires that all participants — regardless of how they joined — complete the VALID/INVALID and then ACCEPTED/DEFERRED transitions before being treated as committed participants.

## Surface Symptom vs. Underlying Problem

**Surface:** In the FVCV-handoff demo, Vendor2 accepts an invite and becomes a participant with no explicit validation step — no RM:RECEIVED → RM:VALID → RM:ACCEPTED transition is demonstrated.

**Deeper problem:** Accepting a case invite should place the joining participant at RM:RECEIVED, after which they are responsible for running the standard RM triage cycle. This is required protocol behavior for all participants, but it was not enforced or demonstrated for invite-joining participants. CM-11-001 in the spec incorrectly stated that Accept(Invite) MUST advance the invitee to RM.ACCEPTED, conflating two distinct protocol acts: joining the case and validating its vulnerability content. An invited participant has seen only a redacted/stub view of the case when they accept — they cannot be in RM.ACCEPTED before reviewing the full case.

## Resolution

**Resolved**: 2026-08-05 — implementation tracked in #2017, #2018, #2019.
Docs PR: <https://github.com/CERTCC/Vultron/pull/2014>.
Spec: `specs/case-management.yaml` CM-11-001 through CM-11-004 (corrected).
Notes: `notes/case-state-model.md` § "Invite-Path Participant RM Entry Point".
