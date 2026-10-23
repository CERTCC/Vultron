---
source: ISSUE-1706
timestamp: '2026-07-29T19:05:06.891688+00:00'
title: collect_actor_names scans list-valued AS2 fields
type: implementation
---

## Issue #1706 — Report: collect_actor_names does not scan list-valued ActivityStreams fields

Fixed `_collect_actor_names_from_obj` to recurse into list-valued
`actor`/`object`/`object_`/`target`/`origin` fields, which AS2 permits. Actor
objects nested inside such lists were previously silently skipped and their
`name` fields never harvested into the URI→name map. Added tests for
list-valued actor, object, and target fields.

PR: <https://github.com/CERTCC/Vultron/pull/1822>
