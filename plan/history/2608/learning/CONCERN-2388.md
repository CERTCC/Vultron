---
source: CONCERN-2388
timestamp: '2026-08-21T16:41:57.775935+00:00'
title: 'concern: build→learn→specs pipeline has no gate for ''is this a system requirement?'''
type: learning
---

The `build` → `learn` → `specs/` pipeline has no gate for "does this qualify as a system requirement?", causing implementation details (file paths, demo scripts, agent guidance) to accumulate as `priority: MUST` requirements in `specs/`. Five targeted changes to `upward-reflection.md`, the `learn` skill, the linter, the meta-spec, and `specs/AGENTS.md` close the gap.

**Surface symptom vs. Underlying problem:**

Surface symptom: ~1,000 `project`/`process`-kind MUST requirements describing file locations, demo step ordering, and agent instructions rather than observable system behavior.

Underlying problem: Three absent quality gates, each independently sufficient to cause the problem:

1. `upward-reflection.md` spec-gap signal is too broad — "Was any behaviour implemented or fixed that has no existing spec entry?" fires on any implementation action. No qualifier for "externally-observable" or "protocol-visible" behavior.
2. `learn` skill has a completion imperative with no filter — "A lesson is not complete until it has been promoted to `specs/`, `notes/`, or `AGENTS.md`." For `signal: spec-gap`, the instruction is "Write the missing spec requirement" with no gate question.
3. Linter enforces structure, not substance — MS-05-003 is a hard MUST in `meta-specifications.yaml` but has no linter check. Implementation-detail requirements pass all linter checks perfectly.

**Evidence:**

- 949 `project`/`process` MUST requirements identified by corpus analysis (2026-08-19).
- Signal-word breakdown: 208 organization/path, 113 demo/script, 34 agent guidance, 24 naming convention, 24 coding practice, 467 ambiguous.
- All 70+ spec files share creation date 2026-04-27 (git log `--diff-filter=A`).
- Related: #2382 (missing verification criteria — the downstream symptom of the same root cause).

**Resolved**: 2026-08-21 — implementation tracked in #2466.
Docs PR: <https://github.com/CERTCC/Vultron/pull/2465>.
Spec: `specs/meta-specifications.yaml` (MS-10-003, MS-10-005).
Notes: `notes/specs-vs-adrs.md`.
