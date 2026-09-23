---
title: "An AC that declares an exclusion intentional gets elaborated, not tested — the agent supplies missing detail in the wrong direction"
type: learning
timestamp: "2026-09-22T17:30:00Z"
source: ISSUE-3510
signal: theme-candidate
---

AC-3 of ISSUE-3510 said to extend `managed_keys` with `activity` and the
`context_data` keys, and added a parenthetical:

> `actor_id` is intentionally excluded (outer execution holds its own actor id
> as a Python local).

That reason is true of `execute_with_setup` and false of every node — all four
bases in `behaviors/helpers.py` re-read `/actor_id` in `initialise()`, which
py_trees runs on every tick in which the node was not `RUNNING`. So the exclusion
leaked a nested execution's actor to every later sibling of the calling node.

**What is worth recording is not that the AC was wrong — it is what I did with
it.** I did not merely inherit the bad premise. I *strengthened* it. Asked to
implement an exclusion described as intentional, I went looking for the mechanism
that would make it safe, found a plausible one, and wrote it into three places
with more confidence and more specificity than the AC had:

> every node base in `helpers.py` copies `/actor_id` into `self.actor_id` during
> `setup()`, which `execute_tree` runs for the whole tree before the first tick

The AC never said `setup()`. I supplied that, because a lifecycle hook that runs
once per execution is exactly what the AC's claim needs in order to be true. I
had even grepped the right file and seen the line numbers — and read them as
being inside `setup()` because that is the reading I was looking for. Then I
wrote a **test that pinned the leak in place** (`test_actor_id_is_left_to_each_execution`),
with a docstring explaining why the exclusion was correct. A reviewer's job got
harder, not easier, because the defect now had a passing test and a mechanism.

The second half of the rationale I invented was not even coherent:

> Adding it here would be the riskier change, not the safer one: it would restore
> the outer actor over an inner execution whose own teardown has not run yet.

The restore *is* the inner call's own teardown. That sentence cannot be true of
any code. It survived because I was generating support for a conclusion rather
than checking one — and unfalsifiable filler reads as caution, which is the
register that gets least scrutiny.

**Why this is not the same as ordinary premise-inheritance.** An agent that
simply believes a wrong AC produces a wrong implementation, and the wrongness
stays the size the AC made it. An agent asked to *preserve* something described
as deliberate produces a wrong implementation **plus** a mechanism, a code
comment, a spec rationale and a regression test — each of which independently
suppresses the next reader's scrutiny. The defect gets institutionalised on the
way through. The cost is not one bug; it is that the bug now has infrastructure.

**How to apply.** When an AC, docstring, or comment tells you something is
*intentionally* excluded, skipped, or not needed:

- Treat the stated reason as a **claim to test**, not context to honour. Write
  the probe before the code. Mine was fifteen lines and settled it in one run:
  a `Sequence(memory=False)` whose first child runs a nested execution as actor
  B and whose second child records what it resolves.
- If you find yourself *supplying* a mechanism the source did not state — a hook
  name, an ordering, a "runs once" — stop. That is the tell. You are not
  documenting the reason; you are constructing one, and you picked it because it
  makes the instruction coherent.
- Never write a test whose purpose is to assert that an exclusion is correct,
  unless you have independently reproduced the behaviour it depends on. A test
  that pins current behaviour and calls it intended converts a live defect into a
  documented invariant.
- Grepping for a symbol and reading the *enclosing function* are different acts.
  `grep -n actor_id` gave me line 397; only `sed -n '374,400p'` showed that 397
  is inside `initialise()`. When a claim turns on *when* code runs, the line
  number is not the evidence — the enclosing `def` is.

Corroboration needed: one instance. The nearest queued claim is
[[20260918-2505-a-retired-exemption-survives-in-the-copies-that-do-not-cite-the-adr]],
which covers the *codebase* side of this (a confident sentence with a plausible
rationale attached is a prime suspect); that side gained its second witness here
and is filed as #3535. This entry is the *agent-behaviour* side, which that entry
does not cover: not "the wrong rationale survives" but "the next worker enlarges
it." A second witness would be any session that is told a behaviour is deliberate
and ends up adding a mechanism, a spec clause, or a test that the instruction did
not contain.

Related: [[20260916-3192-tightening-a-resolver-wakes-dormant-checks]] — its
subject is also a guard nobody had tested, reached from the opposite direction
(there, making a resolver answer *activated* a dormant check; here, a dormant
premise was never checked at all).
