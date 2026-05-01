---
title: TASK-SEDRIFT — Fix Semantic Extraction Pattern Gaps
type: implementation
timestamp: '2026-04-28T22:54:41+00:00'

source: TASK-SEDRIFT
---

## TASK-SEDRIFT — Fix Semantic Extraction Pattern Gaps

All three subtasks implemented and tested.

**SEDRIFT.1** — Bare-string `object_` guard in `find_matching_semantics()`:

- `find_matching_semantics()` returns `UNKNOWN_UNRESOLVABLE_OBJECT` when
  `activity.object_` is a bare string and the activity type has registered
  patterns; tested in `test/test_semantic_activity_patterns.py`.

**SEDRIFT.2** — Subtype-aware `_match_field()` for AS2 actor types:

- `_match_field()` now supports `isinstance(activity_field, as_Actor)` for
  `AOtype.ACTOR` pattern fields, matching any AS2 actor subclass.
- `InviteActorToCasePattern` uses `object_=AOtype.ACTOR` discriminator.
- Tests cover `Invite(VultronPerson, target=Case)`.

**SEDRIFT.3** — Dead-letter handling for unresolvable `object_`:

- `UnresolvableObjectUseCase` stores `DeadLetterRecord` and logs WARNING.
- Registered in `vultron/semantic_registry.py` for
  `MessageSemantics.UNKNOWN_UNRESOLVABLE_OBJECT`.
- `UnresolvableObjectReceivedEvent` event model defined.
- Tests in `test/core/use_cases/received/test_unresolvable_object.py`.
