---
source: ISSUE-802
timestamp: '2026-06-09T20:54:59.286520+00:00'
title: Collapse CoreActor|as_Actor adapter unions
type: implementation
---

## Issue #802 — Collapse CoreActor|as_Actor adapter unions after wire actor types land

Removed `as_Actor` from all adapter-layer function signatures and type aliases
per ADR-0017 (two-branch hierarchy, Option D). The adapters now work exclusively
with core-branch `CoreActor`; wire-branch `as_Actor` no longer appears in any
adapter or factory public API.

### Changes

- **`actors.py` router**: collapsed `AnyActor = CoreActor | as_Actor` → `CoreActor`;
  updated all function signatures, type maps, and `cast()` calls; switched
  `_ACTOR_TYPE_MAP` to core-branch Vultron types; unified `get_actors()` to
  iterate `_ACTOR_RECORD_TYPES` (including `"CoreActor"`)
- **`trigger_activity_adapter.py`**: replaced 3 `as_Actor(id_=...)` stubs with
  `CoreActor(id_=...)`
- **`vultron_actor.py`**: added `VOCABULARY["Actor"] = CoreActor` and
  `VOCABULARY["CoreActor"] = CoreActor` so `record_to_object()` can reconstruct
  stored `CoreActor` instances via `find_in_vocabulary()`
- **Factory/activity widening (transitional)**: `recommend_actor_activity()`,
  `rm_invite_to_case_activity()`, and their internal `object_` fields widened to
  `CoreActor | as_Actor` pending full wire actor retirement
- **Tests**: updated `VOCABULARY["Actor"]` assertion; replaced `as_Actor` with
  `CoreActor` in conftest `_actor_classes`; added explicit `inbox`/`outbox` URIs
  for `CoreActor` test fixtures; added `_SUPERSEDED_BASE_MODULES` exclusion for
  the registry-completeness test

### Outcome

All 3079 unit tests pass; all 4 linters (black, flake8, mypy, pyright) clean.

PR: [https://github.com/CERTCC/Vultron/pull/855](https://github.com/CERTCC/Vultron/pull/855)
