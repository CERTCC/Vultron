---
source: ISSUE-1721
timestamp: '2026-07-27T19:36:52.537844+00:00'
title: 'fix(demo): remove mail-carrying post_to_inbox_and_wait from demo scenarios'
type: implementation
---

## Issue #1721 — fix(demo): remove mail-carrying post_to_inbox_and_wait from all demo scenarios

Removed all cross-actor `post_to_inbox_and_wait` calls from six demo scenario files, replacing them with polling helpers that wait for real HTTP delivery. Added `wait_for_object_stored` polling helper and `TestWaitForObjectStored` unit tests. Self-delivery calls (CONCERN-1653 exception) preserved in fccv/fvcv handoff demos. AGENTS.md How-to-apply bullet corrected to cite `wait_for_object_stored`.

PR: <https://github.com/CERTCC/Vultron/pull/1730>
