---
source: NOTES-activitystreams-state-update--open-question-actor-subtype-aware-pattern-matching
timestamp: '2026-09-17T17:08:15.099907+00:00'
title: 'Open Question: Actor Subtype-Aware Pattern Matching'
type: note
---

**Archived:** 2026-09-17
**Reason:** (a,e) resolved; subtype-aware matching implemented
**Superseded by:** vultron/wire/as2/extractor/_pattern.py,_instances.py

---

## Open Question: Actor Subtype-Aware Pattern Matching

(DR-07 Update, 2026-04-20)

`InviteActorToCasePattern` in `vultron/wire/as2/extractor.py` has no
`object_` field, violating SE-03-003. The correct structure per AS2 is
`Invite(object=Actor, target=Case)`.

**Constraint discovered (2026-04-20)**: `AOtype.ACTOR = "Actor"` only matches
the base `as_Actor` class (`type_="Actor"`). Real AS2 actor subtypes
(`VultronPerson`, `VultronOrganization`, `CaseActor`) have `type_="Person"`,
`type_="Organization"`, `type_="Service"` respectively. The pattern matcher
uses exact string equality, so `object_=AOtype.ACTOR` would NOT match real
invite objects containing actor subtypes. Adding it breaks existing tests and
real invite flows.

**Required fix before this can be implemented**: Add subtype-aware matching
in `_match_field()` (e.g., check `isinstance(activity_field, as_Actor)`) or
a custom actor-type predicate in `ActivityPattern`.

**Open Question**: What is the right predicate API for ActivityPattern
subtype matching? Options include:

1. `object_type_predicate = lambda obj: isinstance(obj, as_Actor)` — flexible
   but non-declarative
2. A `subtype_of` field on `ActivityPattern` that maps to a class — consistent
   with the existing `object_type` string field

Until subtype-aware matching is implemented, `InviteActorToCasePattern`
should remain without an `object_` constraint and this open question tracked
in the pattern audit.

---
