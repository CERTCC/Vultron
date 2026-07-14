---
title: py_trees blackboard stores lists by reference — pop(0) write-back is redundant
type: learning
timestamp: 2026-07-13T00:00:00Z
source: ISSUE-1374
---

When a py_trees blackboard holds a list, it stores the object by reference (not
a copy). Calling `list.pop(0)` or `list.append(x)` on the retrieved object
mutates the stored value in place — any subsequent reader sees the updated list
without a write-back.

The pattern:

```python
lst = self._bb.my_key
lst.pop(0)
self._bb.my_key = lst   # <-- redundant: same object, already updated
```

The write-back on line 3 is a no-op: it assigns the same object reference back
to the same slot.

**Exception**: the write-back IS needed when the list was created fresh in an
`except KeyError` branch (new `[]` not yet stored on the blackboard). In that
case the write-back is the only thing that persists the new list.

Verified by live py_trees test in session ISSUE-1374 build.
