---
source: ISSUE-1652
timestamp: '2026-07-23T21:00:08.583246+00:00'
title: Extract-before-reuse rule for demo and codebase DRY
type: implementation
---

## Issue #1652 — Extract-before-reuse: MUST for vultron/demo, SHOULD for codebase

Added extract-before-reuse rule to three locations:

- `vultron/demo/AGENTS.md`: MUST rule — extract to `helpers/` before writing the second use of any pattern; no copy-paste from existing scenario files
- `specs/multi-actor-demo.yaml`: DEMOMA-16 group with DEMOMA-16-001 normative MUST spec entry; version bumped 1.0.0 → 1.1.0
- `AGENTS.md`: DRY SHOULD bullet in Code Organization cross-referencing the demo rule and DEMOMA-16-001

All linters clean; 5372 tests passed.

PR: <https://github.com/CERTCC/Vultron/pull/1657>
