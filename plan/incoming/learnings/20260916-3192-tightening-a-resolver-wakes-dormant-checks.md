---
title: "Making a permissive resolver answer unconditionally activates every downstream check that consumed its None"
type: learning
timestamp: "2026-09-16T20:05:00Z"
source: ISSUE-3192
signal: theme-candidate
---

ADR-0088 replaced a URL-shape gate inside `_find_case_actor_id` with an
unconditional role lookup. Read as a change to *that function*, it is small and
local: same signature, same return type, strictly more answers. The issue
(#3192) scoped it that way, and so did the ADR.

The cost was not in the function. It was in the two call sites that had been
consuming its `None` as an *implicit permission*:

- `_validate_canonical_entry` guards CLP-07-003 with
  `if case_actor_id and snapshot_actor == case_actor_id: raise`. The leading
  `and` short-circuits on `None`, so for every case whose manager was an
  ordinary participant the check never ran. Making the resolver answer turned it
  on for the first time — and it immediately refused legitimate entries, because
  the predicate assumed the authority and the participants were disjoint sets.
- `AnnounceVulnerabilityCaseReceivedUseCase` gates replica seeding with
  `if case_actor_id is not None and case_actor_id != sender: return`. Same
  short-circuit, opposite failure: the guard had been *silently permissive* in
  exactly the window it existed to police.

Neither site was in the ADR's scan, because the ADR enumerated code that
*determines* authority and these two *consume* it. Neither announced itself as a
bug either: the first surfaced as two failing tests that looked like stale
fixtures, and the second surfaced as a test that **passed** — by accepting an
imposter.

**How to apply.** When a change makes a resolver, lookup, or predicate return a
value where it used to return `None`/`False`/empty, the blast radius is not the
resolver's callers — it is the subset of callers that *branch on the empty
answer*. Grep for the resolver's name and read every `if x` / `if x is not None`
/ `x and …` / `x or default` guard around it, and for each one ask which branch
was being taken before. Two questions settle it:

- Was the empty answer granting permission? Then the change tightens behaviour,
  and legitimate flows may start being refused.
- Was the empty answer withholding a check? Then the change activates a predicate
  that has never run, and it may never have been correct.

A check that has been dormant has also never been tested. Its unit tests can be
green and vacuous — asserting the short-circuit, not the logic — so passing tests
are not evidence the predicate is right.

Corroboration needed: one instance so far. The related-but-distinct claim already
in the queue is [[20260914-3217-measure-what-a-permissive-fallback-absorbs]],
which covers *removing* a permissive path and measuring what it was absorbing.
This one is its downstream mirror: not "what does the tolerance absorb" but "who
was relying on the tolerance's silence". A second witness would be any session
that tightens a resolver and finds a previously-unreachable guard either refusing
valid input or revealed to have been inert.

Related: [[20260914-3217-measure-what-a-permissive-fallback-absorbs]]. Its watched
neighbouring claim was corroborated by this session and filed as #3295.
