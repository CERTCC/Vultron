---
title: "Splitting a nested block moves its skip-on-failure semantics to a seam that a test of either piece cannot reach"
type: learning
timestamp: "2026-10-31T02:45:00Z"
source: ISSUE-5533
signal: theme-candidate
---

**Trigger.** You replaced one block whose nesting carried the behaviour — a
`demo_gate`, a `try`/`finally`, a context manager, a BT composite — with two
sequential pieces, and you unit-tested each piece.

**Claim.** The nesting *was* the failure behaviour: it decided what got
skipped. Split it and that decision moves to the caller that now sequences the
pieces, which is a place neither piece's test reaches. So a split needs a test
that drives the **composed caller** through the failure, not two passing tests
of the pieces; otherwise the one behaviour the split changed is the one nothing
checks.

**Evidence.** #5533 (PR #5588) split the case-invite chain into
`invite_and_await_delivery` and `answer_case_invite` so a story could put the
invitee's branch point between them. Three tests pinned the skip — a failed
invite trigger, a failed delivery lookup, and the success path — and all three
called the fragments directly. The runner that sequenced them emitted the step
mark between the two, unnested, and a failed invite trigger therefore died at
the mark instead of skipping the answer. A fresh-agent pre-push review found it
by running the composed `run_story`, which no test did.

**What would confirm it.** A second instance where a nesting-to-sequence
refactor passed its per-piece tests and changed a skip, a cleanup or an
ordering guarantee at the caller. ADR-0135's "compose, never chain" rule for BT
helpers (`notes/bt-pitfalls.md`) is the same shape seen from the design side,
which is weak corroboration: it says what to build, not what to test.

**How to apply.** When a diff turns nesting into sequence, name the guarantee
the nesting gave (what did it skip, and on whose failure?) and write one test
that exercises that guarantee through the new caller. The per-piece tests stay;
they are not the ones at risk.
