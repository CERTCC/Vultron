---
source: CONCERN-3339
timestamp: '2026-09-29T14:44:35.117880+00:00'
title: Received-side handlers mutate case state procedurally, bypassing behavior trees
  (BT-06-001)
type: learning
---

## Summary

BT-06-001 requires that all protocol-significant behavior run inside a behavior tree — the tree is the auditable record of what the protocol does, with no "simple enough to skip" threshold. Some received-message use-case handlers violate this intent: they change case state directly in `execute()` instead of through a BT.

Surfaced by a decision-audit adversarial re-derivation of spec group BT-06. Verdict: BT-06-001 correctly states the intent; the **code** is the violation.

Confirmed procedural case-state mutations with no BT involvement:

- `vultron/core/use_cases/received/case/lifecycle.py:59-60` — `AddReportToCaseReceivedUseCase.execute()` appends to `case.vulnerability_reports` and `self._dl.save(case)` directly (the sibling `CloseCaseReceivedUseCase` correctly uses BTBridge).
- `vultron/core/use_cases/received/note.py:137-170` — `RemoveNoteFromCaseReceivedUseCase.execute()` mutates `case.notes` and saves directly (while `AddNote`/`CreateNote` in the same module route through BTBridge).
- `vultron/core/use_cases/received/sync.py:184,193` — `_upsert_replication_state` persists via `dl.save` in a plain helper (SBT-01-001 says this procedural logic MUST move to BT invocations).

The guard does not catch this. `test/architecture/test_single_bt_execution_received_side.py` only checks (a) no import of the guarded-commit factory and (b) at most one `execute_with_setup` per `execute()`; its own docstring concedes it does not verify that no other domain-significant code remains in `execute()`. So BT-06-001's broad auditability edge is enforced by nobody, while only the narrower BT-06-006 (protocol-observable cross-actor actions) is actually guarded.

This is the residue of the CONCERN-1071 single-BT ratchet gap, which named a different file set and was closed; the same class survives in `lifecycle.py`/`note.py`.

## Acceptance Criteria

- [ ] AC-1: The procedural case-state mutations in `received/case/lifecycle.py` (add-report) and `received/note.py` (remove-note) are moved into behavior trees, matching the BT-routed sibling handlers.
- [ ] AC-2: `received/sync.py` replication-state persistence is routed through a BT per SBT-01-001, or SBT-01-001 is reconciled if a helper is genuinely correct.
- [ ] AC-3: The received-side ratchet is widened so a domain-significant `dl.save`/case mutation in an `execute()` outside a BT fails the build (closing the gap its own docstring admits), with a declared-exclusions allow-list that can only shrink.

## Reference

Spec: `specs/behavior-tree-integration.yaml` BT-06-001 / BT-06-006
Guard: `test/architecture/test_single_bt_execution_received_side.py`
Related: CONCERN-1071 (closed), SBT-01-001

**Resolved**: 2026-09-29 — implementation tracked in #3869, #3870, #3871, #3872, #3873, #3874.

Planning found the concern half right. The two handler findings (add-report and
remove-note) hold and are worse than described: neither is CASE_MANAGER-gated and
neither commits a ledger entry, so a non-CASE_MANAGER replica mutates itself from an
inbound message and no other replica learns of the change. The sync finding is dead
code: `_update_replication_state` has no production caller and
`UpdateReplicationStateNode` already does the work inside the reject-entry tree. The
ratchet claim named the wrong test: `test_no_dl_mutations_in_execute.py` already
exists with a bidirectional allow-list holding exactly the two files above. Its real
gap is that a helper called from `execute()` is excluded by design, which let eleven
`execute()` bodies in nine files reach a DataLayer write it never saw.

The plan names a fourth received-side stage, intake, ahead of guards, commit, and
effects (ADR-0111; CLP-10-006/010 amended; CLP-10-017 through CLP-10-020 added). One
shared intake node stores the received activity and its inlined objects verbatim,
runs first in every tree the shared factory builds, and is the only store path. The
mutation ratchet follows use-case helpers transitively; its allow-list is seeded with
those nine files plus the two direct-write files it already held, and emptied by the
migration issues, each of which carries the allow-list shrink as an acceptance
criterion. CM-15-005 is amended: the `auto_create_case` gate is an in-tree condition
node, since the routing-level short-circuit existed only to store the report and
Offer before the tree ran.

Docs PR: <https://github.com/CERTCC/Vultron/pull/3868>.
Spec: `specs/case-ledger-processing.yaml`.
Notes: `notes/bt-integration.md`.
