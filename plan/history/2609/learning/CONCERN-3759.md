---
source: CONCERN-3759
timestamp: '2026-09-28T15:57:29.282383+00:00'
title: EmbargoEvent accepts naive start_time/end_time from nested wire objects
type: learning
---

`EmbargoEvent` (`vultron/core/models/embargo_event.py`) is a core class used directly on the wire (ADR-0099). The wire edge normalises an activity's own datetimes, but not the datetimes on a nested `EmbargoEvent`, so a naive `end_time` from an inbound `Invite(EmbargoEvent)` reaches core unchanged.

Comparing an aware datetime with a naive one raises `TypeError`. PR #3756 (the RSVP deadline clamp) hit this and guards it locally: `resolve_rsvp_deadline` runs every input through `as_utc`, and there is a regression test. Nothing else in core compares these values today. Still, a naive value is persisted and re-serialised without an offset, and the next consumer that compares one will fail the same way.

Root principle: datetime normalisation is an object construction/validation concern — objects must reliably provide UTC-aware timestamps. Neither `EmbargoEvent` nor `as_Object.validate_datetime` enforced this.

**Resolved**: 2026-09-28 — implementation tracked in #3784, #3785.
