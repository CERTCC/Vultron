---
source: ISSUE-751
timestamp: '2026-06-09T15:32:14.472995+00:00'
title: Decompose CreateCaseParticipantNode into composed subtree
type: implementation
---

## Issue #751 — God node decomposition: split CreateCaseParticipantNode into composed subtree

Completed decomposition of CreateCaseParticipantNode into a composed behavior-tree subtree with named leaf nodes for participant status resolution, participant construction, attachment, event recording, conditional embargo signatory seeding, and outbox notification enqueue.

The embargo seeding step now runs as an explicit conditional subtree (Selector + guarded sequence), replacing inline branching while preserving CM-14-005 behavior.

Added unit coverage for subtree composition, conditional branch structure, and active-embargo signatory seeding.

PR: [#840](https://github.com/CERTCC/Vultron/pull/840)
