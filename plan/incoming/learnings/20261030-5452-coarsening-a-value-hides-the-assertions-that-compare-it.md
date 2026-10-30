---
title: "Deliberately coarsening a value makes every assertion that compares two of them pass vacuously, and the coarsening is why nobody sees it"
type: learning
timestamp: "2026-10-30T18:10:00Z"
source: ISSUE-5452
signal: theme-candidate
---

**Trigger.** You are about to reduce a value's resolution on purpose — truncate
a clock, round a measurement, bucket an id, quantise a score — or you are
raising the resolution of one that was reduced earlier, and tests that compare
two such values start failing.

**Claim.** An assertion that two of these values differ, or that one follows
another, cannot fail while the coarsening makes them equal. The assertion still
runs, still reads as a guarantee, and proves nothing. The coarsening is what
hides it: a reviewer checks whether the assertion is *correct*, not whether the
value it compares can vary, and the value cannot vary by design. So the vacuity
survives review and arrives the moment the resolution is raised, in whatever
code the raise touches — which is rarely the code the assertion guards.

**Evidence.** #5452 raised `now_utc()` from whole seconds to microseconds. Three
assertions that had been passing turned out to be vacuous, and only one of them
was about timestamps:

- #5510's ratchet "a datalayer read mints no id and reads no clock" had been
  green since the day before, while the outbox read stamped its response
  collection from the clock on every request. Two reads inside one second gave
  one string, so the comparison held. The defect it was written to catch was
  live the whole time.
- `test_announce.py` built two copies of one case and relied on them deriving
  the same genesis hash; they agreed only because both were stamped in the same
  second.
- `test_add_participant_status_bt.py` seeded a case status and asserted the
  committed one sorted after it.

The suite had 23,438 passing tests before the raise and three of them were
load-bearing fictions.

**What would confirm it.** A second instance outside the clock: a rounded
duration, a bucketed id, a truncated hash prefix, or a quantised score whose
coarsening makes a difference-assertion unfallible. The claim is about
precision reduction generally; so far every witness is one clock change.

**How to apply.** When you coarsen a value, grep the suite for assertions that
compare two of them (`!=`, `<`, `>`, "differs", "after", "newer") and check each
one can still fail — a coarsened comparison needs a test that pins the
resolution, not just the ordering. When you raise a resolution, expect failures
in code the change does not touch, and read each as a defect report before
assuming the test is stale: the first instinct, that a newly-red time assertion
needs its expectation updated, is how a live read-side clock read would have
been papered over here. Related: `notes/testing-pitfalls.md` § assertion-quality
traps.
