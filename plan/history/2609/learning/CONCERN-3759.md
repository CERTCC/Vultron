---
source: CONCERN-3759
timestamp: '2026-09-28T15:57:29.282383+00:00'
title: EmbargoEvent accepts naive start_time/end_time from nested wire objects
type: learning
---

`EmbargoEvent` (`vultron/core/models/embargo_event.py`) is a core class used directly on the wire (ADR-0099). The wire edge normalises an activity's own datetimes, but not the datetimes on a nested `EmbargoEvent`, so a naive `end_time` from an inbound `Invite(EmbargoEvent)` reaches core unchanged.

Comparing an aware datetime with a naive one raises `TypeError`. PR #3756 (the RSVP deadline clamp) hit this and guards it locally: `resolve_rsvp_deadline` runs every input through `as_utc`, and there is a regression test. Nothing else on the receive path in core compares these values today (the trigger-side request validators in `vultron/core/use_cases/triggers/requests.py` compare `end_time`, but reject naive input first). Still, a naive value is persisted and re-serialised without an offset, and the next consumer that compares one will fail the same way.

Root principle: datetime normalisation is an object construction/validation concern — objects must reliably provide UTC-aware timestamps. `as_Object.validate_datetime` already does this for wire objects (commit 9f9b71df3, #3202, 2026-09-14), but `EmbargoEvent` is a `CoreObject`, not an `as_Object`, so that validator never runs on its fields, and `CoreObject._carry_absent_times_on_inbound` handles absent and blank times only. The fix belongs on the core branch, where every ADR-0099 core-on-wire class shares the gap.

Governing specs: CLP-15-007 (take inbound data as received), ARCH-10-001, CS-13-001

**Resolved**: 2026-09-28 — implementation tracked in #3784. A second issue, #3785 (normalise naive datetimes in `as_Object.validate_datetime`), was closed during PR triage as already implemented.

Docs PR: <https://github.com/CERTCC/Vultron/pull/3787>.
