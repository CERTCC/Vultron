---
source: ISSUE-752
timestamp: '2026-06-09T20:42:08.879055+00:00'
title: God node decomposition for case creation BT nodes
type: implementation
---

## Issue #752 — God node decomposition: split EmitCreateCaseActivity, SendOfferCaseManagerRoleNode, and RecordCaseCreationEvents

Decomposed the three case-creation BT god nodes into composed subtrees with explicit leaf nodes so responsibilities are isolated and independently testable. Added unit tests for each new leaf path, including missing-context failure paths for the case creation event leaves, and preserved existing create-case behavior.

PR: [#853](https://github.com/CERTCC/Vultron/pull/853)
