---
source: CONCERN-3959
timestamp: '2026-10-07T20:17:31.167542+00:00'
title: Protocol-coverage ratchet is one-sided
type: learning
---

## Summary

`MAX_UNCOVERED_PROTOCOL_SPECS` in `test/architecture/test_spec_coverage_ratchet.py` is asserted one-sided (`uncovered <= ceiling`), so slack accumulates silently as markers are added without lowering the constant. When #3827 added `@pytest.mark.spec` markers for HP-09/HP-10 the live uncovered count was already 909 against a ceiling of 937 — 28 protocol requirements could have lost coverage with no test failing, which is the regression the ratchet exists to prevent. #3827 re-pinned the constant to the live count (906) but did not change the assertion's shape.

## Surface symptom vs. underlying problem

- **Surface**: the constant drifted 28 above the actual count.
- **Underlying**: the ratchet's own comment ("keep it pinned to the actual count — slack between the two is room for uncovered specs to grow unnoticed") is not enforced by the assertion. Nothing fails when the count drops below the ceiling, so re-pinning depends on an agent noticing. The MS-10-006 design for the verification ceiling is two-sided for exactly this reason (`notes/spec-authoring-rules.md` § "A Ratchet Needs an Owner and a Terminal State").

## Category / Severity

Test infrastructure fragility / Medium — no protocol requirement is currently uncovered beyond the pinned count, but the guard only holds while someone re-pins it by hand.

## Evidence

- `PYTHONPATH= uv run spec-coverage` reported `Uncovered protocol-kind requirements (909)` on `origin/main` at fb27b4367 while the constant read 937.
- The constant's comment history shows it was lowered by hand in #2607 and #2880 to close earlier slack.

## Impact if ignored

Up to (ceiling − live count) protocol requirements can lose their only test marker without CI noticing; the gap re-opens every time a PR adds markers without touching the constant.

## Suggested action

Make the assertion two-sided (`uncovered == MAX_UNCOVERED_PROTOCOL_SPECS`) with a message for each direction (new uncovered → add markers; resolved → lower the constant), mirroring the `KNOWN_VIOLATIONS` pattern (ARCH-18-001) and the MS-10-006 ceiling rules. Update SR-05-005's `verification:` to name the two-sided check. Consider the same audit for any other `<=` ceiling ratchet under `test/architecture/`.

Governing specs: SR-05-005, ARCH-18-001, MS-10-006

**Resolved**: 2026-10-07 — implementation tracked in #4315.

Planning outcome: the suggested two-sided equality was rejected because a
two-sided count pin races every concurrent PR
(`notes/testing-pitfalls.md`, #3984). Both `MAX_UNCOVERED_PROTOCOL_SPECS` and the sibling
`MAX_MISSING_STORY_SUPPRESSIONS` will be replaced by PR-only growth guards on a
shared base-vs-head helper; #4200 now reuses that helper. Spec rewrites
(SR-05-005, MS-12-007, MS-12-008) land with the code in #4315 so each
verification clause names a check that exists (MS-10-009).
