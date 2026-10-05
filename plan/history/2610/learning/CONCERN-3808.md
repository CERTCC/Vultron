---
source: CONCERN-3808
timestamp: '2026-10-02T17:27:27.587050+00:00'
title: 'concern: CS-13-005 (serialise with UTC offset) conflicts with CLP-15-007 (carry
  as received) for aware non-UTC inbound timestamps'
type: learning
---

## Observation

`CoreObject._serialize_datetime` (`vultron/core/models/base.py`) writes every timestamp with `isoformat()`. For a value that arrived aware but not in UTC — say `2026-09-01T12:00:00+05:00` on a nested `EmbargoEvent.endTime` — that re-renders as `+05:00`. CS-13-005 says wire-format datetime fields MUST serialize with an explicit **UTC** offset (`Z` or `+00:00`), so the bytes we emit for a carried-through non-UTC timestamp literally violate it.

Neither normaliser converts: `as_utc()` (used by `as_Object.validate_datetime` on the wire branch and, since #3784, by `CoreObject._normalise_datetime_to_utc` on the core branch) attaches UTC to a *naive* value and leaves an *aware* value with the offset it came with. That is deliberate under CLP-15-007 ("carry as received") and keeps `payloadSnapshot` bytes stable across replicas, but it means CS-13-005 and CLP-15-007 pull in opposite directions for one input class: an aware, non-UTC inbound timestamp.

Surfaced by the spec review of #3784, where `resolve_rsvp_deadline` lost the only `astimezone(timezone.utc)` conversion in the codebase. Nothing about #3784 introduced the conflict; it made it visible.

## Question to settle

Which wins for a carried non-UTC offset?

- **(a) CS-13-005 as written** — convert to UTC at the serialiser (`value.astimezone(timezone.utc).isoformat()`). Same instant, different bytes; every replica runs the same code so snapshot comparison stays consistent, but the sender's offset is lost and the `payloadSnapshot` is no longer "the verbatim AS2 activity" (CLP-07-011).
- **(b) CLP-15-007 as written** — carry the offset and amend CS-13-005 to require an explicit offset (any), with "UTC" reserved for values the application *produces*. This matches what `as_utc` has always done.

Recommendation from the review: (b), since instants compare correctly either way and the snapshot contract is the stronger one. Needs a decision (spec amendment or serialiser change), then a test on `CoreObject._serialize_datetime` pinning it.

## Where

- `vultron/core/models/base.py` — `_normalise_datetime_to_utc`, `_serialize_datetime`
- `vultron/core/models/_helpers.py` — `as_utc`
- `specs/code-style.yaml` — CS-13-001, CS-13-005; `specs/case-ledger-processing.yaml` — CLP-15-007, CLP-07-011

**Resolved**: 2026-10-02 — CS-13-005 amended: minted times are written in UTC; a carried timestamp keeps the explicit offset it arrived with (CLP-15-007, CLP-07-011). Captured in specs/code-style.yaml; test pinning owned by #4164.
Docs PR: <https://github.com/CERTCC/Vultron/pull/4174>.
