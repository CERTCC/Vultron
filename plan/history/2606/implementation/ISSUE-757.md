---
source: ISSUE-757
timestamp: '2026-06-08T13:46:59.872317+00:00'
title: Extract shared participant-finder BT node
type: implementation
---

## Issue #757 — Extract shared FindParticipantNode to eliminate VerifySenderIsParticipantNode / CheckParticipantExists duplication

Implemented a shared FindParticipantByActorIdNode in `vultron/core/behaviors/helpers.py` and refactored both behavior nodes to delegate to it, removing duplicated participant lookup logic while preserving existing status-tree case resolution behavior.

Added helper-node tests to cover participant lookup success and failure paths.

PR: <https://github.com/CERTCC/Vultron/pull/819>
