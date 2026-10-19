---
source: CONCERN-4229
timestamp: '2026-10-19T13:43:43.682197+00:00'
title: Spec Check jobs share one failure label, so one job's success closes another
  job's CI-failure issue
type: learning
---

## Summary

Every job in `.github/workflows/spec-check.yml` (`spec-lint`, `spec-tests`, `docs-path-ratchet`) files and closes its CI-failure issue under the same `ci:workflow-spec-check` label. In `close` mode the `notify-failure` action closes every open issue carrying `ci:main-failure` plus that label. So when one job passes, it can close the failure issue another job just filed for a red `main`.

## Surface Symptom vs. Underlying Problem

- **Surface symptom:** a CI-failure issue for Spec Check opens and closes again within the same run, or never seems to stay open.
- **Underlying problem:** the failure signal is keyed by *workflow*, while notify and close run per *job*. Whichever job finishes last decides whether the issue survives. Each workflow with one job is correct and should be left untouched.

## Category

CI reliability / failure notification (CISEC-05).

## Severity

Medium. A red `main` can be reported and then silently auto-closed.

## Evidence

On a push to main where `spec-lint` fails and `spec-tests` passes: `spec-lint`'s notify step files "CI failure: Spec Check", and `spec-tests`'s close step (`if: success()`) then closes every open issue with that label pair. Which happens last depends on job completion order. The spec review of PR #4228 (#4199) surfaced this. That PR's new workflow, `verification-debt-owners.yml`, avoids the pattern by running its notify/close pair in only one of its two jobs.

## Impact if Ignored

A spec-corpus regression on `main` goes unreported, which is the failure the CISEC-05 issue exists to surface.

## Suggested Action

- Either give each job its own workflow label (`ci:workflow-spec-check-<job>`), or add one final aggregate job that notifies or closes once from `needs.*.result`.
- Audit every other workflow in `.github/workflows/` for more than one notify/close pair sharing a label.
- Extend `test/ci/test_workflow_failure_notification.py` so a shared label across jobs fails the test.

Governing specs: CISEC-05-001, CISEC-05-002, CISEC-05-003

**Resolved**: 2026-10-19 — implementation tracked in #4874.
Docs PR: <https://github.com/CERTCC/Vultron/pull/4873>.
Spec: `specs/ci-security.yaml` (CISEC-05-003 amended: one job per workflow owns the notify/close pair).
Notes: `notes/ci-workflow-authoring.md`.
Audit: `spec-check.yml` is the only workflow with more than one notify/close pair under one label.
