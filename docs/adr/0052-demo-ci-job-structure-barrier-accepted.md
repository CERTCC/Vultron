---
status: accepted-provisional
date: 2026-08-05
deciders: Allen D. Householder
consulted: []
informed: []
---

# Demo CI Job Structure: Accept Barrier + Concurrency Group Over Job Consolidation

## Context and Problem Statement

`demo-integration.yml` runs 7 demo scenarios and 7 invariant-harness jobs as
two GitHub Actions matrix blocks. The invariant-harness job declares
`needs: demo`, which — per GitHub Actions semantics — creates a **full fan-in
barrier**: every invariant job must wait for the slowest of all 7 demo jobs
before any invariant job can start. The actual logical dependency is pairwise
(fv-invariant depends only on fv-demo, not on fvcv-handoff-demo), so the
barrier introduces systematic lag proportional to the variance in demo scenario
runtimes.

Three structural options were evaluated for eliminating or reducing this lag.

## Decision Drivers

- DEMOCI-04-001: invariant failures MUST produce a **separate, independent
  pass/fail status** on the PR, visible even when the demo job fails.
- DEMOCI-02-011: the workflow MUST define a `concurrency` group to cancel
  superseded PR runs — this is an unimplemented MUST already in spec.
- Workflow maintainability: the YAML must remain easy to add new scenarios to.
- GitHub Actions platform constraints: `needs:` on a matrix job name waits for
  **all** entries of that matrix, with no native pairwise-dependency syntax.

## Considered Options

- **Option A — Merge demo + invariant into one job per matrix entry** (single
  13-step matrix job that runs both the demo and pytest inline)
- **Option B — Expand to 14 named jobs** (replace both matrix blocks with 14
  individually-named jobs so each invariant job can `needs:` its specific demo
  job by name)
- **Option C — Accept barrier, add concurrency group** (keep the current
  two-matrix structure; implement the already-specified DEMOCI-02-011
  concurrency block that was never wired in; eliminate the pairwise ordering
  problem by cancelling superseded PR runs early)

## Decision Outcome

Chosen option: **Option C — Accept barrier, add concurrency group**, because:

- Option A violates DEMOCI-04-001: merging both steps into one job collapses
  the two independent pass/fail statuses into one. A reviewer can no longer
  distinguish "demo passed, invariant failed" from "demo failed" — exactly the
  failure mode that motivated the separate-job design.
- Option B achieves pairwise ordering but multiplies YAML maintenance cost
  14×. Every new scenario requires two new named jobs; the YAML grows
  non-linearly and there is no matrix inheritance to DRY it. Additionally,
  even with named pairwise `needs:`, GitHub Actions does not guarantee that
  artifact uploads from a named job are visible to its dependent before the
  dependent starts; the download-artifact step already handles this correctly.
- Option C recovers the most impactful practical improvement: on active PR
  branches, every push cancels the prior queued run, so the accumulated
  "all 7 demo jobs must finish before any invariant job starts" wall-clock cost
  only occurs **once per PR commit**, not for every intermediate push. The
  `cancel-in-progress: false` on main-branch runs preserves per-commit signals.

This decision is **accepted-provisional** because the scenario coverage split
(minimum PR validation set vs. full post-merge set) is not yet designed or
validated. When DEMOCI-06 is implemented — defining a minimum PR set and a
full post-merge set — this ADR should be revised to reflect whether the reduced
PR scenario set further mitigates the barrier impact.

### Consequences

- Good, because DEMOCI-02-011 (a MUST that was never implemented) is closed.
- Good, because superseded PR runs are cancelled, recovering CI minutes on
  active branches and giving faster per-commit feedback.
- Good, because the two-matrix structure is preserved and new scenarios require
  only two new matrix entries (one per block) per DEMOCI-03-004.
- Good, because DEMOCI-04-001's separate pass/fail signals are fully preserved.
- Neutral, because the fan-in barrier persists structurally on individual
  commits; it only manifests as lag when a PR push is not superseded by a
  later push.
- Bad, because genuinely pairwise dependency cannot be expressed in GitHub
  Actions without Option B's YAML explosion.

## Validation

The concurrency block (DEMOCI-02-011) is verifiable by inspection of
`demo-integration.yml`. The behaviour (cancel superseded PR runs, never cancel
main-branch runs) is validated by observing CI behaviour on a PR with multiple
rapid pushes.

## More Information

- Source concern: CERTCC/Vultron#1967
- Related implementation issue: CERTCC/Vultron#1862
  (push-to-main trigger + concurrency + cache-warm removal)
- DEMOCI spec: `specs/demo-ci.yaml` DEMOCI-02-011, DEMOCI-05
- Follow-on: CERTCC/Vultron#1794 epic — scenario coverage analysis will
  determine whether a minimum PR validation set can reduce the number of matrix
  entries that participate in the barrier, further reducing worst-case lag.
- Generated spec requirements: `specs/demo-ci.yaml` DEMOCI-06-001 through DEMOCI-06-003.
