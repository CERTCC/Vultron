---
source: CONCERN-5886
timestamp: '2026-11-06T15:19:21.888102+00:00'
title: CM-14-006 (SHOULD) and EP-04-003 (MUST) state the same shorter-of-two embargo
  rule
type: learning
---

Theme: theme:requirements-traceability — the shorter-of-two default-embargo rule is stated once, at one priority.

## Summary

CM-14-006 (SHOULD): when the reporter's `Offer(VulnerabilityReport)` carries an embargo proposal, case initialization SHOULD reconcile the proposed duration against the CASE_OWNER's published policy (its actor default, EP-04-003) and initialize the embargo at the shorter of the two.

EP-04-003 (MUST): where the sender proposes a duration and the CASE_OWNER's profile carries an embargo policy, the CASE_MANAGER MUST make the shorter of the two the active embargo at once.

Same rule, two priorities. CM-14-006 even cites EP-04-003 for the policy it reconciles against.

## Surface Symptom vs. Underlying Problem

- Surface: a duplicate requirement.
- Underlying: the priorities disagree, so a conformance reader cannot tell whether the shorter-of-two outcome is mandatory. CM-14-006 also names case initialization (the pre-ADR-0041 CM-14 sequence) as the actor, while EP-04-003 names the CASE_MANAGER.
- Correct and should stay: EP-04-003's MUST, which is what the code implements.

## Category

Spec consistency (duplicate at conflicting priority).

## Severity

Low: the code follows the MUST; the risk is a reader weakening it from CM-14-006.

## Evidence

- `specs/case-management.yaml` CM-14-006; `specs/embargo-policy.yaml` EP-04-003.
- Found by the SR-13 link audit of CM and PRM (#5207, PR #5882).

## Impact if Ignored

Two sources of truth for one rule drift further; the relationship graph records a link between restatements rather than a real dependency.

## Suggested Action

Retire CM-14-006 in favour of EP-04-003 (moving any story or test reference), or rewrite it as a pointer-free narrower case that `refines` EP-04-003 at MUST. Ask the maintainer which priority is intended before changing CM-14-006's obligation.

**Resolved**: 2026-11-06 — resolved in the planning PR by spec edits; no implementation issue needed (code and tests already conform). CM-14-006 retired in favour of EP-04-003 (MUST); its story link moved to EP-04-003; archive at plan/retired-specs/CM-14-006.md.

Docs PR: https://github.com/CERTCC/Vultron/pull/6027.
