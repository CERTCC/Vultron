---
source: CONCERN-2004
timestamp: '2026-08-05T20:31:36.136682+00:00'
title: DEMOMA-19-008 phantom conftest.py reference; spec path-existence lint
type: learning
---

## Original concern

`DEMOMA-19-008` (MUST) ended with: "The harness MUST be added to
`test/ci/invariants/conftest.py` under the `fcvcv` scenario key." No such file
existed, and no prior scenario harness registered anywhere — each of the eight
harnesses hardcoded its own `devlogs/<scenario>/` path. So the clause could not
be satisfied as written. `test_fcvcv_invariants.py` (PR #1962) followed the
established pattern instead, satisfying the spec's intent while formally
violating its letter.

Found during `/pr-ship` triage of PR #1962 (finding
`phase5-demoma-19-008-conftest-stale-0`). Not a defect in that PR.

## Verdict: the spec was wrong, not misled

The framing question that unlocked this was "is the spec just wrong, or was it
misled?" Provenance answered it:

- The clause was authored in `439cead6` ("docs: plan issue #1217"), a *planning*
  commit that wrote all 9 DEMOMA-19 entries spec-first, before any FCVCV code
  existed. There was no implementation to describe.
- `test/ci/invariants/conftest.py` has never existed on `main` —
  `git log --all --diff-filter=A` finds one adding commit, not an ancestor of
  `origin/main`.
- No scenario-keyed registry exists anywhere under `test/`.
- The three prior harness clauses (`multi-actor-demo.yaml:1241`, `1534`, `1761`)
  name the test file and stop. The generic clauses (DEMOMA-16-008, DEMOCI-04-004)
  say `test/ci/invariants/test_XXX_invariants.py` — the per-file pattern.

So this was not a premise that drifted. It was never true, and the surrounding
spec text pointed the other way. "Build the registry to make the spec true" was
only attractive while the clause looked like it might encode real intent.

## What the audit found

DEMOMA-19-008 was not isolated. A path-existence scan over all spec statements
found **18 clauses across 13 phantom paths**, most stale after a file move or a
module-to-package refactor: `vultron/config.py` (now a package),
`sync_activity_port.py` (renamed), `specs/architecture.md` (wrong extension),
`.github/skills/` (moved to `.claude/skills/`), and others.

Three needed semantic rewrites rather than path fixes, because the referenced
*concept* was gone: UCORG-02-001/002 (`USE_CASE_MAP` replaced by
`SEMANTIC_REGISTRY`), PD-06-004/005 (`plan/PRIORITIES.md` deliberately archived
in `51fa5aee4`, migrated to the Project #24 `Schedule` field).

## Key distinction: statement vs. rationale

A scan of `rationale` found 5 more hits, but **2 were correct as written** —
rationale narrates history by design ("`specs/meta-specifications.md` has been
converted to `.yaml`", "if `CVDRole` stays in `vultron/core/states/roles.py`...").
Enforcing path existence on `rationale` would be wrong. The lint check scans
`statement` only. The 3 genuinely-stale rationale refs to the dead aggregate
invariant file were fixed by hand.

## The registry that does exist

The scenario-to-harness registry is the `demo`/`test_file` matrix in
`.github/workflows/demo-integration.yml`, duplicated verbatim across both the
`demo` and `invariant-harness` jobs. A `conftest.py` registry would have been a
*second* one.

## Resolution

Deviated from plan-only: the fix is docs + a lint check, which is what Phase 5
writes anyway, so routing it through an impl issue would be ceremony. The
universal-test dedup stayed an issue because it is a real code change across the
CI gate for all 8 scenarios.

- Amended DEMOMA-19-008 to describe the actual pattern and record that the CI
  matrix is the sole registry.
- Retargeted 15 stale path references; rewrote 3 clause groups semantically.
- Added MS-15-001 and `_check_phantom_paths` as a **hard error** — an advisory
  warning would have been the same failure mode being fixed. Escape hatch is
  `lint_suppress: [phantom_path_ref]`; placeholder forms and package-relative
  illustrations are exempt automatically.
- 6 regression tests: fires, passes on real path, both exemptions, rationale
  non-scanning, suppression. Verified by negative test that the check exits 1
  and names the path, and 0 once suppressed.

## Downstream: the clause had already propagated

Issue #1926 was open *only* because its AC-4f was this same phantom requirement,
copied verbatim out of DEMOMA-19-008 by `plan-issue`. AC-4a–4e were all already
shipped in #1962. The unbuildable AC was the sole reason the issue could not
close — a work item that could never be completed as written. AC-4f struck with
a triage comment. This is the landmine reproducing one level up from the spec,
which is the strongest argument for the lint gate.

Also noted: `test/ci/invariants/conftest.py` *is* added by #1976, holding
synthetic in-memory JSONL fixtures for unit-testing `common.py` — no scenario
mapping. After #1976 lands the filename resolves, making the phantom clause
*more* inviting, not less. Documented in `notes/demo-ci-invariants.md` so nobody
bolts scenario routing onto a fixtures module.

**Resolved**: 2026-08-05 — implementation tracked in #2007.
Docs PR: <https://github.com/CERTCC/Vultron/pull/2006>.
Spec: `specs/meta-specifications.yaml` (MS-15), `specs/multi-actor-demo.yaml`.
Notes: `notes/demo-ci-invariants.md`.
