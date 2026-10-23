---
source: BTND5.4
timestamp: '2026-05-04T18:01:38.559888+00:00'
title: Legacy bt/ isolation pattern for shared enums
type: learning
---

When a `core/` enum is replaced by a new version (e.g. `CVDRoles Flag` ->
`CVDRole StrEnum`), the legacy type used only by `bt/` should be moved to
`vultron/bt/roles/enums.py` (or similar bt/-local module) rather than kept
in `core/`. This keeps `core/` clean and signals clearly that the legacy
type is an implementation detail of the simulator layer.

Key decisions: `NO_ROLE` is removed from the StrEnum (empty list = no roles).
Serialization uses `.value` (lowercase), not `.name`. The centralized
`serialize_roles` / `validate_roles` helpers in `roles.py` are the single
source of truth for all models — don't duplicate per-class serializers.

**Promoted**: 2026-05-04 — archived as task-specific history; not a general
design pattern warranting a notes entry.
