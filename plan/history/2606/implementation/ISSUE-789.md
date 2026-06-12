---
source: ISSUE-789
timestamp: '2026-06-12T20:54:38.924550+00:00'
title: Migrate case history write paths to CaseLedger commits
type: implementation
---

## Issue #789 — Migrate case history write paths to CaseActor-authorized canonical commits

Removed all `VulnerabilityCase.record_event()` dual-writes from BT nodes and
standalone use-case call sites, replacing them with canonical `CaseLedgerEntry`
commits via `CommitCaseLedgerEntryNode`, `CommitLogCascadeNode`, and
`commit_log_entry_trigger`.

### Changes

#### Phase A — Remove dual-write record_event from BT nodes

- `RecordCaseCreationEvents` subtree removed from `CreateCaseFlow`
- `RecordParticipantAddedEventNode` removed from `CreateCaseParticipantNode`;
  `datalayer.save()` moved into `AttachParticipantToCaseNode`
- `RecordOwnerJoinedEventNode` removed from `CreateCaseOwnerParticipant`
- `record_event` removed from `SetEmbargoActiveNode` and
  `RecordParticipantAcceptanceNode`

#### Phase B — Replace standalone record_event in use cases

- `AcceptInviteActorToCaseReceivedUseCase`: replaced `participant_joined` /
  `embargo_accepted` calls with `commit_log_entry_trigger`
- `AddCaseParticipantToCaseReceivedUseCase`: removed `participant_added` call

#### Phase C — Fix event_type strings to match EXPECTED_EVENT_TYPES

- `accept_report`, `accept_embargo`, `add_note`, `propose_embargo`
- `notify_fix_ready` / `notify_fix_deployed` / `notify_published` /
  `add_participant_status` via `_status_event_type()` in
  `AddParticipantStatusToParticipantReceivedUseCase`
- `payloadSnapshot` enriched with `emConsentState` / `cvdRole` / `rmState`
  for invariants 7 and 9

#### Phase D — Flip xfail markers to passing (invariants 1–5, 7, 9)

### Outcome

All 7 targeted invariants now pass without xfail.
3202 unit tests passed; all linters (black, flake8, mypy, pyright) clean.

PR: [#944](https://github.com/CERTCC/Vultron/pull/944)
