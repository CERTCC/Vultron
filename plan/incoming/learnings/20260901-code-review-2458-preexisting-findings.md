---
title: Pre-existing findings surfaced by code review for PR #2928 (ISSUE-2458)
type: learning
timestamp: 2026-09-01
source: ISSUE-2458
signal: concern
---

Code review agent for PR #2928 (ISSUE-2458) used stale local `main` as the diff
base instead of `origin/main`, surfacing 4 findings in files not touched by this
PR. These are pre-existing issues that should be tracked:

1. `vultron/wire/as2/vocab/objects/case_status.py:87` — `_coerce_vf_or_none`
   raises uncaught `KeyError` for unrecognised `vf_state` strings; Pydantic v2
   only catches `ValueError/TypeError/AssertionError` in validators, so `KeyError`
   propagates and crashes the inbox pipeline. `_coerce_vf` in `dimensions.py`
   already has the correct `try/except KeyError → ValueError` wrapping.

2. `vultron/wire/as2/vocab/objects/case_status.py:97` — Same class of bug in
   `_coerce_d_or_none`: uncaught `KeyError` for unrecognised `d_state` strings.

3. `vultron/core/behaviors/status/nodes/_adjudication.py:95` — When a participant
   currently has `vf=None` but a peer asserts a non-None VF state, neither branch
   fires and the peer's claimed VF value is silently accepted, even when the
   participant has no VENDOR role.

4. `vultron/core/behaviors/status/add_participant_status_tree.py:206` —
   `EmitCaseStatusUpdateNode` constructed with `case_id=''` when `tree_case_id`
   is `None`, producing an opaque FAILURE instead of a structural guard failure.
   Inconsistency: same `tree_case_id` passed as `None` to `ThreatTerminationBranchNode`
   at line 227.

All four are in files not modified by PR #2928. They require investigation and
dedicated bug issues before fixing.
