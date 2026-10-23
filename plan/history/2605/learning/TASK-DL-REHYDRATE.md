---
source: TASK-DL-REHYDRATE
timestamp: '2026-05-04T18:01:00.762939+00:00'
title: Do not name a method list in a Python class
type: learning
---

Defining `def list(self, ...)` on a class causes Python to shadow the built-in
`list` type in the class body scope. Any annotation `list[str]` that appears
AFTER the `def list(...)` definition is evaluated at class-body execution time
with `list` resolving to the method (a function), producing a TypeError at
runtime. `# type: ignore[valid-type]` only suppresses mypy — it does NOT
prevent the runtime error. Fix: rename the method to avoid collision (e.g.,
`list_objects`). This affects any method that shares a name with a Python
built-in type (`dict`, `set`, `tuple`, etc.).

**Promoted**: 2026-05-04 — captured in specs/code-style.yaml as CS-16-001.
