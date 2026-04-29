---
title: DR-07 Update InviteActorToCasePattern missing object_ + subtype constraint
type: learning
date: 2026-04-20
source: REVIEW-26042001-supplement-DR-07
---

InviteActorToCasePattern has no object_field violating SE-03-003. Fix requires
subtype-aware matching in_match_field() since AOtype.ACTOR = "Actor" does not
match actor subtypes (Person/Organization/Service).

**Promoted**: 2026-04-28 — captured as open question in
`notes/activitystreams-semantics.md`.
