---
source: CONCERN-2415
timestamp: '2026-08-20T15:59:03.144634+00:00'
title: No post-merge CI protection on main — failures are silent
type: learning
---

## Summary

The CI pipeline validates PRs before merge but has no post-merge protection
for `main`. When Demo Integration or Invariant Harness jobs break on `main`,
no alert fires, no issue is filed, and no notification reaches the team.
Breakage sits undetected until someone manually checks the Actions tab.

## Surface Symptom vs. Underlying Problem

**Surface symptom:** `main` is occasionally found broken by someone trying to
branch from it or cut a release.

**Underlying problem:** The CI pipeline was designed as a merge gate
(one-directional: block bad PRs). There is no scheduled or push-triggered run
of Demo Integration or Invariant Harness on `main`, and no failure-notification
mechanism. The feedback loop is structurally asymmetric: CI blocks bad PRs but
does not protect `main` from the cumulative effect of edge cases that
individually passed PR CI. Issues #1859 and #2132 documented this gap; both
were closed without a follow-on issue or implementation.

## Resolution

**Resolved**: 2026-08-20 — implementation tracked in #2438 (composite action +
workflow wiring), #2439 (verification test), #2440 (bot-managed label guard).

Docs PR: <https://github.com/CERTCC/Vultron/pull/2437>.
Notes: `notes/demo-ci-invariants.md` § "CI Failure Notification".
Spec: `specs/ci-security.yaml` CISEC-05-001 through CISEC-05-005.
