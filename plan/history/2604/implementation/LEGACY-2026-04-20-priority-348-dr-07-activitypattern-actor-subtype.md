---
title: "PRIORITY-348 DR-07 \u2014 ActivityPattern actor subtype-aware matching"
type: implementation
timestamp: '2026-04-20T00:00:00+00:00'
source: LEGACY-2026-04-20-priority-348-dr-07-activitypattern-actor-subtype
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 7204
legacy_heading: "PRIORITY-348 DR-07 \u2014 ActivityPattern actor subtype-aware\
  \ matching"
date_source: git-blame
---

## PRIORITY-348 DR-07 — ActivityPattern actor subtype-aware matching

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:7204`
**Canonical date**: 2026-04-20 (git blame)
**Legacy heading**

```text
PRIORITY-348 DR-07 — ActivityPattern actor subtype-aware matching
```

**Completed:** 2026-05-05

**Task:** DR-07 — ActivityPattern discrimination requirement (remaining work).

**Problem:** `InviteActorToCasePattern` had no `object_` discriminator, violating
SE-03-003. The `_match_field()` function used exact `type_` string equality, but
real AS2 actor subtypes (`Person`, `Organization`, `Service`) have different
`type_` values than the base `Actor`. Adding `object_=AOtype.ACTOR` would fail
to match real invites because `"Person" != "Actor"`.

**Solution:**

1. Added subtype-aware matching in `_match_field()` (in `ActivityPattern.match()`
   in `vultron/wire/as2/extractor.py`): when `pattern_field == AOtype.ACTOR`,
   check `isinstance(activity_field, as_Actor)` rather than comparing `type_`
   strings. This matches all actor subtypes correctly.
2. Added `object_=AOtype.ACTOR` discriminator to `InviteActorToCasePattern`.
   This propagates through `AcceptInviteActorToCasePattern` and
   `RejectInviteActorToCasePattern` (which use nested patterns).
3. Added import of `as_Actor` from `vultron.wire.as2.vocab.base.objects.actors`.

**Files changed:**

- `vultron/wire/as2/extractor.py` — subtype-aware `_match_field()`, new import,
  `object_=AOtype.ACTOR` on `InviteActorToCasePattern`
- `test/test_semantic_activity_patterns.py` — 9 new tests (4×Person/Org/Svc/Actor
  for Invite, 4×Accept(Invite), 1×non-actor object doesn't match)

**Test Result:**

1715 passed, 12 skipped, 182 deselected, 5581 subtests passed
