---
source: ISSUE-760
timestamp: '2026-06-09T13:54:24.821869+00:00'
title: Update-case BT integration
type: implementation
---

## Issue #760 — Add BT to UpdateCaseReceivedUseCase and fix post-BT cascade anti-pattern

Implemented a BT-backed update-case workflow with ownership and embargo checks, plus in-tree broadcast delivery. `UpdateCaseReceivedUseCase` now delegates to `BTBridge`, and the new tree keeps the broadcast inside the sequence instead of a post-execute cascade.

PR: [#837](https://github.com/CERTCC/Vultron/pull/837)
