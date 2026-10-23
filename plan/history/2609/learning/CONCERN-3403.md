---
source: CONCERN-3403
timestamp: '2026-09-18T19:36:55.765886+00:00'
title: Relocating a documentation claim is not verifying it — sweeps need a verification
  budget
type: learning
---

## Summary

A mechanical pass over prose — a naming sweep, a Diátaxis extraction, a page
split — forces an agent to read claims it would otherwise skim. Two sessions
have now found real defects that way, in both cases as a side effect rather than
as the goal. The corollary is that a sweep which only *moves* text carries the
source's errors forward with full authority, and the act of copying is the
cheapest moment to catch them.

This is the second witness for a claim already in `plan/incoming/learnings/`,
which is why it is filed as an issue rather than a second learning file
(BW-07-006).

## The two witnesses

- **#3342 (CaseActor → CASE_MANAGER rename)**, recorded in
  `plan/incoming/learnings/20260917-3342-caseactor-rename-keeps-infrastructure-concrete.md`:
  "A naming sweep is a cheap way to surface these stale-premise landmines,
  because it forces you to read the rationale the term sits in." It surfaced
  CM-20-001/004/005 claiming to `refines:` CBT-01-003 while asserting its
  opposite.
- **#3002 (this session)**: extracting Explanation content copied a mermaid
  diagram from `acknowledge.md` onto a new `docs/topics/` page. Reading the
  diagram as a set of assertions rather than as page furniture exposed three
  wrong AS2 verb attributions (#3395) that had survived #2785, an issue whose
  express purpose was correcting accuracy errors in those same pages.

The shared claim: **re-reading in a new context is a different act from reading
in place.** In place, a diagram is furniture. Copied onto a page whose job is to
justify the design, the same diagram becomes a claim with a truth value.

## Why this is worth acting on

The failure mode is specific and recurring. A sweep's success criterion is
usually "all content accounted for", which a faithful copy satisfies perfectly
while propagating a false statement to a second location with more authority
than it had in the first. #3002 came close to shipping a new Explanation page
telling implementers to emit `Leave(VulnerabilityReport)`, an activity that
matches no registered `ActivityPattern`.

## Candidate responses

- Add a rule to `.claude/skills/shared/docs-style-guide.md` or the `write-docs`
  procedure: a claim being **moved or republished** must be verified against its
  authority (code, spec, or reference page) before it lands, and the move is not
  complete until it has been. Distinguish this from authoring new prose, where
  verification is already implied.
- Have `lint-docs` treat a wholesale copied block as a finding class of its own
  rather than as unchanged content, since copied content is exactly what its
  mechanical passes are least likely to question.
- Give `learn` and `decision-audit` an explicit expectation that a sweep budgets
  for verification, so "all content accounted for" stops being a sufficient
  completion test.

The right response is a judgment call; this issue records the pattern and the
evidence, not a decided fix.

## Reference

Source: #3002, corroborating the theme-candidate from #3342
Related: #3395 (the defects this instance surfaced), #3402 (the automated check
that would have caught this particular class)

**Resolved**: 2026-09-18 — implementation tracked in #3414.
Docs PR: <https://github.com/CERTCC/Vultron/pull/3415>.
