---
source: CONCERN-5885
timestamp: '2026-11-06T15:19:18.998876+00:00'
title: CM-14-011 and CM-22-006 disagree on who the case Create is addressed to
type: learning
---

Theme: theme:requirements-traceability — the case-initialization and CASE_MANAGER case-creation requirements agree on who receives the `Create(VulnerabilityCase)`.

## Summary

CM-14-011 says step 4 of case initialization MUST queue a `Create(VulnerabilityCase)` "addressed to the reporter". CM-22-006 says the CASE_MANAGER MUST address that `Create(VulnerabilityCase)` "to the report receiver, the CASE_OWNER, only", with the report receiver then introducing the CASE_MANAGER to the reporter (CBT-01-001, ADR-0132). Both are MUST; both cannot be met as written.

## Surface Symptom vs. Underlying Problem

- Surface: two statements name different recipients for one activity.
- Underlying: the CM-14 six-step sequence (CM-14-001, steps CM-14-008 to CM-14-013) predates CASE_MANAGER-authoritative creation (ADR-0041). CM-12-001 now routes creation through CM-22-001, and CM-22-001 records `supersedes` CM-14-001 "in multi-actor deployments". So CM-14-011 may already be superseded in the deployments the prototype runs, but nothing on CM-14-011 says so, and a reader of CM-14 alone gets the old recipient. Whether CM-14 still binds anywhere (single-actor deployment) is the open question.
- Correct and should stay: CM-22-006's recipient rule and the CBT-01-001 introduction step (ADR-0132).

## Category

Spec consistency (requirements contradiction).

## Severity

Medium: an implementer following CM-14-011 would send the case to the reporter directly, breaking the CBT-01 bootstrap trust path.

## Evidence

- `specs/case-management.yaml` CM-14-011, CM-22-006, CM-22-001 (`supersedes` CM-14-001, note: multi-actor deployments), CM-12-001.
- Found by the SR-13 link audit of CM and PRM (#5207, PR #5882).

## Impact if Ignored

The relationship graph cannot say which recipient rule binds; agents loading CM-14 alone implement the wrong recipient.

## Suggested Action

Decide whether CM-14 still has a deployment where it binds. If not, retire or rewrite CM-14-011 to match CM-22-006 (and record `supersedes` from CM-22-006 on CM-14-011 if an exception remains); if so, scope CM-14-011 to that deployment explicitly.

**Resolved**: 2026-11-06 — resolved in the planning PR by spec edits; no implementation issue needed (code and tests already conform). CM-14-011 now addresses the case Create to the reporter when the CASE_MANAGER is the report receiver, otherwise to the CASE_OWNER only (CBT-01-001, CBT-01-010); CM-22-006 is scoped to the separate-manager path; CM-14-001's 'single-actor only' note and CP-09-001's supersedes edge are removed, since the CASE_MANAGER runs the sequence on the proposal path.

Docs PR: https://github.com/CERTCC/Vultron/pull/6027.
