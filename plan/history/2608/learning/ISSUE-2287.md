---
title: _accepted_wire_patch uses hardcoded key names to select adjudicated fields from port output
type: learning
timestamp: '2026-08-22T00:00:00+00:00'
source: ISSUE-2287
signal: design-question
---

In `vultron/core/behaviors/status/nodes/dimension_filter._accepted_wire_patch`,
the function calls `port.render(filtered)` and then filters the result to the
keys `"rmState"`, `"vfdState"`, `"caseStatus"`.

Issue #2287 said "delete core camelCase hand-patches." The interpretation made
was: using hardcoded wire key names to *select which adjudicated fields to
include* in the patch dict is acceptable — the *values* come from the port.
Hardcoding them does not violate ARCH-01 because no values are being
constructed by hand; only the selection is explicit.

The alternative (include all rendered fields) was rejected because it would
override non-adjudicated fields in the ledger entry's `payload_snapshot`.

If the wire schema for `ParticipantStatus` ever renames `rmState`, `vfdState`,
or `caseStatus`, this function must be updated to match. Consider making the
key list derive from the port's schema rather than being hardcoded if that
becomes a maintenance concern.

**Promoted**: 2026-08-24 — captured in archive only (code is authoritative).
Docs PR: [PR URL TBD].
