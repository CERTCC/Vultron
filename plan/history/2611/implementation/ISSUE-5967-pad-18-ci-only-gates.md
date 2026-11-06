---
source: ISSUE-5967-pad-18-ci-only-gates
timestamp: '2026-11-06T20:03:52.681372+00:00'
title: PAD-18 states the CI-only test gates
type: implementation
---

Closes #5967 (Epic #5944). PR: https://github.com/CERTCC/Vultron/pull/6061

## What landed

The prepared ADR-0179 amendments to the `PAD-18` group of
`specs/parallel-development.yaml`, now that ruleset `main-3 Require CI gate` is
active on `main` with no bypass actors. The full unit and integration suites,
pyright, the heavy `prepush-ci-mirror` checks and the scratch-merge tests are
stated as CI-only gates; the dev container keeps ruff, mypy, the targeted tests
and the cheap mirror checks.

- `specs/parallel-development.yaml`: amended the `PAD-18` group description and
  thirteen items (`-001`, `-003`, `-004`, `-008`, `-009`, `-010`, `-012`,
  `-015`, `-016`, `-017`, `-023`, `-024`, `-025`), and added `PAD-18-027`
  through `-030` (no local pyright; a draft first push; ready only on green CI;
  the first draft CI run is not a fix round).
- `docs/developer/how-to/fix-your-first-bug.md`: the `check-docs-sync` update —
  two passages told a human contributor to run the full suite locally before
  pushing, which the amended `PAD-18-008` forbids.

## Why it waited

#5946 shipped ADR-0179 with only `PAD-18-026` and `PAD-18-031`, because the
remaining amendments forbid local gates while `PAD-18-031` forbids dropping a
local check before GitHub enforces the equivalent CI check. #5945 (the ruleset)
and #5971 (live verification on a real docs-only PR and a real failing PR)
closed that precondition, so the rest of the amendments landed as one unit.
Provenance for every amendment is the maintainer's approval on
https://github.com/CERTCC/Vultron/issues/5946#issuecomment-6667648144.

## Re-applied by hand, not cherry-picked

The prepared text on `prep/5946-pad-18-amendments` (`3b5ccf9e6`) was cut before
several unrelated spec changes landed, so its diff against `main` mostly
reverted newer work. Only the hunks inside the `PAD-18` group were amendments;
each was re-applied onto `main`'s current text. Discarded as stale reversions:
the `PAD-02-041` deletion, the recalibrated `PAD-05` AC bands and diff ceilings
with the `PAD-05-011` rationale and `PAD-05-013`, the `PAD-15` `TestReviewCeiling`
rename, the `PAD-16` `needs-decomposition` rename, and the `PAD-18-032`
deletion. Lines 1-2602 of the shipped file are byte-identical to `origin/main`.

## Sequencing left open on purpose

Prose in `AGENTS.md`, several `.agents/skills/`, `test/AGENTS.md`,
`.github/copilot-instructions.md`, two `notes/` files and
`vultron/metadata/planning/ci_mirror/_registry.py`, plus ten
`@pytest.mark.spec` markers, still name the superseded statements. Each site
belongs to an open sibling blocked by #5967 — #5948 (first-push gate, draft
PRs), #5949 (mirror checks, pyright), #5950 (scratch-merge tests) — which
changes the behavior in the same commit as its prose. Editing it here would
document a gate the skills do not yet implement.

## ADR-0179 status

Stays `proposed`, and that is its epoch: MS-14-007's day 14 is 2026-11-19, and
every `PAD-18` item citing `ADR-0179` verifies by Inspection with no test path,
so MS-14-010 does not fire. `tree_dependents()` reports no dependent, and
`adr-lifecycle-check` exits 0 on this tree and with `--base origin/main`.

