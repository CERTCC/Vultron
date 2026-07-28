---
source: ISSUE-1505
timestamp: '2026-07-20T14:45:32.637394+00:00'
title: 'Architecture ratchet: dl.read() must not return wire vocab types'
type: implementation
---

## Issue #1505 — Add architecture ratchet: no wire vocab type escapes dl.read into core

Implemented `test/architecture/test_dl_read_returns_core_objects.py` enforcing DL-05-004.

Two tests:

1. `test_dl_read_returns_core_objects_not_wire_types` — round-trips all CORE_VOCABULARY types through an in-memory SqliteDataLayer and asserts no result's `__module__` starts with `vultron.wire.as2`. KNOWN_WIRE_ESCAPES (6 actor types) are documented as pre-existing violations; the ratchet set is shrink-only.
2. `test_activity_type_exemptions_are_not_in_core_vocabulary` — verifies that ACTIVITY_TYPE_EXEMPTIONS (29 AS2 Activity type strings) never appear in CORE_VOCABULARY; the exemption set is shrink-only.

PR: <https://github.com/CERTCC/Vultron/pull/1531>
