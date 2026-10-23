---
source: NOTES-case-state-model--actor-to-participant-index
timestamp: '2026-09-17T17:13:54.089664+00:00'
title: Actor-to-Participant Index (SC-PRE-2)
type: note
---

**Archived:** 2026-09-17
**Reason:** (a) delivered
**Superseded by:** vultron/wire/as2/vocab/objects/vulnerability_case.py:107

---

## Actor-to-Participant Index (SC-PRE-2)

Several handlers (including `accept_invite_to_embargo_on_case` and
`accept_invite_actor_to_case`) need to resolve an **Actor ID → CaseParticipant
ID** mapping within the context of a specific case. Without a fast lookup,
handlers must iterate all participants, which is fragile and error-prone.

### Design

Add `actor_participant_index: dict[str, str] = Field(default_factory=dict)`
to `VulnerabilityCase`:

- Key: `actor_id` string (full URI)
- Value: `participant_id` string (full URI of the `CaseParticipant` object)
- This field is a **derived index** — it MUST be excluded from
  ActivityStreams serialization (use `exclude=True` in the field definition
  or an equivalent Pydantic v2 pattern) because it is not protocol data
- `case_participants` is the canonical participant surface; lookup helpers
  MAY use the index as a shortcut, but they MUST treat any divergence between
  the two surfaces as an explicit error rather than silently reconciling it

### Participant Management Methods

Add two methods to `VulnerabilityCase`:

- `add_participant(participant: CaseParticipant)`: appends
  `participant.as_id` to `case_participants`; records
  `actor_id → participant.as_id` in `actor_participant_index`; raises
  (or no-ops) if the actor is already registered — choose one behavior
  and enforce it consistently
- `remove_participant(participant_id: str)`: removes from
  `case_participants`; removes the corresponding actor key from
  `actor_participant_index`

### Handler Updates

All handlers that currently write to `case.case_participants` directly MUST
be updated to call `case.add_participant()` or `case.remove_participant()`:

- `accept_invite_actor_to_case` (actor handler)
- `create_case` BT node `CreateInitialVendorParticipant`
  (`behaviors/case/nodes.py`)
- `remove_case_participant_from_case` (participant handler)
- Any other handler that appends or removes participants

**Invariant**: The index MUST always reflect the contents of
`case_participants`. Out-of-sync states MUST NOT be possible via normal
code paths.

Read-side participant lookup MUST prefer `case_participants` as the source of
truth. `actor_participant_index` exists only as a derived lookup aid, so any
missing or contradictory mapping MUST fail fast and surface a bug in the
write path or fixture setup.

**Open Question**: (blocks SC-PRE-2) Whether to raise or silently no-op on
duplicate `add_participant()` calls. Recommend raise for correctness;
handlers should guard with an existence check before calling
`add_participant()` to keep idempotency logic explicit.

**Cross-reference**: `specs/case-management.yaml` CM-10-002, CM-10-001;
`AGENTS.md` "Cases should have participant-to-actor and vice versa indexes".

---
