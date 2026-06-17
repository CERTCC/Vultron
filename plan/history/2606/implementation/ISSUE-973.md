---
source: ISSUE-973
timestamp: '2026-06-16T20:35:53.381046+00:00'
title: Split trigger_activity_adapter.py into domain-focused subpackage
type: implementation
---

## Issue #973 — Split `trigger_activity_adapter.py` into focused submodules

Replaced the 712-line flat module
`vultron/adapters/driven/trigger_activity_adapter.py` with a
`trigger_activity_adapter/` subpackage using the mixin-composition
pattern established by the `datalayer_sqlite/` split (issue #974 epic).

**New subpackage structure:**

- `_base.py` — `_DUMP_KWARGS` constant + `_TriggerAdapterBase.__init__(dl)`
- `notes.py` — `_NotesMixin` (3 methods)
- `reports.py` — `_ReportsMixin` (3 methods)
- `cases.py` — `_CasesMixin` (5 methods)
- `actors.py` — `_ActorsMixin` (8 methods)
- `embargo.py` — `_EmbargoMixin` (5 methods)
- `__init__.py` — `TriggerActivityAdapter` composes all mixins; public import
  path unchanged

**Tests:** Added 48 adapter-level unit tests in
`test/adapters/driven/trigger_activity_adapter/`. Key fix: the
`TestAcceptCaseInvite` fixture must store the invitee actor in the DL
before the invite so `_rehydrate_fields` can expand the dehydrated
`object_` URI — matching the pattern in `test_actor_triggers.py`.

**Outcome:** 3474 tests pass, 0 regressions. All four linters pass.

PR: [#1018](https://github.com/CERTCC/Vultron/pull/1018)
