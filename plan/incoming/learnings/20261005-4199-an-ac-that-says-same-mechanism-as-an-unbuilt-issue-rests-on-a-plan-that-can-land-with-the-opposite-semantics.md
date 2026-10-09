---
title: "An AC that says 'same mechanism as <open issue>' rests on that issue's plan, which can land mid-build with the opposite semantics"
type: learning
timestamp: "2026-10-05T19:30:00Z"
source: ISSUE-4199
signal: theme-candidate
---

# 4199's AC-4 read: "CI check fails when a `verification_debt` marker names a

closed issue (same mechanism as the ARCH-18 ratchet-baseline owner check)." At
the time, the ARCH-18 owner check was #3927, which was still being planned. No
mechanism existed to be "the same as", so the AC really carried two claims: a
behaviour (fail) and a deference (match ARCH-18).

While #4199 was being built, #3927's plan landed on `main` as ARCH-18-004. It
says the owner-state check runs outside the merge path and MUST NOT fail the
build, because failing on a hand-closed issue turns every PR in flight red.
The two halves of AC-4 now contradicted each other, and only the freshen
before push surfaced it: the cherry-pick conflicted on
`notes/architecture-ratchet-corpus.md`, and reading the conflicting commit
showed the new rule. The maintainer resolved it in-session with a third
design: fail only the PR whose `Closes #N` closes an owner still in use, and
report hand closures hourly without failing the build.

Claim, from one instance: when an AC defers to "the same mechanism as" an
issue that is not yet built, the build should re-read that issue's current
plan and specs right before pushing, not only at claim time. Planning PRs
merge to `main` at the same pace as code, so the deferred-to design can
change while the build is in flight. A planner can avoid the problem by
stating the behaviour outright and dropping the deference, or by wiring the
deferred-to issue as a blocker.
