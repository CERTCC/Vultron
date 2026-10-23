---
source: ISSUE-726
timestamp: '2026-06-04T16:01:35.264761+00:00'
title: Migrate EmbargoPolicy + EmbargoEvent to core
type: implementation
---

## Issue #726 — Migrate EmbargoPolicy + EmbargoEvent to core

Refactor step 3 of #699: migrated `EmbargoPolicy` and `EmbargoEvent` domain
objects from the wire layer (`vultron/wire/as2/vocab/objects/`) into
`vultron/core/models/`, making the wire layer a thin projection.

### What changed

- Created `vultron/core/models/embargo_policy.py` with `EmbargoPolicy(CoreObject)`,
  ISO 8601 duration validators/serializers, and public `parse_duration()` helper
- Migrated `vultron/core/models/embargo_event.py`: renamed `VultronEmbargoEvent`
  → `EmbargoEvent(CoreObject)` with `Literal["EmbargoEvent"]`; added backward-compat
  alias `VultronEmbargoEvent = EmbargoEvent`
- Refactored wire `embargo_policy.py` to thin projection with `from_core()`/`to_core()`
- Updated wire `embargo_event.py` with `from_core()`/`to_core()`; `to_core()` strips
  wire-synthesized `name` to preserve core round-trip fidelity
- Updated all importers: `vultron_types.py`, `events/embargo.py`, behavior nodes,
  trigger use cases, extractor
- Added 84 new test cases across 4 new test files; all 2725 unit tests pass

### Code review findings addressed

- Renamed `_parse_duration` → `parse_duration` (public API shared with wire layer)
- Fixed `EmbargoEvent.to_core()` to strip wire-synthesized `name` field to prevent
  round-trip contamination; added regression test assertion

PR: [#771](https://github.com/CERTCC/Vultron/pull/771)
