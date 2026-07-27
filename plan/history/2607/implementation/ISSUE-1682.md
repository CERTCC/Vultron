---
source: ISSUE-1682
timestamp: '2026-07-27T14:12:41.578750+00:00'
title: 'Report: map actor URIs to semantic names'
type: implementation
---

## Issue #1682 — Report: map actor URIs to semantic names/roles instead of hex fragments

Implemented URI-to-display-name resolution for the demo report tool. Actor URIs using UUID-based paths (e.g. `actors/9e580519-…`) now resolve to semantic names (e.g. "Vendor", "Finder") instead of hex-fragment labels like "A1e7 421f B727".

### Changes

- `collect_actor_names()` — scans all payload snapshots for AS2 actor objects with both `id` and `name` fields; builds URI→name map with sorted/deterministic first-writer-wins resolution
- `_collect_actor_names_from_obj()` — recursive scanner for nested actor objects
- `friendly_actor_name()` — updated with optional `actor_names` parameter; resolves from map before URI heuristic
- `CaseTimelineEvent` — three new display name fields (`actor_display_name`, `target_display_name`, `activity_target_display_name`)
- `actor_label` / `target_label` properties — prefer resolved display names
- `_ACTOR_LIKE_TYPES` — added `Application` and `CaseActor` (F2 code review fix)
- 14 new tests in `TestActorNameResolution`
- `specs/demo-report.yaml` v1.3.0→v1.4.0: added DRPT-03-003 and DRPT-05-004
- DEFER #1706: list-valued AS2 fields not yet scanned

PR: <https://github.com/CERTCC/Vultron/pull/1708>
