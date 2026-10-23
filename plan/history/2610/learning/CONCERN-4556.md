---
source: CONCERN-4556
timestamp: '2026-10-14T16:44:14.553880+00:00'
title: 'A participant at RM CLOSED can still have acts recorded: sender guards do
  not check closure'
type: learning
---

## Problem

The sender guards accept an act from a participant at RM `CLOSED`. A participant that has left can still have an act recorded while the case is open.

- `notes/case-joining.md` § "Authority to act" says a participant at RM `CLOSED` "may act on nothing further, because `CLOSED` is terminal".
- The guards in `vultron/core/behaviors/sender_entitlement.py` (for example `SenderIsActiveLedgerParticipantNode`, the `ACTIVE_PARTICIPANT` arm of the CASE_MANAGER relay check, and the note-author check) call `is_case_content_recipient()` in `vultron/core/participants/recipients.py`.
- `is_case_content_recipient()` checks only `VulnerabilityCase.is_active_participant()`. That check does not include RM `CLOSED`. So a closed participant's `Add(Note)`, status update, or `Reject(CaseLedgerEntry)` passes the guard.

## Why it matters

Since #4212, the CASE_MANAGER sends a closed participant no case content after the entries that record its own closure (CM-23-004). A closed participant can therefore still write to the case, but it never sees the result or anything that followed. CM-23-013 refuses external writes only after `case_fully_closed`, not after one participant's own closure.

## Evidence

- `is_case_content_recipient()` docstring (after #4212): it does not apply the RM `CLOSED` filter, because a closed participant may still Reject for a replay of its own closure entries. The replay is capped instead (`closed_participant_ledger_cutoff()`).
- No requirement in `specs/` states that the CASE_MANAGER refuses an act from a participant at RM `CLOSED`. A search for "closed participant" finds only the receive-side rules (CM-23-004, CM-31-009).

## Decision needed

1. Add a requirement and a guard: refuse every act from a sender at RM `CLOSED` except a `Reject(CaseLedgerEntry)` for its own closure entries (and a repeated `Leave`).
2. Keep accepting acts from a closed participant until `case_fully_closed`, and correct the note.

Recommendation: option 1. It matches "CLOSED is terminal" and ADR-0114.

Source: found while building #4212.

**Resolved**: 2026-10-14 — implementation tracked in #4615; #4522 gained AC-3 and AC-4 for the note and `Leave` declarations.
Planning found the gap is wider than reported: `SenderIsActiveParticipantNode` checks only roster membership, so inert, removed and closed senders all pass it. A repeated `Leave` is decided by effect (`SKIPPED` whatever its activity id), not by activity id.
Docs PR: <https://github.com/CERTCC/Vultron/pull/4614>.
Spec: `specs/case-management.yaml` (CM-23-018).
Notes: `notes/case-joining.md` § "Authority to act".
