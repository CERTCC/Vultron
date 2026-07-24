---
source: CONCERN-1649
timestamp: '2026-07-23T20:55:08.945867+00:00'
title: Invariant harness hard gate + per-scenario invariant sets
type: learning
---

## Concern

The demo invariant harness (`EXPECTED_EVENT_TYPES`) runs as an `if: always()` CI job. When a demo run also fails, the invariant failure is easy to miss — reviewers focus on the primary failure. In PR #1590, a missing notes-exchange phase failed silently across multiple fix cycles for this exact reason.

Additionally, the current common event-type list assumes all scenarios share the same required phases. Scenarios have unique required phases that must not be collapsed into a single shared list.

**Resolved**: 2026-07-23 — implementation tracked in #1656.

Docs PR: <https://github.com/CERTCC/Vultron/pull/1655>.

Spec: `specs/demo-ci.yaml` (DEMOCI-04), `specs/multi-actor-demo.yaml` (DEMOMA-16).

Notes: `notes/demo-ci-invariants.md`.
