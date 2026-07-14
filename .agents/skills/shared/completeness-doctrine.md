# Completeness Doctrine

**Boil the lake, not the ocean.**

Complete what is in front of you — thoroughly, with tests, with edge cases
handled, with documentation current. Do not unilaterally expand into adjacent
work that was not scoped here. There will be other lakes.

## What "Done" Means

A task is not done until:

- All changed behaviors have tests (unit and/or integration)
- All edge cases the implementation touches are handled, not deferred
- Type annotations and docstrings are current with the new behavior
- Linters pass clean (no `# type: ignore` or `# noqa` added without justification)
- Specs, notes, and AGENTS.md are consistent with the new behavior

A happy-path-only implementation is not done. A behavior with no test is not
done. A changed interface with a stale type annotation is not done.

## Depth vs. Scope Expansion

**Depth** (within the current task's scope) is **never optional**. Do not
offer to "come back to" edge cases, missing tests, or documentation gaps that
clearly belong to the current task. Do not leave dangling threads when tying
them off is within reach.

**Scope expansion** (adjacent work that crosses into a different issue,
domain, or design space) requires a judgment call:

| Signal | Action |
|---|---|
| Would require creating a new GitHub issue | Ask the user if present; make best-judgment call if unattended — record rationale as a learning file |
| Requires a design decision about *how* it should work | Ask the user if present; make best-judgment call if unattended — record rationale as a learning file |
| Hard to reverse (API change, schema change, spec change) | Ask the user if present; make best-judgment call if unattended — record rationale as a learning file |
| Trivially additive (clearly-missing test, obvious type fix) | Just do it — no permission needed |

When unattended: choose whatever seems most correct, document the reasoning
explicitly in a learning file, and let the user review and override.

## Finding Severity (build, pr-review, bugfix)

Both FAIL and IMPROVE require action before the PR merges:

| Category | Meaning | Action |
|---|---|---|
| **FAIL** | Broken: won't work correctly, spec violated, changed behavior untested | Fix before the PR opens or merges |
| **IMPROVE** | Works but incomplete: missing adjacent test, stale doc, extractable helper, obvious gap in scope | Fix in the same session; document in a follow-up commit and PR comment |

One exceptional category for genuinely out-of-scope work:

| Category | Gate |
|---|---|
| **DEFER** | 1. Create a follow-up GitHub issue immediately with specific justification. 2. Get explicit user acknowledgment. No unilateral deferral. |

**WARN** (flagged but no required action) does not exist in this project.
If something is worth noting, it is worth fixing or DEFER-gating.

## The Regression Test Rule (bugfix)

A bug fix without a regression test is not a bug fix. The only exception:
when test infrastructure cost is genuinely disproportionate (requires
long-running infrastructure, complex setup far exceeding fix scope). In that
case, create a follow-up GitHub issue explaining the specific reason. The fix
may ship — the debt is tracked, not silently discarded.

## Root Cause vs. Symptom (bugfix)

Fix the root cause, not the symptom, unless the root cause is provably out of
scope. Even then: create an issue. Never ship a symptom-only fix without
documenting the underlying cause.

## The Cost of Deferral

Every deferral is a bet that future context will be as good as current context.
That bet is usually wrong. The agent working an issue now has the most context
it will ever have. A follow-up issue is a lossy description of that context,
not a reliable handoff.

Defer when you genuinely must. Never defer when you could just finish.
