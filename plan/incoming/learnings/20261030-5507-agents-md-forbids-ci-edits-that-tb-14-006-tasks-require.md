---
title: >-
  AGENTS.md says agents MUST NOT touch CI, but TB-14-006 and its Tasks are
  agent-built workflow edits
type: learning
timestamp: '2026-10-30T19:00:00+00:00'
source: ISSUE-5507
signal: spec-contradiction
---

## Trigger

You pick up a Task whose ACs edit `.github/workflows/*.yml` (a `timeout-minutes`
cap, a `notify-failure` step, a path filter), and the root `AGENTS.md` § "Scope
of Allowed Work" says agents MUST NOT "touch CI/deployment/secrets".

## Claim

The scope rule and the CI specs disagree. TB-14-006 and CISEC-05 oblige
edits to every workflow, and agents file and build those Tasks (PR #5495,
PR #5557), yet the rule as written forbids them all. The likely intent is
narrower: no changes to secrets, deploy credentials or the release pipeline.
The rule should say so, or name which workflow edits need human review.

## Evidence

Issue #5507 needed caps in 17 workflows, including `deploy_site.yml` (Pages deploy)
and `quarterly_tag.yml` (release tag). The work went ahead only because the
user named the issue explicitly. Without that, an agent following the rule
would either refuse the Task or edit against its own scope rule.
