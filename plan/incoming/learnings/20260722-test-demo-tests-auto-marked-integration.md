---
title: Every test under test/demo/ is auto-marked integration, even pure-unit ones
type: learning
timestamp: 2026-07-22T00:00:00Z
source: ISSUE-1307
---

## Observation

`test/demo/conftest.py`'s `pytest_collection_modifyitems` hook unconditionally
adds `pytest.mark.integration` to **every** test collected from `test/demo/`,
regardless of whether the test actually spins up a FastAPI `TestClient`. Since
the default `pyproject.toml` `addopts` is `-m 'not integration'`, a brand-new
pure-unit test file placed in `test/demo/` (e.g. `test_report.py`, which only
exercises in-process parsing/rendering with `tmp_path`) is **silently
deselected** by `uv run pytest test/demo/test_report.py` — the run reports
"N deselected" and 0 passed, which looks like a collection error but isn't.

## How to apply

- To run (or confirm) unit tests that live under `test/demo/`, pass `-m ""`:
  `uv run pytest test/demo/test_report.py -m ""`.
- This is also why AGENTS.md requires the full suite (`uv run pytest -m ""`)
  whenever `vultron/demo/` or `test/demo/` is touched — the fast default run
  skips the entire directory.
- A fast in-process demo utility test does not need HTTP fixtures; put it in
  `test/demo/` for colocation but remember it will be labelled integration by
  the directory-level hook, not by its actual dependencies.
