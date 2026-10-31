---
title: >-
  Moving a scenario step into a shared helper disarms every patch.object on the
  old module, and the test keeps passing with nothing intercepted
type: learning
timestamp: 2026-10-31T00:00:00+00:00
source: ISSUE-5534
signal: theme-candidate
---

A consolidation that moves a step out of a scenario module and into a shared
helper leaves `patch.object(scenario_module, "wait_for_...")` in place and
pointing at a name the module still imports but no longer calls. The patch
takes, the test runs, and nothing is intercepted: the helper resolves the name
in its own module. Nothing goes red — the test asserts about what the step did,
and the step did it, against a real poll on a `MagicMock` client.

Three witnesses, all in #5534's family:

- The RM gate, the trigger and the vendor's own VF check became
  `coordinated_story.vendor_notifies_fix_ready`, so `rcvcv`'s fix-lifecycle
  tests patched `rcvcv_demo.wait_for_participant_rm_state` and intercepted
  nothing. Here it *did* go red, because the unpatched wait then polled a mock.
- The three identical `open_cast` closures became
  `coordinated_story.coordinated_open_cast`, so a test patching
  `rcvcv_demo.open_coordinated_cast` raised `AttributeError` — the loud case,
  and the only one of the three that announced itself.
- The ISSUE-2239 artifact table patched each scenario's "first step" by module
  attribute; for the five composed scenarios the first thing that can die moved
  into the shared opening, so the table's rows had to name a dotted target in
  `coordinated_story` instead.

The claim worth a second witness outside this family: **the loud failure is the
lucky case.** `patch.object` raises only when the name is gone from the module
entirely. A module that still *imports* the name — because another of its own
steps uses it, or because ruff has not yet called the import unused — gives a
patch that succeeds and intercepts nothing, and whether the test then fails
depends on whether the real call happens to blow up on a stand-in. #5537, #5535
and #5536 each move more steps into shared helpers, and #5592 moves every one
of them into a subpackage, where the same trap has a second form: a patch on
the package's `__init__` never reaches the submodule that resolves the name.

What would settle it: whether a check can distinguish "patched and intercepting"
from "patched and inert" — for instance, asserting that a patched name is
actually called at least once per test that patches it, or that every
`patch.object` target in `test/demo/` names a module that both imports *and*
references the name in the function under test.
