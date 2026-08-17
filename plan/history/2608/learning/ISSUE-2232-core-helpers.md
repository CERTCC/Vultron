---
title: Concern — notes/domain-validation.md directs helpers to a module that cannot import core.states
type: learning
timestamp: 2026-08-12T00:00:00Z
source: ISSUE-2232-core-helpers
signal: concern
---

`notes/domain-validation.md` says canonical layer-neutral helpers belong in
`vultron/core/models/_helpers.py`.  That guidance is **unfollowable for any
helper that needs a state enum**, and the failure mode is a confusing
`ImportError` rather than a clear rejection.

`vultron/core/models/base.py` imports `_helpers` (for `_new_urn`/`_now_utc`), so
`_helpers` is loaded *during* `models.base` initialisation.  Importing
`vultron.core.states.rm` from `_helpers` first executes
`vultron/core/states/__init__.py`, which pulls `states/cs.py` →
`states/common.py` → back into `models.base` — still partially initialised:

```text
ImportError: cannot import name 'NonEmptyString' from partially initialized
module 'vultron.core.models.base' (most likely due to a circular import)
```

The trap is that `states/rm.py`'s *own* imports are clean (logging, enum,
transitions, `states.common`).  Inspecting the target module tells you nothing;
the cycle runs through the package `__init__`.  So `_helpers.py` is usable only
for helpers that depend on nothing outside stdlib and `TYPE_CHECKING`.

`participant_status_rm_state` was instead placed in
`vultron/core/models/participant_status.py`, next to the model it reads.  That
is arguably the better home regardless — the canonical reader for a type lives
with the type — but it was reached by hitting the wall, not by design.

**Suggested fix:** amend `notes/domain-validation.md` to state the constraint
explicitly, and to direct type-specific canonical readers to the type's own
module. A shared BT-node wrapper (`read_rm_states`) went into
`vultron/core/behaviors/helpers.py`, which has no such restriction.

Related: #2269 (that placement was also forced by the `append.py` line ceiling).

**Promoted**: 2026-08-17 — captured in notes/domain-validation.md (canonical helper locations / circular import section).
Docs PR: <https://github.com/CERTCC/Vultron/pull/2330>.
