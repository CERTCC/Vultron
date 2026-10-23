---
source: CONCERN-1859
timestamp: '2026-07-31T15:52:13.284665+00:00'
title: Demo CI never runs on push to main
type: learning
---

## Concern

`demo-integration.yml` triggers only on `pull_request` (to `main`) and
`workflow_dispatch`; its `invariant-harness` job runs `needs: demo` and is
therefore also PR-only. The only workflow that fires on `push: main` —
`demo-image-cache-warm.yml` — builds the demo Docker images but never runs the
demo or the invariant harness (it only populates the cache). As a result there
was no post-merge demo/invariant signal on `main`: a PR could be green and
merge, yet the demos on `main` could be broken with nothing to detect it.

**Underlying problem:** PR CI validates the *merge commit* (PR head merged onto
current `main` at test time), not the actual merged result of PRs that land
concurrently. Two PRs each green in isolation can interact to break `main`, and
nothing re-ran the demos/invariants against the real merged `main` HEAD — the
default branch had no demo/invariant baseline at all. The path-filtered PR
trigger only re-checks the demos when a *later* PR happens to touch a filtered
path, so a broken `main` could persist untested until then.

## Resolution

**Resolved**: 2026-07-31 — implementation tracked in #1862; merge-queue
follow-up deferred to Idea #1863.

Planning decisions (grill-me):

- Add a `push: main` trigger (same path filter) to `demo-integration.yml` so
  the full demo + invariant matrix runs against the merged `main` HEAD per
  qualifying merge. Cron rejected (blind window, range-level attribution);
  GitHub has no native "once per N hours" throttle for `push`. Cost bounded by
  path filter + concurrency group.
- DEMOCI-02-011 (`concurrency` group) was authored as SHOULD but never
  implemented on either workflow. Promoted to MUST and wired on both triggers
  via `cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}` — PR bursts
  collapse to newest; on-main runs always complete for per-commit attribution.
- The on-main run exports the `demo-integration-main` cache scope, making
  `demo-image-cache-warm.yml` redundant — it is removed.
- Merge queue (closes the concurrent-merge *interaction* gap) deferred to Idea
  #1863.
- No ADR — refines existing DEMOCI requirements (spec + notes only).

Docs PR: <https://github.com/CERTCC/Vultron/pull/1861>.
Spec: `specs/demo-ci.yaml` (DEMOCI-02-002/003/011, new group DEMOCI-05).
Notes: `notes/demo-ci-invariants.md` § "Post-Merge Validation on main".
