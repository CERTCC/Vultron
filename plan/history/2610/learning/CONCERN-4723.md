---
source: CONCERN-4723
timestamp: '2026-10-21T16:42:57.322194+00:00'
title: Give every ledger-written activity a real AS2 shape and a registry semantic
  type
type: learning
---

## Problem

Every case ledger entry carries an AS2 activity in `payloadSnapshot` and a semantic type in `eventType`.
The 2026-10-15 demo UI planning session settled that the semantic registry (`vultron/semantic_registry/`) is Vultron's complete vocabulary: everything Vultron can send, receive, or write to a ledger.
An entry's `eventType` must then be what the registry's matcher returns for its payload.

Today that does not hold:

- About ten ledger-only semantic types have no registry entry and no `MessageSemantics` member. They are module constants or inline strings across `vultron/core/behaviors/**`: `create_case_participant`, `case_fully_closed`, `report_received`, `invite_to_embargo_on_case_expired`, `invite_to_embargo_on_case_expired_noop`, `invite_to_embargo_on_case_reinvite`, `honour_late_accept_invite_to_embargo_on_case`, `accept_actor_recommendation`, `reject_actor_recommendation`, `inbox_event`, and the embargo constants in `event_conditions.py`.
- The invite-expiry entry's payload type is `Expire` (`vultron/core/models/rsvp_deadline.py:52`), which is not an AS2 activity type.
- Some shapes carry more than one semantic type, so no pattern can tell them apart today:
  - the case-closing `Update(VulnerabilityCase)` vs. other case updates
  - an on-time `Accept(Invite(EmbargoEvent))` vs. one honoured late
  - expiry vs. expiry no-op

## Decisions needed (interactive; do not build without them)

1. For each ledger-only semantic type: its AS2 shape, and whether it becomes a `MessageSemantics` member with a `SemanticEntry`.
2. The replacement for `Expire`. Candidates include `Remove(Invite)` or `Reject(Invite)` attributed to the CASE_MANAGER, or an AS2 activity with a distinguishing field.
3. For each colliding shape: put the distinguishing fact in the payload so a pattern can see it, or merge the two semantic types into one.
4. Whether a recognized semantic type with no received handler needs any registry marker. The session's answer was no: the inbox reports "no use case found" and does no permission checks. Confirm that the registry needs nothing extra.

## Context

- Decision record: the new ADR on ledger entries and the vocabulary (drafted alongside ADR-0128).
- Glossary: **Semantic type** in `CONTEXT.md` and `docs/reference/glossary.md`.
- Replica apply nodes match on `eventType` alone (`vultron/core/behaviors/sync/nodes/event_conditions.py`), so the strings themselves need not change.

**Resolved**: 2026-10-21 — implementation tracked in #5037, #5038, #5039, #4724.
Docs PR: <https://github.com/CERTCC/Vultron/pull/5036>.
Rulings recorded in ADR-0152.
