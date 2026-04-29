---
title: 'SC-PRE-2 complete: actor_participant_index'
type: implementation
date: '2026-03-11'
source: SC-PRE-2
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 367
legacy_heading: "2026-03-10 \u2014 SC-PRE-2 complete: actor_participant_index"
date_source: git-blame
legacy_heading_dates:
- '2026-03-10'
---

## SC-PRE-2 complete: actor_participant_index

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:367`
**Canonical date**: 2026-03-11 (git blame)
**Legacy heading**

```text
2026-03-10 — SC-PRE-2 complete: actor_participant_index
```

**Legacy heading dates**: 2026-03-10

### Design

`actor_participant_index: dict[str, str]` maps actor IDs (from
`CaseParticipant.attributed_to`) to participant IDs. Added to
`VulnerabilityCase` alongside two new methods:

- `add_participant(participant: CaseParticipant)` — appends the full object
  to `case_participants` and updates the index atomically. Requires a full
  `CaseParticipant` object (not a string ref) to derive the actor key.
- `remove_participant(participant_id: str)` — filters `case_participants`
  and removes the corresponding index entry.

### Handlers updated

- `add_case_participant_to_case` → calls `case.add_participant(participant)`
- `remove_case_participant_from_case` → calls `case.remove_participant(participant_id)`
- `accept_invite_actor_to_case` → calls `case.add_participant(participant)`;
  idempotency check now uses `actor_participant_index` (old check was
  comparing actor IDs against participant IDs and never matched).

### Notes for SC-3.2 / SC-3.3

The `actor_participant_index` is the prerequisite for SC-3.2 and SC-3.3.
SC-3.2 records the accepted embargo ID in `CaseParticipant.accepted_embargo_ids`
using the CaseActor's trusted timestamp. The index makes it efficient to
look up a participant from the actor ID when processing `Accept(Invite(...))` or
`Accept(Offer(Embargo))` activities.

SC-3.3 adds `_check_participant_embargo_acceptance()` as a module-level helper
in `vultron/api/v2/backend/handlers/case.py`. It is called from `update_case`
after the ownership check passes. The helper iterates `actor_participant_index`,
rehydrates each participant, and logs a WARNING if the participant's
`accepted_embargo_ids` does not include the case's `active_embargo` ID.
Full enforcement (withholding the broadcast) is deferred to PRIORITY-200 when
the outbox delivery pipeline is implemented.
