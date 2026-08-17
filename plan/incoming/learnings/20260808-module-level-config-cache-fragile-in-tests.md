---
title: "Module-level config cache makes reload_config() order-sensitive in test teardown"
type: learning
timestamp: "2026-08-08"
source: ISSUE-2086
signal: concern
---

`vultron/config/app.py` holds a module-level `_config_cache`. `get_config()`
lazily populates it; `reload_config()` clears it and re-reads the environment.
That makes the *cache* process-global while the *environment* it derives from is
per-test — and pytest's `monkeypatch` fixture undoes env changes **after** the
requesting fixture's teardown body runs.

So this order is a latent session-wide leak:

```python
# teardown
reload_config()      # re-caches the still-patched fake host
# ... monkeypatch's own undo runs here, too late
```

and this order is correct:

```python
monkeypatch.undo()
reload_config()
```

Four demo fixtures had the buggy order (`test_fvcv_handoff_demo.py`,
`test_pcr_late_joiner.py`, `test_case_proposal_round_trip.py`,
`test_pcr_engage_case.py`). One (`test_fv_demo.py`) had already hit this and
worked around it by using an explicit `MonkeyPatch()` instead of the fixture,
with a comment explaining why — the knowledge existed but was local to one file
and never generalized.

Because the leak only bites tests that run *after* the offender, and
`pytest-randomly` reseeds order each run, it presented as CI flakiness rather
than a deterministic failure.

**Suggested follow-up**: the durable fix is to stop reaching for a module-level
singleton in tests — e.g. expose config via a FastAPI dependency that tests
override, or provide a `config_override()` context manager in
`vultron/config/app.py` that owns both the env patch and the cache invalidation
so callers cannot get the order wrong. The current fix (source fixes plus an
autouse snapshot/restore guard in `test/demo/conftest.py`) contains the blast
radius but does not remove the footgun.

**Promoted**: 2026-08-17 — captured in GitHub #2323 (Concern: test infra config management footguns).
Docs PR: TBD.
