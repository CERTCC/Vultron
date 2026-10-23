---
source: ISSUE-469-BT
timestamp: '2026-05-08T17:29:12.676885+00:00'
title: py_trees blackboard.get() raises KeyError; duplicate class methods shadow BT
  logic
type: learning
---

## Learning: py_trees blackboard.get() and duplicate class body pitfalls

Two related BT pitfalls surfaced during #469 implementation:

### 1. `blackboard.get(key)` raises KeyError for unwritten READ keys

`Client.get(key)` raises `KeyError` (not `None`) when a key is registered for
`Access.READ` but has not yet been written to `Blackboard.storage`. This is
the opposite of `dict.get()`. Safe-access patterns: use a `try/except KeyError`
guard in `update()`, or ensure the writing node always precedes the reading
node in the BT sequence. Using `Blackboard.storage.get("/key")` is acceptable
only in tests.

### 2. Duplicate method definitions silently shadow correct BT node logic

When editing node files, if a class body is accidentally embedded inside a
sibling class (e.g., via a mis-scoped `old_str`/`new_str` in an edit tool),
Python resolves duplicate `__init__`/`setup`/`update()` definitions by keeping
the *last* one. The correct methods are silently replaced by the embedded
class's methods, making the node behave as a completely different node. The
symptom was `SendOfferCaseManagerRoleNode.update()` behaving as
`EmitCreateCaseActivity.update()` — returning `SUCCESS` whenever `case_id` was
present, regardless of `case_actor_id`.

**Detection**: `grep -n "^class " <file>` after every multi-class edit to
verify class boundaries have not shifted.

Both pitfalls are now documented in `notes/bt-integration.md` and indexed in
`AGENTS.md`.
