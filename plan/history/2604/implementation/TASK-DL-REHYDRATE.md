---
title: "DataLayer list_objects() method and model_validate cleanup"
type: implementation
timestamp: '2026-04-30T15:46:25+00:00'

source: TASK-DL-REHYDRATE
---

## TASK-DL-REHYDRATE — DataLayer `list_objects()` + coercion cleanup

Added `list_objects(type_key)` to the `DataLayer` Protocol and `SqliteDataLayer`
adapter. The method uses the existing `_from_row()` rehydration pipeline (vocab
reconstruction → field rehydration → semantic-class coercion) to return fully
typed domain objects filtered by `type_key`.

Also removed a redundant `model_validate` fallback in `SvcAcceptCaseInviteUseCase`
— the `_coerce_to_semantic_class` step in `_from_row()` already returns the
correct `RmInviteToCaseActivity` type, making the try/except coercion dead code.

Named `list_objects` (not `list`) to avoid shadowing Python's built-in `list`
type in the class body, which causes a runtime `TypeError: 'function' object
is not subscriptable` on class definition (not just a mypy error).

`CasePersistence` (the narrow core port) intentionally does NOT expose
`list_objects` — no core use case requires bulk listing through that interface.
