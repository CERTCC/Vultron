---
source: CONCERN-2137
timestamp: '2026-08-10T18:25:05.634254+00:00'
title: Parallel fix PRs to a shared CI suite need an integration branch as the cumulative
  gate
type: learning
---

## The problem

There are currently 4+ distinct demo-CI failures on `main` spanning at least 2
root-cause classes. Open PRs (#2127 and whatever follows) each target `main`
directly. This creates a verification gap:

- Each PR author can only confirm their own scenario passes.
- None can confirm they have not perturbed the other 6 failing scenarios.
- The last known-green Demo Integration baseline was before 2026-08-07 — over
  3 days ago. Any PR that claims "demo CI passes" is verifying against a
  partial picture.

## Why this matters

Demo Integration failures are silent by default (see #2132). Without a
baseline, a PR that fixes its own scenario and accidentally breaks a
currently-passing scenario (fv, fcv-reject demo) could merge undetected.

## Proposed strategy: integration branch

1. **Open a single `fix/demo-ci` branch** off current `main` as the integration
   target for all child fixes of epic #2136.
2. PRs for #2120, #2135, #2134, #2121 all target `fix/demo-ci`, not `main`.
3. **Run Demo Integration against `fix/demo-ci`** after each child PR merges
   into it — this is the cumulative gate.
4. Only when all 9 Demo Integration jobs are green on `fix/demo-ci` does that
   branch merge to `main`.

**Resolved**: 2026-08-10 — implementation tracked in #2139.
Docs PR: <https://github.com/CERTCC/Vultron/pull/2138>.
