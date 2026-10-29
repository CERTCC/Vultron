---
source: CONCERN-5496
timestamp: '2026-10-29T20:31:37.910413+00:00'
title: CI workflows outside python-app.yml have jobs with no timeout-minutes cap
type: learning
---

Theme: theme:test-and-ci — every CI job ends a hang within minutes instead of running to GitHub's default limit.

## Summary

PR #5495 (for #2076) capped every job in `python-app.yml` with `timeout-minutes`
and added TB-14-006 for that file. Most other workflows still have jobs with no
cap, so a hang there holds a runner until GitHub's 6-hour default and shows as
`cancelled` in `gh pr checks`.

## Evidence

Jobs (`runs-on`) vs. `timeout-minutes` lines per workflow on 2026-10-29 include:
`ui.yml` 2/0, `spec-check.yml` 4/0, `verification-debt-owners.yml` 2/0,
`demo-integration.yml` 4/2, and one uncapped job each in `actions-lint.yml`,
`adr-lifecycle.yml`, `adr-status-drift.yml`, `ci-main-failure-label-guard.yml`,
`deploy_site.yml`, `docs-build-check.yml`, `epic-needs-planning.yml`,
`label-to-issue-type.yml`, `lint_md_all.yml`, `pr-size-label.yml`,
`quarterly_tag.yml`, `ratchet-baseline-owners.yml`, `stale_claim_sweeper.yml`.

## Open question

Should TB-14-006 widen from `python-app.yml` to every workflow job (with a test
over `.github/workflows/*.yml`), or only the PR-gating workflows? The #2076
criterion approved by the user covered `python-app.yml` only, so this was not
done there.

Where: .github/workflows/

**Resolved**: 2026-10-29 — implementation tracked in #5507. Docs PR: <https://github.com/CERTCC/Vultron/pull/5506>. Spec: `specs/testability.yaml` (TB-14-006 widened to every workflow). Notes: `notes/ci-workflow-authoring.md`.
