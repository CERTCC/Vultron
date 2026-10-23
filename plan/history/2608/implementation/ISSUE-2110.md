---
source: ISSUE-2110
timestamp: '2026-08-07T20:48:33.805089+00:00'
title: 'feat: implement duplicate-ignoring in as_Collection.append()'
type: implementation
---

## Issue #2110 — feat: implement duplicate-ignoring in as_Collection.append()

Added `PrivateAttr _ids: Set[str]` to `as_Collection` to track seen `id_` URIs.
A `model_validator` seeds `_ids` from existing `items` on construction so that
round-tripped collections also reject duplicates. `append()` silently skips
items whose `id_` is already present; items with no `id_` are always appended.
5 unit tests added covering unique, duplicate, no-id, construction-seeding,
and round-trip invariant cases.

PR: <https://github.com/CERTCC/Vultron/pull/2111>
