# Completeness Doctrine

**Boil the lake, not the ocean.**

Complete what is in front of you — thoroughly, with tests, with edge cases
handled, with documentation current. Do not unilaterally expand into unrelated
work that has nothing to do with what you were asked. There will be other
lakes.

But "boil the lake, not the ocean" is not a license to leave puddles. Most of
the work an agent discovers while doing a task is *part of that task* or sits
right next to it with the context already loaded. That work should get **done**,
not filed-and-forgotten. This doctrine exists to make the difference between
"boil this lake" and "leave a puddle for a future session" a decision you make
on purpose, with evidence — not a reflex.

## What "Done" Means

A task is not done until:

- All changed behaviors have tests (unit and/or integration)
- All edge cases the implementation touches are handled, not deferred
- Type annotations and docstrings are current with the new behavior
- Linters pass clean (no `# type: ignore` or `# noqa` added without justification)
- Specs, notes, and AGENTS.md are consistent with the new behavior

A happy-path-only implementation is not done. A behavior with no test is not
done. A changed interface with a stale type annotation is not done.

## Filing Is Not Deferring

This is the load-bearing distinction in this doctrine. Read it slowly.

When you are working on issue A and you discover problem B, you face **two
separate decisions**, and they are routinely — and wrongly — collapsed into
one:

1. **FILE** — do you create a durable record that B exists? Filing captures the
   fact that something needed doing. It is about *tracking*, not *timing*.
2. **DEFER** — do you leave B for a *later* session, or fix it *now* while the
   context that surfaced it is still loaded? Deferring is about *timing*, not
   *tracking*.

The failure mode this doctrine is built to kill: an agent finds B, files an
issue for B, and treats the act of filing as if it were a decision to *not do
the work* — "I recorded it, so I'm done with it." That is "file and pretend you
didn't just create more work." Every issue processed this way spawns one to
five new deferred issues, and the backlog grows without bound. In the
2026-09-02 audit, nearly every finding parked this way was eventually re-found
and re-filed by a later session: the deferral bought nothing but the
rediscovery cost, and several findings fell through entirely.

**The default is: FILE if the record is warranted (see below), and FIX NOW.**
Filing and fixing are not in tension — a fixed finding still gets its record,
and the PR closes it. Deferral is the exception you must *earn*, not the
default you fall into because you happened to open an issue.

Do not "optimize" this default away, because the reason for it is strong:
**you, working this finding right now, have the most context anyone will ever
have on it.** A follow-up issue is a lossy snapshot of that context, not a
reliable handoff. Starting a fresh issue-to-merge cycle later — re-orienting,
re-loading specs, re-deriving the fix — is far more expensive than folding the
fix into the PR whose context you already hold. Cheap-now, expensive-later. So
when the finding is trivial, small, overlaps the current work, or you already
know the fix, *just do it*. Do not file-and-walk.

## When To FILE (Keep A Record)

Not every fix needs a filed issue, or the issue tracker fills with closed
micro-issues (`Closes #847: fixed typo in docstring`) and stops meaning
anything. Filing is gated on one question:

> **Would the PR be *surprising* if a reviewer compared it to the issue(s) it
> closes?**

A PR must clearly say what it does and *why*, mapped to the issues it closes.
That clarity — not small size — is the hard constraint (see "Clarity Over
Size, Always"). Two tests detect surprise:

1. **The "also" test (breadth surprise).** If explaining why you fixed both the
   original thing and the discovered thing requires the word "also" — "I fixed
   the parser bug, and *also* rewrote the retry logic" — then the discovered
   thing is a genuine excursion. **File it.** It needs its own record so the PR
   can close it and the "why" has somewhere to live. If you can explain both in
   one sentence *without* "also," it is simply part of doing the task
   correctly: **do not file it** — the diff is its record.

2. **The inversion test (foundation surprise).** If the work *inverts an
   assumption* the issue rested on — you did the exact thing asked, but on a
   premise that contradicts what the issue was built on — that is not a scope
   excursion, it is an *epistemic* event: something the project believed is now
   wrong. The reference frame for "was this assumption already known" is the
   **issue text plus the specs and ADRs the issue rests on** (loaded via
   `orient-agent` and `deepen-context`), not the issue text alone — because the
   most dangerous inversions overturn a spec- or ADR-level premise the issue
   never restated. Inversions are handled by a dedicated gate, below; they are
   never filed silently, and never *acted on* silently.

The failure modes are asymmetric, which is why the bar leans toward "when in
doubt, don't file":

- **Under-filing** (you rode an excursion in the diff without a record) is
  **self-correcting** — it shows up as scope-creep the moment anyone reads the
  diff against the closed issue. The diff *is* the audit.
- **Over-filing** (a record for every trivial change) is **not**
  self-correcting — the closed-micro-issue noise accumulates in the tracker
  forever and nothing ever cleans it.

## The Fix-Now Floor and How Far It Reaches

Fix-now is the floor, not a branch you sometimes land on. Two rules bound how
far it reaches, so a session does not eat its own tail.

### Depth: first-order vs. second-order

- **First-order** findings — discovered by the *original* work on A — are
  **"don't ask, just do."** You never defer first-order work. Fixing it *is*
  finishing A.
- **Second-order** findings — discovered *while fixing* a first-order
  excursion (B revealed C) — are the *only* findings eligible for a
  deferral-ask. Without this cap, every fix is a new surface revealing more
  fixes, "the context is loaded" justifies descending forever, and the PR never
  terminates. First-order-only bounds the chain at one hop.

### Breadth: the effort floor is the evidence contract

You may not raise the "should I stop / can I defer this?" question until you
have **earned** it by producing real output. The floor is defined on **output
you produced** — the diff you have written, the count of things you have
already fixed — never on **resources consumed** (tokens, turns, wall-clock).
A floor defined on consumption is satisfiable by *flailing*: an agent can burn
tokens thrashing and then claim it "worked hard enough" to bail. A floor
defined on output can only be cleared by *actually changing code*.

Critically, **the floor and the deferral-evidence requirement are the same
mechanism.** You cannot legally ask to defer until you can show a *measured
remainder* — "I converted 3 of the 47 call sites; the other 44 each need their
own signature change" — and you cannot produce a measured remainder without
having already done the output-work that clears the floor. There is **no
separate threshold number to define**: the evidence contract *is* the floor.
(Wall-clock is unreliable anyway — an agent has no proprioceptive sense that an
hour has passed and will blow past any time budget without noticing. Do not
gate anything on it.)

## The Two Gates

Everything else — first-order fixes, "also" excursions you file autonomously —
the agent does without pausing. Exactly two situations require a human, each
with a defined rule for what happens on silence (because these skills routinely
run unattended).

### Gate 1 — The deferral-ask

You want to *not* do work you could do. To defer, you must:

1. Describe the deferral candidate to the human in **plain domain language, no
   jargon** — if you cannot describe it simply, you do not understand it well
   enough to know it should be deferred.
2. Present **evidence, not opinion** — a *measured remainder*, not a forecast
   and not an attempt count. "I tried three times" is effort-theater and is
   gameable by flailing shallowly three times. "I did X, here is concretely
   what remains, here is the ratio" is not gameable, because you have to
   enumerate the remainder. The standard is: **try first and show it is too big
   to finish now; otherwise just finish it.**
3. Get **explicit approval.** Then, and only then, defer.

Note what "needs separate design effort" is *not*: it is not a category that
authorizes deferral. If a few questions to the human would resolve the design,
that is not deferral — that is *asking the questions and then fixing it*. Only
a genuine, evidenced multi-session design problem earns a deferral-ask.

**On silence (no human response): FIX IT NOW.** No response means no approval,
so the fix-now default stands. Silence is *never* consent to defer. (This
overturns the older "silence → record as deferred and continue" behavior, which
was the defer-by-default reflex in disguise.)

### Gate 2 — The inversion-ask

You discovered that the work *inverts a premise* (per the inversion test
above). Because a premise is usually *shared* — other issues, specs, and ADRs
likely rested on it too — inverting it has blast radius the current PR cannot
contain, and acting on it unreviewed is exactly the kind of silent
foundation-change that bites later.

**Explain the overturned premise to the human in plain language, and ask if and
what to file.** You do not autonomously file an inversion (unlike an "also"
excursion) and you do not autonomously act on the new premise. The human decides
whether it is real and what the record should say.

**On silence (no human response): HALT the PR and block on a human.** Mark it
draft/blocked and stop. An inversion is a circuit breaker. This is safe *and*
self-correcting: a mistaken halt lands in front of a human immediately and
visibly ("that's not an inversion, proceed"), whereas a silent
act-on-new-premise would ship an unreviewed foundation-change that surfaces only
when it breaks something.

## Clarity Over Size, Always

**It is more important that a PR is CLEAR about what it does and why — with
respect to the issues it closes — than that it is small.**

Do not split work, decline a fix, or leave a rabbit uncaught in the name of
keeping a PR small. If chasing rabbits lands more work in one PR, so be it —
package it as **one PR**. This doctrine deliberately contains no "when to split
a PR" guide, because size is not a constraint.

What keeps a large, rabbit-chasing PR honest is not smallness — it is the
machinery above, which *is* the clarity engine:

- Non-"also" work needs no record because it is self-evidently part of the
  task.
- Every "also" excursion gets a filed issue, so every excursion has a number to
  close and a place for its "why."
- Every inversion gets explained before it can distort the PR.
- Every deferral is stated with its measured remainder.

Concretely, in the PR body: **every filed excursion the PR fixed appears as its
own `- Closes #N` bullet**, and each non-obvious excursion gets a one-line "why"
in the Changes section (see `pr-body-guide.md`). A reviewer reading the closing
list and the Changes section should never be surprised.

## Finding Severity (build, pr-triage, bugfix)

Both FAIL and IMPROVE require action before the PR merges:

| Category | Meaning | Action |
|---|---|---|
| **FAIL** | Broken: won't work correctly, spec violated, changed behavior untested | Fix before the PR opens or merges |
| **IMPROVE** | Works but incomplete: missing adjacent test, stale doc, extractable helper, obvious gap in scope | Fix in the same session; file a record only if it passes the "also" test |

One exceptional category for work genuinely left for later:

| Category | Gate |
|---|---|
| **DEFER** | The full deferral-ask (Gate 1): file the record, present a *measured remainder* in plain language, and get **explicit** human approval. On silence, fix it now. No unilateral deferral, no attempt-count justification, no "silence counts as yes." |

**WARN** (flagged but no required action) does not exist in this project.
If something is worth noting, it is worth fixing or DEFER-gating. Posting a
finding only as an `[ADVISORY]` PR comment, or describing it in a
`plan/incoming/learnings/` file, does **not** count as tracking it — neither can
be assigned, scheduled, or closed, and citing the PR that surfaced it is not a
tracking reference either. If it warrants a record, it gets a real issue.

## The Regression Test Rule (bugfix)

A bug fix without a regression test is not a bug fix. The only exception:
when test infrastructure cost is genuinely disproportionate (requires
long-running infrastructure, complex setup far exceeding fix scope). In that
case, create a follow-up GitHub issue explaining the specific reason. The fix
may ship — the debt is tracked, not silently discarded.

## Root Cause vs. Symptom (bugfix)

Fix the root cause, not the symptom. "The root cause is out of scope" is a
deferral, so it must clear Gate 1: prove it with a measured remainder and get
approval, not merely assert it. Even when a genuine root-cause fix is deferred,
file the issue and document the underlying cause. Never ship a symptom-only fix
without a tracked, evidenced record of the root cause.

## The Cost of Deferral

Every deferral is a bet that future context will be as good as current context.
That bet is usually wrong. The agent working an issue now has the most context
it will ever have. A follow-up issue is a lossy description of that context,
not a reliable handoff.

Defer when you genuinely must — and can prove it. Never defer when you could
just finish.
