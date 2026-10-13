---
source: NOTES-architecture-ratchet-corpus--xdist-compatibility
timestamp: '2026-10-12T19:36:37.468830+00:00'
title: 'Architecture ratchet corpus: xdist compatibility'
type: note
---

**Archived:** 2026-10-12
**Reason:** delivered — pytest-xdist is enabled (`uv run pytest -n auto`, `--dist loadgroup` in `pyproject.toml`); the compatibility audit is done.
**Superseded by:** TB-13-005/006 in `specs/testability.yaml`; `notes/testing-pitfalls.md` (process-global state)

---

## xdist Compatibility

`pytest-xdist` is a declared dependency (`pyproject.toml`) but not
currently enabled in CI or local runs. Enabling `-n auto` could reduce
full-suite wall-clock by 50–70% on multi-core runners.

Known xdist hazards in this codebase:

- `py_trees.blackboard.Blackboard.storage` is a process-global dict.
  Tests that do not reset it (some BT tests) would race under parallel
  execution.
- Module-level singletons used by some demo tests (e.g., actor
  configuration globals).

A compatibility audit (TB-13-005) is a prerequisite before enabling xdist.
