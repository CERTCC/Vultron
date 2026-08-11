---
status: accepted
date: 2026-08-11
deciders: [adh, Claude Sonnet 4.6]
---

# ADR-0056: `embargo_adherence` Is a Computed Property Derived from PEC State

## Context and Problem Statement

`ParticipantStatus.embargo_adherence: bool` was declared as a stored field
defaulting to `True`. The draft protocol specification (§6.4.6) defined it as
a derived property — `True` iff PEC state is `SIGNATORY`, `False` otherwise
— but flagged the derived-vs.-stored choice as unresolved (open question 14).

Two risks followed from the stored implementation:

1. **Drift.** The field can disagree with the PEC state it is meant to project.
   `_sync_latest_status_metadata()` updated `ParticipantStatus.consent` on
   every PEC write, but never updated `embargo_adherence`. A participant who
   transitioned from `SIGNATORY` to `LAPSED` still carried
   `embargo_adherence=True`.

2. **Fail-open default.** The default `True` means a freshly constructed
   `ParticipantStatus` — with `consent=None` or `consent.state=NO_EMBARGO` —
   reads as "is a signatory". The MV-10-005 full-case-delivery gate depends
   on this field; a wrong default bypasses the gate silently.

The question is: **should `embargo_adherence` be a stored field or a computed
property, and what is the enforcement point?**

## Decision Drivers

- `embargo_adherence` has exactly one correct value for any given PEC state;
  there is no scenario in which it should differ
- A stored field that can be set independently of PEC provides no value and
  creates two sources of truth for the same fact
- The fail-open default is a correctness hazard at the MV-10-005 gate
- Pydantic v2 `@computed_field` makes the derived nature explicit and
  serialization-compatible, requiring no changes to DataLayer consumers

## Considered Options

1. **`@computed_field` derived from `consent.state`** (chosen): remove the
   stored field; add a `@computed_field` that returns
   `self.consent is not None and self.consent.state == PEC.SIGNATORY`.
   The wire projection (`as_ParticipantStatus.from_core()`) computes the value
   instead of copying it.

2. **Stored field + `model_validator(mode='after')`**: keep the stored field;
   add a validator that sets it from `consent.state` on every construction.
   Guards initial construction, but still allows a caller to write the field
   after construction via direct assignment.

3. **Stored field + fix `_sync_latest_status_metadata`**: update the sync
   method to also write `embargo_adherence`. Does not guard initial
   construction; a freshly constructed `ParticipantStatus` still starts `True`.

## Decision Outcome

**Chosen option: `@computed_field` derived from `consent.state` (Option 1).**

### Consequences

- `ParticipantStatus.embargo_adherence` becomes a Pydantic `@computed_field`.
  It appears in `model_dump()` output and the Pydantic schema, exactly as a
  regular field, but it cannot be set directly.
- The default is effectively `False` — a participant with `consent=None` is
  not a signatory. This is fail-closed.
- `as_ParticipantStatus.from_core()` computes the value as
  `core_obj.consent is not None and core_obj.consent.state == PEC.SIGNATORY`.
  The stored wire field default changes from `True` to `False`.
- Departed participants who were `SIGNATORY` when they left will transition to
  `LAPSED` on embargo revision (the normal PEC machine path). The computed field
  correctly reflects `False` for `LAPSED`.
- Good, because drift is eliminated permanently.
- Good, because the fail-open default is replaced with a fail-closed one.
- Good, because the MV-10-005 full-case-delivery gate is now correctly
  enforced for all construction paths, not just those that call
  `apply_pec_transition()`.
- Bad, because callers that previously set `embargo_adherence` directly will
  fail at the Pydantic validation layer. Any such site must instead change
  the PEC state via `apply_pec_transition()`. (A grep sweep at
  implementation time will surface these sites — expected count: zero in
  production code, as CM-18-005 already requires all consent writes to go
  through `apply_pec_transition()`.)

## Validation

- Unit tests confirm `embargo_adherence` is `True` when `consent.state==SIGNATORY`
  and `False` for all other PEC states and for `consent=None`.
- Existing tests that assert `embargo_adherence is True` for a SIGNATORY
  participant continue to pass.
- Wire round-trip: `as_ParticipantStatus.from_core(core_status).to_core()`
  produces the correct `embargo_adherence` value.

## More Information

- Closes open question 14 in `docs/reference/draft-vultron-spec.md` (§6.4.6).
- Builds on ADR-0048 (PEC NO\_EMBARGO is absence of embargo) and ADR-0036
  (per-machine dimension objects).
- Generated spec requirements: `specs/case-management.yaml` CM-18-008.
- Source: Concern #2091.
