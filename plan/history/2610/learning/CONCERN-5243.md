---
source: CONCERN-5243
timestamp: '2026-10-27T15:11:29.955179+00:00'
title: Permissive object patterns classify a bare-id Announce(EmbargoEvent) as Announce(VulnerabilityCase)
type: learning
---

## Concern

`ActivityPattern` matches a bare string `object` against any object type unless the pattern is `strict` (`vultron/wire/as2/extractor/_pattern.py`, `_match_activity_field`). The registry's first `Announce` pattern that accepts a bare `object` wins, so a CASE_MANAGER's `Announce` that names an `EmbargoEvent` by its id alone is classified as `ANNOUNCE_VULNERABILITY_CASE`, not `ANNOUNCE_EMBARGO_EVENT_TO_CASE`. Reproduce with `extract_event(parse_activity({...Announce, object: "<embargo id>", context: <case>}))`. The same holds for `Accept`, `Reject` and `Add` with a case `target`, which match their first permissive pattern whatever the bare `object` names.

## Why it matters

- A bare reference is routed to a handler for a different object type, which then refuses or misreads it.
- It bounds the object dereference #3739 added (AKM-05-007). The inbox fetches a bare `object` only when no pattern matches (`UNKNOWN_UNRESOLVABLE_OBJECT`); an activity that matches the wrong pattern never reaches the fetch. Widening the fetch first would make replicas fetch in flows that work today, so the pattern behaviour is the thing to decide.

## Question to settle

Should `object` matching be strict by default, so that a bare `object` the receiver does not hold is unresolvable (and fetched, AKM-05-007) instead of matched by type-blind patterns? Which patterns legitimately rely on a bare `object` (for example, an Announce of a case the receiver holds)?

Surfaced while building #3739 (PR #5242).

Governing specs: SE-08, AKM-05-007, ARCH-25-009

Where: vultron/wire/as2/extractor/_pattern.py

**Resolved**: 2026-10-27 — implementation tracked in #5264 (strict object matching, blocked by #3739). Also filed: #5265 (partial inline objects accepted at the parse edge, a separate defect found while planning) and #5266 (Idea: typed `{id, type}` references for every object type).

Docs PR: <https://github.com/CERTCC/Vultron/pull/5263>.
Spec: `specs/semantic-extraction.yaml` (SE-01-006).
