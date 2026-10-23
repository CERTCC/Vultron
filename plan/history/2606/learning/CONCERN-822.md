---
source: CONCERN-822
timestamp: '2026-06-08T14:40:57.053459+00:00'
title: Participant lookup canonical surface
type: learning
---

## Summary

Participant lookup logic currently spans two case participant surfaces (`case_participants` and `actor_participant_index`), and this split has caused regressions when shared BT/use-case lookup paths only honor one representation. We should remove ambiguity by adopting a single canonical surface and treating mismatches as explicit errors.

## Category

- [ ] Top risk
- [ ] Technical debt
- [ ] Security
- [ ] Performance / scaling
- [x] Fragile / high-churn area
- [ ] Other

## Severity

medium

## Evidence

- `vultron/core/models/case.py`
- `vultron/core/use_cases/_helpers.py`
- `vultron/core/behaviors/report/nodes/conditions.py`
- `test/core/use_cases/triggers/test_case_engage_defer.py`
- `test/core/use_cases/triggers/test_trignotify.py`

## Impact if Ignored

Participant-related workflows will keep regressing depending on which surface fixtures/callers populate, causing brittle BT behavior and hard-to-diagnose state drift across status/embargo paths.

## Suggested Action

Adopt a single canonical participant surface and remove dual-path lookup behavior. Fix remaining narrow call sites in one pass, then fail fast when lookup data does not satisfy the canonical contract instead of silently falling back.

**Resolved**: 2026-06-08 — implementation tracked in #824 and #825.
Docs PR: <https://github.com/CERTCC/Vultron/pull/826>.
Notes: `notes/case-state-model.md`.
