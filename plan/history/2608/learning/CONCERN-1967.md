---
source: CONCERN-1967
timestamp: '2026-08-05T17:52:33.643926+00:00'
title: 'Demo CI pipeline is structurally inefficient: forced barrier between demo
  and invariant-harness jobs inflates PR wait time'
type: learning
---

## Summary

The demo CI pipeline (`demo-integration.yml`) imposes a full fan-in barrier
between the `demo` matrix and the `invariant-harness` matrix (`needs: demo`),
forcing every invariant job to wait for the slowest demo job before any
invariant job can start. The actual dependency is pairwise (fv→fv,
fvcv-handoff→fvcv-handoff, etc.), so the barrier introduces systematic lag
proportional to the variance in demo scenario runtimes. Beyond the structural
issue, the demo set may contain redundant coverage (simpler scenarios
exercising subsets of more complex ones), and unconditional triggering means
every PR touching `vultron/**` pays the full matrix cost regardless of whether
the change could affect demo scenarios at all.

Three independent inefficiency sources were identified and resolved to separate
implementation tracks:

1. **Fan-in barrier** — GitHub Actions has no native pairwise
   matrix-to-matrix `needs:` syntax. Merging jobs into one (Option A) was
   rejected because it loses the independent DEMOCI-04 pass/fail status
   signals. Expanding to 14 named jobs (Option B) was rejected because YAML
   maintenance cost grows 14× with no pairwise artifact ordering guarantee.
   The chosen approach (Option C) accepts the structural barrier and
   implements the missing DEMOCI-02-011 concurrency group, so superseded PR
   runs are cancelled — recovering the most common wasted-wait scenario.
   See ADR-0052.

2. **Scenario coverage redundancy** — A coverage matrix analysis is required
   to determine the minimum PR validation set vs. the full post-merge set.
   Milestone sets may have been copied across scenarios and may under-report
   what each scenario actually exercises. Tracked in #1996.

3. **Path filter over-triggering** — The `vultron/**` path filter may trigger
   the full matrix on type-annotation or docstring-only changes. Tracked in
   #1997.

**Resolved**: 2026-08-05 — implementation tracked in #1862, #1996, #1997.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1995>.
Spec: `specs/demo-ci.yaml` DEMOCI-06-001 through DEMOCI-06-003.
ADR: `docs/adr/0052-demo-ci-job-structure-barrier-accepted.md`.
