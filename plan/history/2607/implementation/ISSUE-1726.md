---
source: ISSUE-1726
timestamp: '2026-07-31T16:26:09.076814+00:00'
title: Introduce as_CaseParticipantRole wire type and OFFER_CASE_PARTICIPANT_ROLE
  semantic
type: implementation
---

## Issue #1726 — as_CaseParticipantRole wire type and OFFER_CASE_PARTICIPANT_ROLE semantic

Implements ADR-0039: introduces Offer(CaseParticipantRole, target=Actor, context=VulnerabilityCase) as the canonical role-delegation wire format, replacing the deprecated Offer(VulnerabilityCase, target=CaseParticipant) format.

All 8 acceptance criteria met. Code-review FAIL (missing _SYNC_AND_TRIGGER_PORT_SEMANTICS entry) fixed during review. IMPROVE (auto-accept test coverage) also addressed in-session.

PR: <https://github.com/CERTCC/Vultron/pull/1870>
