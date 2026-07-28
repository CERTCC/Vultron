---
source: ISSUE-1574
timestamp: '2026-07-22T00:45:04.705274+00:00'
title: Replace six-kind spec taxonomy with four-tier portability hierarchy
type: implementation
---

## Issue #1574 — Replace six-kind spec taxonomy with four-tier portability hierarchy

Replaced the SpecKind enum and all 68 specs/*.yaml files with the four-tier portability hierarchy (protocol/architecture/project/process) per ADR-0038. Migrated ~76 contaminated domain specs via codebase-specific indicator scan. Added MS-12 classification decision tree to meta-specifications.yaml. Created 4 new docs pages, removed 6 old ones, updated all kind-aware tests.

PR: <https://github.com/CERTCC/Vultron/pull/1578>
