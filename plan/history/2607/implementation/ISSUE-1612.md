---
source: ISSUE-1612
timestamp: '2026-07-22T19:13:48.528910+00:00'
title: split large notes/ files into focused topic-cluster files
type: implementation
---

## Issue #1612 — Split large notes/ files into focused topic-cluster files

Split 5 oversized notes files (bt-fuzzer-nodes-report-management.md 2189L,
bt-integration.md 1800L, codebase-structure.md 752L, activitystreams-semantics.md
679L, triggerable-behaviors.md 678L) into 14 focused per-topic files.

Created: bt-fuzzer-rm-{validation,prioritization,id-assignment,fix,exploit,threat,
publication,reporting,closure}.md, bt-canonical-reference.md, bt-pitfalls.md,
codebase-structure-fastapi-patterns.md, activitystreams-state-update.md,
triggerable-behaviors-resolved.md.

Added BT-22-001/002/003 (BT layer dependency model) to behavior-tree-integration.yaml.
Updated notes/README.md and 5 AGENTS.md files with updated cross-references.

All ACs satisfied. PR: <https://github.com/CERTCC/Vultron/pull/1621>
