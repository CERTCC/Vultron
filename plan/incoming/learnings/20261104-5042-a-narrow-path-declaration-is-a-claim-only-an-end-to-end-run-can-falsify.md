---
title: >-
  A narrow path declaration is a claim about who receives a message type, and no
  unit test can falsify it — only an end-to-end run shows who really does
type: learning
timestamp: 2026-11-04T00:00:00+00:00
source: ISSUE-5042
signal: theme-candidate
---

`paths=` is the first thing a received tree declares that is a claim about the
*world* rather than about the tree. Every other factory argument is checkable
from the tree: a guard either runs read-only or it does not, an emit either sits
behind a gate or it does not. A declaration says "no actor on this path ever
receives this type", and the tree cannot be asked whether that is so.

In #5042 the `Announce(EmbargoEvent)` tree was declared participant-replica
only, reasoning that the CASE_MANAGER sends the announcement and so never
receives it. Every unit test agreed, because each one builds the tree and runs
its stage at a store the test itself set up. The exchange demos disagreed: in
`establish_embargo_demo` the Vendor is the case owner *and* its CASE_MANAGER, so
it is a participant of its own case and the announcement reaches it. On `main`
that delivery was applied as a no-op — the effect is gated on
`AwaitsEmbargoEndingNoticeNode`. The declaration turned it into `REFUSED`, which
`expect_no_inbox_refusals` caught in CI and nowhere earlier.

What generalises, for #5043, #5044, #5785 and any later wave:

- **Derive the declaration from who is addressed, not from who sends.** "The
  CASE_MANAGER sends this, so it does not receive it" is a non-sequitur in a
  protocol where one actor holds several positions. The prototype's common shape
  is owner-as-manager, so "the manager is not a participant of its own case" is
  false by default, not by exception.
- **A narrowing declaration is only as good as the run that exercised it.**
  Before declaring a path *out*, name the end-to-end scenario that would deliver
  the type to it and check that scenario. `test/demo/` is marker-gated, so a
  targeted local run misses it entirely: it needs `-m ""`.
- **A widening declaration is cheap; a narrowing one is a load-bearing claim.**
  Declaring both paths costs a stage that admits everyone and leaves the tree's
  own gates to decide, which is what the code did before. Declaring one path
  converts every delivery on the other into a refusal, and a refusal is visible
  to the sender.
- **The refusal is the tell.** A declaration that is wrong does not fail quietly:
  it reports `REFUSED` with a reason naming the receiver. Any assertion that a
  scenario produces no inbox refusals is therefore the cheapest oracle for a
  declaration, and the only one that reads the real roster.
