---
source: CONCERN-2132
timestamp: '2026-08-11T17:01:14.329114+00:00'
title: CI failures on main are silent — no structured feedback loop from workflow
  failure to issue tracker
type: learning
---

## Summary

CI failures on `main` (push-triggered and scheduled workflows) are not reported
anywhere. There is no notification step, no issue filed, and no alert — the team
only finds out when someone manually checks the Actions tab or notices a broken
badge.

## Surface Symptom vs. Underlying Problem

**Surface symptom:** Individual CI runs show red, but no one is notified. The
failure sits unacknowledged until a developer happens to look.

**Underlying problem:** `main` has no failure alerting contract. The team
implicitly relies on reviewers noticing a broken status badge or stumbling across
the run — there is no structured feedback loop from CI failure back to the issue
tracker. This is a process gap, not just a missing step.

## Category

Observability / CI hygiene

## Severity

Medium — breakage can linger undetected; the longer it sits, the more PRs land
on a broken base and the harder the failure is to attribute.

## Evidence

The following workflows run on push to `main` or on a schedule but have no
on-failure notification step:

- `python-app.yml` (tests, linters, type checks, build)
- `demo-integration.yml` (full 9-scenario end-to-end suite)
- `spec-check.yml` (spec registry linter)
- `actions-lint.yml` (workflow file linter)
- `lint_md_all.yml` (Markdown linter)
- `stale_claim_sweeper.yml` (scheduled, no human watching)
- `quarterly_tag.yml` (scheduled, no human watching)
- `deploy_site.yml` (docs site deployment, push to publish branch)

No `ci:main-failure` label exists in the repo. No composite action for failure
notification exists under `.github/actions/`.

## Impact if Ignored

Broken `main` goes undetected until a developer is blocked or manually audits the
Actions tab. Developers may unknowingly stack PRs on a broken base. Scheduled
workflow failures (sweeper, quarterly tag) have no visibility at all.

**Resolved**: 2026-08-11 — implementation tracked in #2184.
Docs PR: <https://github.com/CERTCC/Vultron/pull/2183>.
Spec: `specs/ci-security.yaml` (CISEC-05).
ADR: `docs/adr/0055-ci-failure-alerting-via-github-issues.md`.
