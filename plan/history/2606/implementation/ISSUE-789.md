---
source: ISSUE-789
timestamp: '2026-06-16T15:05:19.889240+00:00'
title: Migrate record_event() to canonical CaseLedgerEntry writes
type: implementation
---

## Issue #789 — Migrate case history write paths to CaseActor-authorized canonical commits

Removed all remaining `record_event()` call sites from BT nodes and use-case
classes, replacing them with `CommitCaseLedgerEntryNode` canonical ledger
commits. Removed 6 xfail decorators from
`test/ci/test_case_ledger_invariants.py`.

### What changed

**Category A** (trees that already had `CommitCaseLedgerEntryNode` — removed
redundant dual-writes):

- `case_setup.py`: removed `record_event('offer_received')` and
  `record_event('case_created')` from `RecordOfferReceivedEventNode` and
  `RecordCaseCreatedEventNode`
- `owner.py`: removed `record_event('owner_joined')` + redundant `dl.save`
- `participant_add.py`: removed `record_event('participant_added')`
- `embargo.py`: removed `record_event('embargo_initialized')`
- `proposal.py`: removed `record_event('embargo_accepted')` block

**Category B** (tree that lacked `CommitCaseLedgerEntryNode` — added node and
removed `record_event`):

- `accept_invite_tree.py`: added `CommitCaseLedgerEntryNode` positioned after
  `BackfillCanonicalLedgerToInviteeNode` (so backfill sends prior history
  first, then fan-out broadcasts the new accept_invite entry); removed
  `record_event` calls; removed orphaned `active_embargo_id` blackboard key
  registration

**Use case layer**:

- `case_participant.py`: removed `case.record_event('participant_added')`

**Semantic registry**:

- `actor.py`: added `include_activity=True` to `AcceptInviteActorToCase`
  registry entry — without this the `.activity` field on the extracted event
  is `None` and `CommitCaseLedgerEntryNode` cannot extract a valid
  `payloadSnapshot`, raising `VultronCanonicalEntryError`

### Key technical decision

`CommitCaseLedgerEntryNode` is placed **after**
`BackfillCanonicalLedgerToInviteeNode` in `accept_invite_tree`. This avoids
double-delivery of the new entry to the invitee: the backfill sends prior
history first, then the commit fan-out broadcasts the new entry to all
participants (including the now-registered invitee). Placing the commit before
the backfill caused the new entry to appear in both the fan-out and the
backfill, resulting in duplicate delivery.

### Wire vocabulary registration fix

`list_objects("CaseLedgerEntry")` requires the wire-vocab
`vultron.wire.as2.vocab.objects.case_ledger_entry.CaseLedgerEntry` class to
be imported (its `__init_subclass__` registers it in `VOCABULARY`). Tests that
call `list_objects` must import `WireCaseLedgerEntry` — the core
`VultronCaseLedgerEntry` import alone is not sufficient.

### Acceptance criteria met

- All 6 xfail decorators removed from `test/ci/test_case_ledger_invariants.py`
  (inv 1, 2, 3, 4, 5, 7). inv-8 preserved (blocked on #937).
- 2945 unit tests pass, 34 skipped, 2 xfailed, 5633 subtests.
- mypy: 0 errors. pyright: 0 errors. flake8: clean.

PR: [#991](https://github.com/CERTCC/Vultron/pull/991)
