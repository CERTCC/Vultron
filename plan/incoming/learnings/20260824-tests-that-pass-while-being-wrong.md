---
title: Five ways a Vultron test passed while being wrong, and what they share
type: learning
timestamp: 2026-08-24
source: ISSUE-2238
signal: test-quality
---

Working #2238's integration tier from 8 failures to 1 turned up more *passing*
tests that were wrong than failing tests that were right. Collected because the
five share one mechanism and one countermeasure.

**1. Asserting absence from a store nothing writes.** Two `TestDeliveryIsolation`
tests asserted a store did *not* contain something, reading `iso.dl` — which
defaults to `actor_slug="primary"`, an actor those tests never create. Nothing
writes there, so the assertions could not fail however broken isolation was. The
isolation test is now two-sided: the vendor's actor must be *present* in the
vendor's own store before its absence from the finder's means anything. **Third
occurrence** of this `actor_slug` default footgun — dangerous precisely because
forgetting it yields a pass.

**2. An invariant satisfied by omission.** #2505's
`test_all_participants_rm_closed_at_scenario_end` asserts every tracked
participant reaches RM.CLOSED. It passes because the CaseActor is **absent from
the ledger entirely**, not because it reaches CLOSED. Dumping the computed dict
was the only way to see this: `{'vendor': 'CLOSED', 'finder': 'CLOSED'}`.

**3. A swallowed 4xx.** `completed_workflow` skipped engage-case, so RM was still
VALID and `notify-fix-ready` was correctly refused with 422. `demo_step` logs 🔴
and continues, so the fixture reported success with its entire fix-lifecycle half
unexecuted, and three tests asserted against that state.

**4. A test passing because a double was unfaithful.**
`verify_replica_state`'s documented `Raises: AssertionError` path was **dead code**
against the real client, which raises `HTTPStatusError` on 404. The demo double
raised `AssertionError` instead, which is exactly what the test expected — so the
test passed *because* the double was wrong, and broke the moment the double was
corrected. The production defect had been live the whole time.

**5. A timeout reported instead of the error.** `_poll_until` swallowed exceptions
and then raised a bare "Timed out waiting for …". A condition that never *ran* is a
different fault from one that ran and stayed false, and both read identically. It
now names the last swallowed exception, which is what proved the embargo failure
was real rather than a masked read error.

**What they share.** In every case the test's *subject* and the thing it actually
observed were different objects, and nothing in the pass/fail signal distinguished
them. A store belonging to nobody, a participant absent from a list, a step that
logged and continued, a double diverging from the real client, an exception
converted to a timeout.

**How to apply.**

- For any assertion of the form "X does not contain Y", first assert something
  *does* contain Y. A negative assertion alone cannot distinguish "isolated
  correctly" from "looking in the wrong place".
- When a helper swallows and continues (`demo_step`, `demo_check`, best-effort BT
  nodes), the fixture built on it needs an independent check that the step
  actually happened. A 🔴 in a log is not a test failure.
- A test double that diverges from the real client will eventually make a test
  pass for the wrong reason. Prefer making the double faithful even when it
  *raises* the visible failure count — that is the point (see `85f6c245`, which
  took `test_fv_demo` 4 → 6 deliberately).
- When a poll or retry gives up, report what it saw, not merely that it gave up.
- Related: [[a-clean-merge-is-not-a-working-merge]] — a passing suite after a
  clean merge is the same illusion in a different costume.
