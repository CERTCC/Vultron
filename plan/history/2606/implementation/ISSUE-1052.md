---
source: ISSUE-1052
timestamp: '2026-06-19T03:36:49.675682+00:00'
title: Migrate AddNoteToCase, CloseCase, OfferCaseManagerRole to single-BT pattern
type: implementation
---

## Issue \#1052 — Single-BT migration: AddNoteToCase, CloseCase, OfferCaseManagerRole

Migrated three received-side use cases to the ADR-0022 "single-BT execution per
inbox delivery" pattern, completing the ratchet started in #1050 (embargo) and
\#1051 (report/status). `KNOWN_VIOLATIONS` is now `frozenset()`.

**Architecture fix:** `AddNoteToCaseReceivedUseCase` previously called
`_broadcast_note_to_participants` which emitted `AddNoteToCase` directly from
the CaseActor to participants — a violation of `notes/case-communication-model.md`.
The broadcast is removed; `Announce(CaseLedgerEntry)` fan-out via `sync_port`
is the correct notification mechanism (SYNC-02-002).

**New tree factories:**

- `create_add_note_to_case_received_tree()`: `AttachNoteToCaseNode` + guarded commit
- `create_close_case_received_tree()`: `StoreActivityNode(Leave)` + guarded commit
- `create_offer_case_manager_role_received_tree()`: `StoreActivityNode` +
  `AutoAcceptOrSkip` Selector + conditional guarded commit

**New BT node:** `AutoAcceptCaseManagerRoleNode` calls
`trigger_activity_factory.accept_case_manager_role()` + `record_outbox_item()`.

**Port factory:** Moved `ADD_NOTE_TO_CASE` from `_SYNC_AND_TRIGGER_PORT_SEMANTICS`
to `_SYNC_PORT_SEMANTICS` (no longer needs `trigger_activity`).

**Tests:** Cleared `KNOWN_VIOLATIONS`, removed 3 architecture-violating broadcast
tests, updated all callers to remove `trigger_activity` arg and add
`receiving_actor_id` where required. 3434 tests pass.

PR: [#1066](https://github.com/CERTCC/Vultron/pull/1066)
