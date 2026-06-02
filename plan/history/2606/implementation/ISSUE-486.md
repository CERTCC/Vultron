---
source: ISSUE-486
timestamp: '2026-06-02T13:52:08.608536+00:00'
title: Fix actor subtype serialization in FastAPI routers
type: implementation
---

## Issue #486 — HTTP-08-001 violation: actors.py response_model strips subclass fields from GET/POST /actors/ endpoints

Completed implementation of subtype-safe actor serialization for FastAPI actor endpoints and datalayer actor listing.

- Added `VultronApplication` and `VultronGroup` plus `ActorUnion` in `vultron_actor.py`.
- Updated actors router create/list/get responses to serialize concrete actor subtypes with explicit model dumping and alias keys.
- Added raw-record actor lookup helper that preserves bare UUID to URN lookup compatibility while preventing subtype field loss.
- Updated datalayer actors endpoint subtype detection to honor both `type_` and aliased `type` payload keys.
- Added regression coverage in `test_actors_serialization.py` for GET/POST actor endpoints and `/datalayer/Actors/`.

PR: <https://github.com/CERTCC/Vultron/pull/662>
