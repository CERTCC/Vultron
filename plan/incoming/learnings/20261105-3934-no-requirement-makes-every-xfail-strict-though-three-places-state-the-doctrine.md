---
title: "No requirement makes every xfail strict, though three places state the doctrine and a new ratchet now enforces it"
type: learning
timestamp: "2026-11-05T21:30:00Z"
source: ISSUE-3934
signal: spec-gap
---

Issue #3934 item 2 asked for `strict=True` on the one non-strict `xfail` in the
tree, and item 4 asked for the same in `test/ci/README-case-log-ratchet.md`'s
template. Both cite a doctrine the project clearly holds — a goal-state `xfail`
must be strict, so the day the work lands is announced rather than swallowed as
an XPASS nobody reads.

The doctrine is stated in at least three places in prose:
`test_validate_assignment_ratchet.py`'s module docstring,
`test_protocol_asks_specs.py`'s, and the README template item 4 fixed. The
closest **requirement** is ARCH-21-008, which is a `SHOULD`, and is scoped
narrowly: "Each such backlog SHOULD have a companion `xfail(strict=True)` goal
test", where "such backlog" means an ARCH-21-005 exact-set baseline.

So the rule the repo actually lives by is broader than any requirement states.
Two consequences showed up while building this:

- The README template item 4 corrected is **not** an ARCH-21-005 backlog — it
  is a per-scenario case-ledger invariant — so ARCH-21-008 does not reach it,
  yet the issue was plainly right that `strict=False` there is wrong.
- `test_every_xfail_is_strict`, added in this PR, enforces the rule over every
  `xfail` under `test/`. An AST sweep found the tree already complied but for
  item 2's one marker, so the gate is free. Its docstring says in as many words
  that it generalises a `SHOULD` scoped to something narrower, which is an
  honest admission that it polices more than the corpus requires.

**What is being asked of a future reader.** A gate with no governing
requirement is the drift risk this epic (#2619) is about from the other
direction: nothing stops a later session deleting `test_every_xfail_is_strict`
as unfounded, and nothing obliges a reviewer to keep it. Either the corpus
should carry the broader rule — a `MUST` under TB (testability) or a widened
ARCH-21-008 — or the ratchet should be narrowed to the backlogs ARCH-21-008
actually covers. That choice is a spec-authoring judgment, not one a bugfix
session should make unilaterally, and it was raised to the orchestrator as an
open question rather than decided.

Note the generalisation is not obviously safe in perpetuity: a genuinely
platform-conditional `xfail`, or one with `raises=`, could want laxity. The
ratchet's `_NON_STRICT_XFAIL_EXEMPT` is the hatch, and it is empty today —
which is evidence for the broader rule, not proof of it.
