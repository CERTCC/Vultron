---
source: CONCERN-2321
timestamp: '2026-08-26T20:48:00.995643+00:00'
title: vestigial save+read-back in participant-status write path
type: learning
---

## Problem

Two call sites in the participant-status write path save a `ParticipantStatus` and
immediately read it back from the DataLayer before appending it to
`participant.participant_statuses`. The comments at both sites originally said the
read-back was needed *"to obtain the vocabulary-typed (wire-format) version"*.

ADR-0034 states the DataLayer port returns **core** domain objects — not wire-format
objects. The stated reason was incorrect as written.

## Investigation

The two original files were:

- `vultron/core/behaviors/sync/nodes/participant_status_effect.py`
- `vultron/core/behaviors/status/nodes/append.py` (since removed in refactor)

Since the concern was filed, the codebase has changed:

1. The misleading "wire-format" comment is gone from both locations.
2. `append.py` was removed and refactored into `vultron/core/behaviors/status/nodes/append/actions.py`.
3. `participant_status_effect.py` was completely rewritten for ledger replication.

However, the save+read-back pattern persists in two current locations:

- `ApplyParticipantStatusFromLedgerNode.update()` in `participant_status_effect.py` —
  read-back with circular justification referencing ADR-0034, but `status_obj` is
  already a core `ParticipantStatus`.
- `ResolveAndPersistStatusObjectNode.update()` in `append/actions.py` — two
  `self.datalayer.read(self.status_id) or status_obj` calls.

`ParticipantStatus` has only embedded dimension objects (`rm`, `vfd`, `consent`,
`case_status`) — no reference fields that `rehydrate_fields` would expand.
`dl.read()` after `dl.save()` returns a functionally equivalent object. `dl.save()`
raises on failure via `session.commit()`, so the read-back as implicit save-failure
detection is redundant.

**Resolved**: 2026-08-26 — implementation tracked in #2720.
