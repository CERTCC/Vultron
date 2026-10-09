---
source: CONCERN-4322
timestamp: '2026-10-08T20:05:36.532252+00:00'
title: Accept/reject embargo triggers cannot name the embargo in force
type: learning
---

## Concern

The accept and reject embargo triggers resolve their target through `_resolve_embargo_proposal` (`vultron/core/use_cases/triggers/_helpers.py`), which only looks in `pending_embargo_proposal_index`.
That index holds open proposals only, and activation removes the entry (EP-08-003), so a participant whose consent row for the embargo in force is `INVITED` (a late joiner, for example) cannot answer that embargo through `trigger/accept-embargo` or `trigger/reject-embargo`.
This predates #4290: the old activation also pruned the index. It surfaced while migrating tests for #4290 (PR #4320), where fixtures had been hand-seeding the active embargo into the index, a state no protocol event produces.

## Question to settle

Is answering the embargo in force meant to go through the full-case Invite (CM-11-018) and the relayed `Invite(EmbargoEvent)` only? Or should the triggers resolve the active embargo too, now that the register makes it addressable (`case.active_embargo_id`)?
Relevant to #4291 (consent rows) and #4292 (owner activities).

Governing specs: CM-11-018, EP-09-011, EP-08-003, MSM-07-003

## Decision

The triggers answer the embargo in force only when the caller names the `Invite(EmbargoEvent)` (explicit id, consent row `INVITED` or `EXPIRED`).
A call that names no Invite keeps selecting among open proposals only (EP-08-002) and never falls back to the embargo in force: answering an embargo is intentional, so the caller knows its parameters.
The full-case Invite carries no embargo consent (CM-11-010, CM-11-011); the issue's CM-11-018 citation was wrong (CM-11-018 refuses a stub Reject with no participant record).

**Resolved**: 2026-10-08 — implementation tracked in #4373.
Docs PR: <https://github.com/CERTCC/Vultron/pull/4372>.
Spec: `specs/embargo-policy.yaml` (EP-09-012).
Notes: `notes/participant-embargo-consent.md`.
