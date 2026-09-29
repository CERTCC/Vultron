---
title: "A spec clause that quotes an implementation idiom verbatim, paired with a ratchet test that asserts the quoted string, locks in whatever defect the idiom carries — the ratchet then enforces the bug"
type: learning
timestamp: "2026-09-29T18:10:00Z"
source: ISSUE-3293
signal: theme-candidate
---

## Observation

CISEC-05-006 was written as part of the #3249 fix and prescribed the exact
GitHub Actions expression the fix had used:
`contains(needs.*.result, 'failure') && !contains(needs.*.result, 'cancelled')`.
The ratchet test `test_notify_step_does_not_file_on_cancellation` then asserted
that the `!contains(..., 'cancelled')` substring was *present* in every
aggregate-keyed notify guard.

The idiom was wrong: a blanket cancellation exclusion cannot tell a laundered
failure from a genuine one, so it suppressed every genuine failure that shared
a run with a cancelled sibling job (#3293, #3294). The spec and the ratchet
together made the defect look like compliance. Removing the exclusion turned
the test red, so the fix had to rewrite the spec clause, the test, and the
note in the same PR (#3880).

## Claim awaiting a second witness

When a spec statement quotes a code expression rather than stating the
property the expression must have, the ratchet that checks compliance checks
the expression, not the property. Any defect in the quoted expression is then
protected by a passing test and a MUST. The recognisable trigger: a ratchet
fails because you removed or changed a code fragment the spec names verbatim,
and the spec's own rationale describes a property the fragment does not
actually guarantee.

The spec-authoring rules (`notes/spec-authoring-rules.md`, MS topic) say
nothing about quoting implementation idioms in `statement:`. If a second
instance appears, the fix is an MS rule: a statement names the property
(here, "a `failure` in the aggregate is always genuine; consumers skip on a
cancelled producer") and an `i.e.` example belongs in `rationale:` or
`verification:`, never in the normative text.
