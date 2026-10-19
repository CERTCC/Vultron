---
source: CONCERN-4866
timestamp: '2026-10-19T14:09:53.567556+00:00'
title: Received activities archived under the sender's id are read as the actor's
  own sent activities
type: learning
---

## Concern

Inbox ingress still archives every received activity in the receiver's store under the sender's own activity id (`_store_inbox_activity`, `vultron/adapters/driving/fastapi/inbox_storage.py`).

\#4834 stopped storing the *inline objects* (IO-03-004), but the activity row itself stays, and it shares the type tables the actor's own sent activities live in.

Two core reads treat a stored activity of a type as evidence of what *this actor sent*, and cannot tell a received archive row from a sent one:

- `case_is_announced` (`vultron/core/behaviors/case/nodes/proposal_retry_marker.py`) answers "is a `Create` naming this case stored?" by scanning `list_objects("Create")` for `context == case_id`. Any received `Create(...)` whose `context` names the case satisfies it, so `CheckCaseAlreadyAnnouncedNode` can skip the CASE_MANAGER's own `Create(VulnerabilityCase)`.
- The derived-id read beside it (`PendingCreateCaseActivity.create_activity_id(proposal_id)`) reads an id a sender can choose for a delivered activity, so a delivery under that id is read as the CASE_MANAGER's own answer.
- `find_case_create_sent_by` (`vultron/core/services/case_replica_seeding.py`) filters on `actor == self.actor_id`; a delivered activity whose `actor` names the receiver (no signatures yet, #2841) passes.

`IntakeReceivedActivityNode` already archives under a receiver-derived key (`ReceivedActivityRecord.build_id`) for exactly this reason: "a sender's choice of id can collide with nothing but its own earlier delivery".
The ingress row is the remaining sender-keyed copy.

Found during the AC-3 audit for #4674. Not a CASE_MANAGER trust check, so outside that issue's scope; severity looks low (the derived id needs the proposal id; the `actor` forgery is the general #2841 limit).

## Possible directions

- Make "did I send it" reads consult the outbox / a sent-activity record only, never the type tables the inbox archive also writes.
- Or move the ingress archive row off the sender's id (related: #3762, a resend reusing an id with a different body).

Governing specs: IO-03-004, CLP-10-017, CP-05-005

Where: vultron/adapters/driving/fastapi/inbox_storage.py

**Resolved**: 2026-10-19 — implementation tracked in #4869, #4870, #4871.
Docs PR: <https://github.com/CERTCC/Vultron/pull/4876>.
Spec: `specs/datalayer.yaml` (DL-06-006; IE-10-001 in `specs/inbox-endpoint.yaml` amended).
Notes: `notes/datalayer-design.md`.
