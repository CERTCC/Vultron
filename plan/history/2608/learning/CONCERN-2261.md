---
source: CONCERN-2261
timestamp: '2026-08-13T16:44:22.446427+00:00'
title: Post-construction mutation safety — three doors, one lock
type: learning
---

CONCERN-2261 asked whether `VultronBase` should set `validate_assignment`.
Planned as three ratcheted steps in PR <https://github.com/CERTCC/Vultron/pull/2292>,
codified in ADR-0064, and tracked in CI by
`test/architecture/test_validate_assignment_ratchet.py`.

## What was learned

**The one-line fix is a measured dead end, not a judgement call.** Setting
`validate_assignment=True` on `VultronBase` produces 747 FAILED + 423 ERROR;
on `CoreObject`, 398 + 268 (baseline: 2 pre-existing, #2274). **Every single
failure is a `RecursionError`** — 879 and 403 of them respectively. Not one
type-strictness failure is visible in either variant.

The mechanism: `validate_assignment` re-runs every `mode="after"` model
validator on each attribute assignment, so a validator that writes to `self`
re-enters itself. 23 core validators do this (plus 12 in the wire branch).
Guarded ones (`if self.name is None: ...`) terminate at depth 2; unguarded ones
never terminate. **The recursion masks the real blast radius**, which is why
step 2 cannot be sized until step 1 lands — the prerequisite is empirical, not
stylistic.

**There are three doors, and one mechanism cannot close them all.**

```python
case = VulnerabilityCase(case_participants=[wire_obj])  # ValidationError
case.case_participants = [wire_obj]                     # accepted
case.case_participants.append(wire_obj)                 # accepted
```

`validate_assignment` closes the middle door only. `list.append` is not an
attribute assignment, so Pydantic never observes it — that door needs
prohibition + canonical mutators + a static scan, which is exactly what
PRM-03-001 already did for `case_roles` (driving direct mutation in `vultron/`
to zero sites).

**Cost was never the obstacle.** Scalar assignment measured 475 ns → 1464 ns
(3.1×, ~1 µs absolute). The unquantified risk is O(N) collection-field
re-validation, now an explicit AC in #2294 rather than an assumption.

**Placement mattered more than expected.** `CoreObject`-only leaves 16 core
models uncovered, *including all five dimension classes* — precisely the types
implicated in #2232. A core-only mixin on 10 roots covers all 103 core models.
`VultronBase` is excluded **permanently** per ARCH-12-002, not deferred.

## The transferable lesson: non-strict xfail is a silent ratchet failure

The user's concern was "losing the plot over multiple issues." This repo
already had the evidence: the `strict=False` xfails for #1991 and #1992 had sat
green-and-ignored since they were filed. **A non-strict xfail keeps passing
after the work is done, so it never tells anyone to remove it, and it gives no
partial-progress signal.**

The shape that fixes this, adopted here and retrofitted onto #1991/#1992 in the
same PR:

1. An **exact-set backlog** asserted with `==`, so it fails when the set
   **grows** *and* when an entry is fixed but left listed. One-directional
   assertions (`<=`) let the enumeration go stale silently.
2. A companion **`xfail(strict=True)`** goal test. When the last entry goes, the
   goal test XPASSes, which *fails the build* and forces the marker's deletion.
3. Dedup against **everything seen**, and verify the ratchet **in both
   directions** before merge — inject a violation (must fail), then neutralise
   the backlog (must `[XPASS(strict)]` → FAILED).

The ratchet earned its keep within the same PR: the rebase onto `main` picked up
the BTND-07 decomposition (`c19b9997`), which split two of the three backlog
modules. The exact-set assertion failed on the renames and named both new paths
precisely — a one-directional assertion would have passed in silence.

## Process notes

- **Plain language before options.** The first grill-me question was rejected
  with "what is the problem we are trying to solve. assume i have not read the
  issue. use simple language." Lead with the problem statement, then offer
  choices.
- **Concurrent planning collides on IDs.** ADR-0063 and spec group ARCH-20 were
  both claimed by the #2260 plan (PR #2285) while this was in flight; both had
  to be renumbered to ADR-0064 / ARCH-21 during the rebase. Check the *tip of
  main*, not the branch base, before assigning an ADR number or a spec group.
- **Correct measurement errors out loud.** An intermediate claim of "2 wire-layer
  sites" was wrong — there are 12 (the 2 was the unguarded subset). It changed
  the scope of step 1, so it was flagged explicitly and re-asked.

## Outcome

- Docs PR: <https://github.com/CERTCC/Vultron/pull/2292>
- ADR-0064 (core-branch `validate_assignment`, three ratcheted steps)
- Specs: ARCH-21-001..005, CM-27-001..003, PRM-03-003
- Notes: `notes/domain-validation.md` § "Post-Construction Mutation: Three
  Doors, One Lock"; AGENTS.md pitfall covering both traps
- Impl issues under Epic #2229, `Schedule=Focus`:
  - #2293 — step 1: 23 core validators to `mode="before"` (`size:M`)
  - #2294 — step 2: core-only mixin on 10 roots (`size:L`, blocked by #2293)
  - #2295 — step 3: append door via canonical mutators (`size:M`, parallel)
- Repaired the #1991 / #1992 `strict=False` xfails
- Cross-referenced onto #2268 (the 13 remaining shadowing types)

**Explicitly out of scope:** the wire branch stays lenient (ARCH-12-002; its 12
self-assigning validators are exempt by design), #2268's 13 shadowing types,
`frozen=True` / immutable core models, and scanning `test/` for direct mutation.

**Honest framing:** #2261 is *preventive hardening* for the #2233 class of
defect, not the fix for it. Seven Demo Integration scenarios were red on `main`
at planning time (`422 ValidationError: TransitionParticipantRMtoAccepted`) —
that is #2233's own work.
