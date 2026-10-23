---
title: "An AC that declares an exclusion intentional gets elaborated, not tested — the agent supplies missing detail in the wrong direction"
type: learning
timestamp: "2026-09-22T17:30:00Z"
source: ISSUE-3510
signal: theme-candidate
---

**Trigger.** An AC, docstring, or comment says something is *intentionally*
excluded, skipped, or not needed, and you are asked to implement or preserve it.

**Claim.** An agent asked to preserve a behaviour described as deliberate does
not just inherit a wrong premise; it enlarges it. It goes looking for the
mechanism that would make the exclusion safe, finds a plausible one, and writes
it into code comments, spec rationale, and a regression test. Each of those
suppresses the next reader's scrutiny, so the defect gains infrastructure on the
way through. Plain premise-inheritance leaves a bug the size the AC made it;
this leaves a bug with a passing test pinning it in place.

**Evidence.** ISSUE-3510's AC-3 excluded `actor_id` from `managed_keys` because
"outer execution holds its own actor id as a Python local". True of
`execute_with_setup`, false of every node base in `behaviors/helpers.py`, which
re-read `/actor_id` in `initialise()` on every tick. The build attributed the
read to `setup()` (a hook the AC never named, chosen because it made the claim
true) and wrote `test_actor_id_is_left_to_each_execution` asserting the leak was
correct.

**How to apply.**

- Treat the stated reason as a claim to test. Write the probe before the code;
  here, fifteen lines (a `Sequence(memory=False)` whose first child runs a
  nested execution as actor B, whose second records what it resolves) settled it.
- If you find yourself *supplying* a mechanism the source did not state — a hook
  name, an ordering, a "runs once" — stop. You are constructing the reason, not
  documenting it.
- Never write a test asserting an exclusion is correct unless you have
  independently reproduced the behaviour it depends on.
- When a claim turns on *when* code runs, the evidence is the enclosing `def`,
  not the `grep -n` line number.
- Rationale that cannot be true of any code ("restore the outer actor over an
  inner execution whose own teardown has not run yet", when the restore *is*
  that teardown) reads as caution. Check it as hard as anything else.

**What would confirm it.** A session told a behaviour is deliberate that ends up
adding a mechanism, spec clause, or test the instruction did not contain. The
codebase-side theme (a confident rationale suppresses scrutiny) is already
tracked as #3535; this entry is the agent-behaviour side.

Related: [[20260916-3192-tightening-a-resolver-wakes-dormant-checks]].
