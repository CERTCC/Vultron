---
source: IDEA-602
timestamp: '2026-08-27T20:27:09.622332+00:00'
title: '[Docs] Audit howto/activitypub/ for accuracy against current implementation'
type: idea
---

Full audit of `docs/howto/activitypub/activities/` against the current implementation (all 49 ActivityPatterns, 50+ MessageSemantics, 14 demo scripts).

## Outcome

Identified 4 stale/inaccurate existing pages and 4 missing message-type flows. Decomposed into 5 context-grouped implementation issues.

## Stale/inaccurate pages

- `_reengage_case.md` calls `reengage_case()` which returns `as:Undo` — MUST use `as:Join` per `notes/activitystreams-semantics.md`; this also removes a premise in #2214
- `invite_actor.md` sequence diagram shows direct Owner→Actor routing — demo routes through CaseActor when available (PCR-08-008)
- `manage_participants.md` same direct routing issue as `invite_actor.md`
- `transfer_ownership.md` shows P2P routing — BT nodes already emit to CaseActor per ADR-0053 (PR #2044); docs should target the correct model

## Missing message-type coverage

- CaseProposal flow: `CreateCaseProposal`/`AcceptCaseProposal`/`RejectCaseProposal` (ADR-0023; demo + vocab examples exist)
- Ledger replication: `AnnounceLogEntry`/`RejectLogEntry` + `AnnounceVulnerabilityCase` (ADR-0077)
- Role delegation: `OfferCaseParticipantRole`/Accept/Reject (ADR-0039; factories exist)

## Implementation issues

- Issue A (size:M): Fix accuracy errors in existing howto pages
- Issue B (size:S): New howto page — CaseProposal flow (ADR-0023)
- Issue C (size:M): New howto pages — ledger replication + Announce(VulnerabilityCase)
- Issue D (size:S): New howto page — role delegation (OfferCaseParticipantRole, ADR-0039)
- Issue E (size:M): Implement ADR-0053 compliance in demo layer

PR: (pending)
