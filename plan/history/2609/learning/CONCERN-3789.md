---
source: CONCERN-3789
timestamp: '2026-09-28T16:40:42.304660+00:00'
title: Test-local CoreObject subclasses register in process-global CORE_TYPE_MAP
type: learning
---

Test functions that define a local CoreObject subclass with a concrete
type_annotation register it in CORE_TYPE_MAP and CORE_VOCABULARY for the
duration of the process. The name _TwoComputedFields (added in #3695) uses
an underscore-prefixed, unlikely-to-collide name, so the practical risk is
low. However, it is a known testing-pitfall and could cause order-dependent
failures if another test tries to look up or enumerate core vocabulary
entries expecting a fixed set.

The safe pattern is either a pytest fixture that cleans up
CORE_TYPE_MAP/CORE_VOCABULARY after the test, or a subclass that avoids
registration (e.g. by using a non-concrete type_ annotation).

Root cause analysis: CORE_VOCABULARY and CORE_TYPE_MAP are recoverable via
fixture snapshot/restore. The **subclasses**() graph is permanently mutated
by class definition and cannot be restored — but existing architecture
ratchets that walk it (e.g. test_every_core_object_forbids_extra_with_no_exemption_list)
pass anyway because test-local CoreObject subclasses inherit extra="forbid".
The actionable risk is therefore the dict pollution, not the subclass graph.
The wire-side analogue (sync.py filtering as_Object.**subclasses**() to
vultron.wire.as2.vocab) does not apply here: adding a module filter to
_all_core_object_subclasses() would create a blind spot in the invariant
check rather than fixing it.

Fix: extend the existing isolated_vocab fixture to also cover CORE_TYPE_MAP,
rename it isolated_core_registries, and move it to test/core/conftest.py so
it is shared by test_core_object.py and test_actor.py without duplication.

**Resolved**: 2026-09-28 — implementation tracked in #3801.
Docs PR: <https://github.com/CERTCC/Vultron/pull/3800>.
Notes: `notes/testing-pitfalls.md`.
