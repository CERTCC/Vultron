---
title: current_status max-by-ID returns auto-seeded UUID status over received HTTPS IDs
type: learning
timestamp: 2026-08-26T17:30:00Z
source: ISSUE-2256
signal: concern
---

`VulnerabilityCase.current_status` uses `max()` with a tuple key that
includes `id_` as a tiebreaker. UUID-based IDs (`urn:uuid:...`) sort
lexically higher than HTTPS IDs (`https://...`) because `'u' > 'h'`.

`as_VulnerabilityCase` auto-seeds an initial `CaseStatus` with a UUID-based
ID. Any subsequently received status with an HTTPS ID will lose the
`max()` comparison unless its `updated`/`published` timestamp is strictly
later.

In ISSUE-2256 testing this caused `current_status` to return the auto-seeded
initial status (em=NONE) instead of the newly appended filtered status
(em=PROPOSED), even after the filtered status was successfully saved and
appended. The test was fixed by asserting on `dl.read(STATUS_ID)` directly,
but the underlying `current_status` ordering is fragile.

**Risk**: in production, `current_status` may silently return stale
auto-seeded state rather than the most recently received CaseStatus when ID
schemes mix UUID and HTTPS. This could affect embargo teardown decisions
and any consumer of `current_status`.

**Suggested fix**: `current_status` should sort by `updated`/`published`
timestamps only, not by `id_`; or the auto-seeded ID should use the same
HTTPS scheme as received statuses.

Filed as a follow-up concern; tracked via this learning.

**Promoted**: 2026-08-27 — captured in specs/received-status-handling.yaml RSH-05-015/16/17 and specs/case-bootstrap-trust.yaml CBT-01-008/09 and CBT-05-008, specs/state-machine.yaml SM-04-001, notes/bt-pitfalls.md, notes/flaky-tests.md, AGENTS.md. Concern issues #2736 #2737 filed. Docs PR: <pending>.
