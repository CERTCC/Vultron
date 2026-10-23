---
source: CONCERN-3547
timestamp: '2026-09-25T14:30:31.182562+00:00'
title: Stripping a contradicted computed field silently discards a peer assertion
type: learning
---

## Summary

`CoreObject._drop_computed_field_inputs` strips a supplied `@computed_field`
value unconditionally. That is required so a core object can re-read its own
dump under `extra="forbid"` (ARCH-23-005), but it also means a peer *asserting*
a computed value that this object's own state contradicts is silently erased —
no error, no log.

The concrete case is `ParticipantStatus.embargo_adherence` (ADR-0056), which
core derives from `consent.is_signatory()`:

```python
as_ParticipantStatus(
    context="urn:case:1",
    em_consent_state=PEC.UNBOUND,
    embargo_adherence=True,
).to_core().embargo_adherence
# False — the peer's adherence assertion is gone, with no diagnostic
```

Embargo adherence gates disclosure, so a peer claiming adherence while its
consent state says `UNBOUND` is arguably a protocol disagreement worth
surfacing, not normalising away.

This is **not a regression**: before `extra="forbid"` landed, Pydantic's
`extra="ignore"` default discarded the key just as silently. It is the one
remaining silent-drop carve-out in a boundary whose stated contract is that an
unrecognised key is "rejected loudly".

## Why the obvious fix does not work

Triage on #3531 implemented and then reverted the natural fix (strip only when
the supplied value equals the derived one; otherwise raise). It breaks the
wire→core **read** path, and there is a test proving it:

- `as_ParticipantStatus.embargo_adherence` is an independent, settable *wire*
  field, while core derives the value from `consent`. A stored wire row carrying
  `embargo_adherence: True` with no `consent` therefore disagrees with core's
  derived `False` **legitimately**, not as a lie.
- With the strict check in place, `test_create_wire_shaped_storable_record_reads_back_as_core`
  and its `update` twin fail: `dl.read()` stops returning a core
  `ParticipantStatus` and hands back the `as_ParticipantStatus` wire object
  instead, because both core validation *and* the wire→core projection now raise.

So the check cannot be applied without first being able to distinguish
"re-reading our own core dump" (where the values must agree) from "projecting a
wire row" (where they legitimately need not). That distinction is exactly what
the `WireParsePort` (#2938) is meant to own.

## Options to weigh

1. Do nothing: accept the strip, and document it as the deliberate carve-out it
   is. (The code comment added in #3531 does this much.)
2. After #2938, reject a contradiction only on the core-dump re-read path, and
   let the wire-parse path reconcile explicitly.
3. Make the disagreement observable without failing — e.g. a WARNING when a
   supplied computed value differs from the derived one. Cheap, and would have
   made this findable from logs rather than from reading the validator.

Option 3 is available now and independent of #2938.

## Reference

Specs: ARCH-12-003, ARCH-23-005. ADRs: 0056, 0082.
Code: `vultron/core/models/base.py` (`_drop_computed_field_inputs`, and the
`NOTE (#2940 triage)` comment recording the reverted attempt).
Surfaced by triage on #3531.

**Resolved**: 2026-09-25 — implementation tracked in #3695.

Docs PR: <https://github.com/CERTCC/Vultron/pull/3693>.

Spec: `specs/architecture.yaml` (ARCH-23-005).

Notes: `notes/wire-core-boundary.md`.

Outcome: the premise that the strict check could not be applied is out of date. ADR-0099 detail 3 aliased `as_ParticipantStatus` onto core, and `WireParsePort` (#2938) was rejected. Decision: refuse a contradicted computed-field value with `VultronProtocolViolationError`, and strip only a matching one.
