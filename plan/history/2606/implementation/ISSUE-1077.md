---
source: ISSUE-1077
timestamp: '2026-06-22T17:21:54.027669+00:00'
title: migrate 4 received use cases with direct DL mutations to BT leaf nodes
type: implementation
---

## Issue #1077 — Migrate 4 received use cases with direct DataLayer mutations to BT leaf nodes (CLP-10-005 / BT-15-001)

Migrated 5 `execute()` methods across 4 received-side use case files from direct `self._dl.save()`
calls to proper BT leaf nodes accessed via `BTBridge.execute_with_setup()`, in compliance with
BT-06-001, BT-15-001, and CLP-10-005.

Files migrated:

- `received/unknown.py` — `UnresolvableObjectUseCase`: new `StoreDeadLetterRecordNode` + `create_store_dead_letter_tree()`
- `received/case_participant.py` — `AddCaseParticipantToCaseReceivedUseCase` and `RemoveCaseParticipantFromCaseReceivedUseCase`: new add/remove participant nodes and tree factories
- `received/actor/ownership.py` — `AcceptCaseOwnershipTransferReceivedUseCase`: new `AcceptCaseOwnershipTransferNode` + `create_accept_ownership_transfer_tree()`
- `received/actor/announce.py` — `AnnounceVulnerabilityCaseReceivedUseCase`: new `SeedAnnouncedCaseNode` + `create_announce_vulnerability_case_received_tree()`

`KNOWN_VIOLATIONS` in the AST ratchet test reduced from 6 to 2 entries (remaining: `received/case/lifecycle.py`, `received/note.py`).

Key pitfall: `unknown.py` required local imports inside `execute()` to break a circular import chain through `semantic_registry → unknown.py → inbox package → pipeline.py → semantic_registry`. Matches the pattern already used in `received/embargo.py`.

17 new tests added; 3468 unit tests passing. All linters clean.

PR: [#1097](https://github.com/CERTCC/Vultron/pull/1097)
