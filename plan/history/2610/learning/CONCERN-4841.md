---
source: CONCERN-4841
timestamp: '2026-10-16T20:31:17.972108+00:00'
title: A participant sends Add(CaseStatus) in a guide, a demo and the occasion text,
  but RSH-04-001 reserves it for the CASE_MANAGER
type: learning
---

## Problem

RSH-04-001 (MUST) says only the CASE_MANAGER emits `Add(CaseStatus)` directly. Every other participant MUST embed a suggested `CaseStatus` in `Add(ParticipantStatus)`.

Three places have a non-manager participant send `Add(CaseStatus)`:

- `docs/howto/activitypub/activities/status_updates.md`: "In every case, send `Add(CaseStatus)`".
- The vendor in `vultron/demo/exchange/status_updates_demo.py`.
- The `when` text of the CP/CX/CA occasions on `Add(CaseStatus)` in `vultron/semantic_registry/status.py` ("a Participant learns…").

Found while building #4569 (PR #4840). That PR declares the participant forms as occasions on `Add(ParticipantStatus)` and leaves these three places as they are.

## Decision needed

Should a non-manager participant ever send `Add(CaseStatus)`? If not, the guide, the demo and the occasion text change to the `Add(ParticipantStatus)` form. If so, RSH-04-001 needs an amendment.

Governing specs: RSH-04-001, CSB-15-003, MSM-03-004, MSM-03-005, MSM-03-006, MSM-08-007

**Resolved**: 2026-10-16 — implementation tracked in #4851.
Decision: keep RSH-04-001. The CASE_MANAGER sends `Add(CaseStatus)` only inside a
case ledger entry; the inbox admitting it from any sender (exempt sender check,
no StatusAdoptionGate in `add_case_status_tree`) skips RSH-07-001's owner
approval. New RSH-04-005 has a receiver refuse it from anyone else.
Docs PR: <https://github.com/CERTCC/Vultron/pull/4853>.
Spec: `specs/received-status-handling.yaml`.
Notes: `notes/received-status-authorization.md`.
