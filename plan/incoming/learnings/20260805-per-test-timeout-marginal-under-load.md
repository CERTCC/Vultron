---
title: AST-walking architecture ratchets sit near the 5s per-test timeout under full-suite load
type: learning
timestamp: 2026-08-05
source: ISSUE-1988
signal: concern
---

The repo sets `timeout = 5` (per test) in `pyproject.toml`. Several
architecture ratchets parse every file under `vultron/` with `ast` and are
already close to that ceiling in isolation:

- `test_activity_factory_imports.py::test_vocab_activities_boundary` — ~3.4s
- `test_no_asgi_transport_in_app_code.py` — ~1.9s
- `test_core_no_adapter_imports.py` — ~1.2s

Under full-suite load (`uv run pytest -m ""`) one of these times out
non-deterministically — a *different* test on each run
(`test_vocab_activities_boundary`, `test_docs_render`, …), which is the
signature of a load-dependent margin rather than a specific slow test.
Reproduced on a clean `origin/main` worktree with all ISSUE-1988 changes
stashed, so it is pre-existing and not a regression. It is invisible when
running a single directory, which is how these tests are usually exercised.

Mitigation applied to the new ratchet
(`test/architecture/test_infrastructure_logs_not_at_info.py`): a cheap
substring prefilter skips `ast.parse()` for files that do not mention any
target fragment, cutting it from ~2.05s to ~0.67s.

**Suggested follow-up:** apply the same prefilter (or a shared cached
"parse every vultron module once" session fixture) to the existing ratchets, or
mark them with a longer per-test timeout. As more ratchets accumulate — this PR
added one — the aggregate risk of a spurious CI failure grows. Worth a Concern
issue; the fix is mechanical but touches several files and is out of scope for
a logging PR.
