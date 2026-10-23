---
source: TASK-CFG
timestamp: '2026-05-04T18:01:51.626964+00:00'
title: pydantic-settings 2.x source priority order
type: learning
---

In pydantic-settings 2.14, `settings_customise_sources` returns a tuple where
the **first** source has the **highest** priority (it wins in the deep-merge
performed by `_settings_build_values`). The `notes/configuration.md` example
incorrectly commented "last = highest". The correct order to get env vars >
YAML is `(env_settings, YamlConfigSource(settings_cls))`.

Also: when a test fixture calls `reload_config()` in teardown (after `yield`),
it fires BEFORE pytest's `monkeypatch` reverts env var changes. This locks in
the test's env state rather than the session-level defaults from `conftest.py`.
Pattern: set `_config_cache = None` directly in teardown, and let the next
test's first `get_config()` call reload with the correctly-restored env vars.

**Promoted**: 2026-05-04 — both bugs fixed in notes/configuration.md
(source priority order comment + return tuple order corrected; testing
pattern updated to null the cache directly instead of calling reload_config()).
