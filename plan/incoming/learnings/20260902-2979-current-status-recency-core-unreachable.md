---
title: "current_status id_ tiebreaker: core path is unreachable; the bug lives on the wire branch"
type: learning
timestamp: "2026-09-02T00:00:00Z"
source: ISSUE-2979
signal: spec-ambiguity
---

# current_status id_ tiebreaker: core path is unreachable; bug lives on the wire branch

Task: #2979 (Fix current_status UUID tiebreaker), spec CM-29-001.

## What was non-obvious

CM-29-001 and #2979 name `VulnerabilityCase.current_status` (the **core**
type) and prescribe a test that "construct[s] a VulnerabilityCase with an
auto-seeded status (urn:uuid ID, no timestamps) and a received status (HTTPS
ID, no timestamps)". That scenario is **not constructible on the core
branch**: core `CaseStatus` inherits `published`/`updated` with
`default_factory=_now_utc` re-narrowed to non-Optional `datetime`
(`vultron/core/models/base.py` CoreObject), so Pydantic rejects
`updated=None`/`published=None`. Because `cs.updated` is therefore always a
truthy aware datetime in core, the `cs.id_` fallback in the core
`current_status` was **dead code** — the fix there is CM-29-001 compliance,
not a reachable behavior change.

The bug is reachable only on the **wire** branch
(`vultron/wire/as2/vocab/objects/vulnerability_case.py`): `as_CaseStatus`
keeps `datetime | None` and permits explicit `None` timestamps. That is where
a timestampless auto-seeded status (`urn:uuid…` sorts lexically above
`https…`) beat a received status via the `id_` tiebreaker, and where the
regression test that actually fails pre-fix must live
(`test/wire/as2/vocab/test_vulnerability_case.py`).

## Second-order edge: naive wire timestamps

`as_*` `validate_datetime` (`vultron/wire/as2/vocab/base/objects/base.py`)
does `datetime.fromisoformat(value)` with **no tz normalization**, so an
offset-less ISO string deserializes to a *naive* datetime. Replacing the
`id_` fallback with an aware `datetime.min` would then make `max()` compare
naive vs aware → `TypeError`. The recency key must normalize naive→UTC. Both
`current_status` implementations now delegate to
`vultron/core/models/_helpers.py::status_recency_key`, which coerces naive to
UTC (consistent with `_now_utc`) and floors timestampless statuses at
`datetime.min` (UTC).

## Suggested follow-up for `learn`

CM-29-001's `verification` text implies the core `VulnerabilityCase` can hold
timestampless statuses; it cannot. Consider refining the spec verification to
target the wire projection (or note the core path is defensive/unreachable).

The related wire-layer question — whether `validate_datetime` should normalize
naive datetimes at the edge (ADR-0032) rather than each consumer coercing — is
tracked separately as Concern #3098 (do not re-track it here).

---

**Promoted**: 2026-09-03 — captured in `specs/case-management.yaml` (CM-29-001 verification refined: test `status_recency_key` directly; the timestamp-absent branch is unreachable on the core path — `CoreObject` re-narrows to non-Optional aware datetimes — and exercisable only on the wire `as_CaseStatus` branch). Docs PR: <DOCS_PR_URL>.
