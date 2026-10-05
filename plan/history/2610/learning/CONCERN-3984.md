---
source: CONCERN-3984
timestamp: '2026-10-05T17:18:31.958592+00:00'
title: Two-sided pin-to-live-count ratchets race every concurrent PR
type: learning
---

## Concern

Ratchets that pin a count to the exact live value in both directions (MS-10-006's `VERIFICATION_CEILINGS`) are correct on the PR that sets them and wrong on every other PR in flight. A sibling PR that moves the count is green on its own base, and the merge is red on `main` and on every branch rooted at it. Witnesses: #3974/#3975 (project kind pinned 1004, live 1003) and PR #3983. Learning: `20260930-3828-a-pin-to-live-count-ratchet-races-every-pr-in-flight-when-it-lands.md`.

## Planning outcome

Two races: a pin introduced while another PR moves the count, and two PRs making the identical edit to the same ceiling line, which git merges cleanly to a wrong number. Options weighed: better failure message only; split the arms (above fails everywhere, below only on main); compare to `origin/main`; a central ID file; a per-requirement marker. Chosen: a per-requirement `verification_debt: '#N'` marker, so two PRs conflict only when they edit the same requirement, plus a PR-only growth guard that fails when a PR adds a marker versus `origin/main`.

**Resolved**: 2026-10-05 — implementation tracked in #4199 (marker, per-item test, migration, spec/note updates) and #4200 (growth guard).
Docs PR: <https://github.com/CERTCC/Vultron/pull/4201>.
