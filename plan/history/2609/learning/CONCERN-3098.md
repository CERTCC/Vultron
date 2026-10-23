---
source: CONCERN-3098
timestamp: '2026-09-14T18:21:53.510494+00:00'
title: Wire validate_datetime does not normalize naive datetimes to UTC (ADR-0032
  validate-at-edge gap)
type: learning
---

## Summary

`vultron/wire/as2/vocab/base/objects/base.py::validate_datetime` deserializes
the datetime fields (`published`, `updated`, `start_time`, `end_time`) via
`datetime.fromisoformat(value)` with no timezone normalization. An offset-less
ISO string (e.g. `"2026-01-01T00:00:00"`) therefore yields a *naive* datetime
on the wire branch.

## Surface symptom vs. underlying problem

**Surface symptom:** a specific accessor crashes — `VulnerabilityCase.current_status`
compares status timestamps in `max()`, and a naive `updated` compared against a
timezone-aware value raises `TypeError: can't compare offset-naive and
offset-aware datetimes`.

**Underlying problem:** naive datetimes are allowed to flow *past the wire edge*
into the core-facing object graph. Per ADR-0032 (validate at the edge, promote
to strict core types), the wire layer should normalize (or reject) naive
datetimes at deserialization, so no downstream consumer has to defend against
them individually. The current design pushes that burden onto every comparison
site.

## Evidence

Surfaced in #2979 / PR #3095. `current_status` was mitigated locally by
normalizing naive→UTC inside the shared `status_recency_key` helper
(`vultron/core/models/_helpers.py`), but the root cause remains and any other
site comparing wire datetimes against aware datetimes is exposed.

## Category / severity

Architecture / wire-core boundary. Latent correctness fragility; low observed
frequency (AS2 timestamps usually carry offsets) but a hard crash when hit.

## Resolution

**Resolved**: 2026-09-14 — implementation tracked in #3202.

Plan: normalize (not reject) naive datetimes to UTC at the wire edge via
`as_utc()` in `validate_datetime`; consolidate `dt_utils.py` datetime helpers
into `vultron/core/models/_helpers.py`; delete `dt_utils.py`; update all callers.
