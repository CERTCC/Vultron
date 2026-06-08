---
source: ISSUE-654
timestamp: '2026-06-08T13:57:02.055153+00:00'
title: ActivityPub surrogate-key routing
type: implementation
---

## Issue #654 — Implement ActivityPub surrogate-key routing to replace Starlette path-converter workaround

Implemented surrogate-key routing support for actor/case lookups while preserving canonical actor-ID route compatibility.

- Added `find_case_by_short_id` to DataLayer and CasePersistence ports and implemented ambiguity-safe surrogate lookup in `SqliteDataLayer`.
- Updated case resolution surfaces (`resolve_case`, actor action-rules route, demo case-log routes) to resolve canonical case IDs from surrogate keys.
- Added guards so non-case objects cannot shadow case surrogate resolution, and ambiguous short-key matches are rejected.
- Updated demo case-log export path construction to use case surrogate keys.
- Added/updated adapter and core tests covering surrogate routing, ambiguity handling, and ID-collision behavior.

PR: <https://github.com/CERTCC/Vultron/pull/820>
