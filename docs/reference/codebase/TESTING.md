# Testing Patterns

## Core Sections (Required)

### 1) Test Stack and Commands

- Primary test framework: `pytest` with `pytest-timeout`
- Assertion/mocking tools: builtin `assert`, `monkeypatch`, `caplog`,
  `AsyncMock`, `MagicMock`, and FastAPI dependency overrides
- Commands:

```bash
uv run pytest --tb=short 2>&1 | tail -5
uv run pytest test/test_semantic_activity_patterns.py -v
uv run pytest -m integration
uv run pytest -m "" --tb=short 2>&1 | tail -5
```

Default local pytest runs exclude `@pytest.mark.integration`; CI runs the full
suite with `-m ""`.

### 2) Test Layout

- Test file placement pattern: dedicated `test/` tree mirroring `vultron/`
- Naming convention: `test_*.py`
- Setup files and where they run: root `test/conftest.py` sets in-memory SQLite
  defaults and spec-marker validation; deeper `conftest.py` files add area-
  specific fixtures

### 3) Test Scope Matrix

| Scope | Covered? | Typical target | Notes |
|-------|----------|----------------|-------|
| Unit | yes | adapters, use cases, semantic registry, helper functions | default local pytest run |
| Integration | yes | full HTTP stack and selected demo flows | `integration` marker is declared in `pyproject.toml` |
| E2E | yes | Docker-backed demo scenarios | manual scripts in `integration_tests/` are outside pytest |

### 4) Mocking and Isolation Strategy

- Main mocking approach: `monkeypatch`, `AsyncMock`/`MagicMock`, and dependency
  overrides for app-scoped DataLayers or emitters
- Isolation guarantees: root test config sets
  `VULTRON_DATABASE__DB_URL=sqlite:///:memory:` before imports and resets cached
  DataLayer instances before/after the session; `create_app()`-based tests use
  isolated per-app state
- Common failure mode in tests: shared/actor-scoped `DataLayer` seams and
  py_trees global state can leak behavior if fixtures do not isolate them

### 5) Coverage and Quality Signals

- Coverage tool + threshold: `[TODO]` no committed coverage-report tool config
  was found; documented expectations require 80%+ overall coverage and 100% for
  message validation, semantic extraction, dispatch routing, and error handling
- Current reported coverage: `[TODO]` no committed coverage report was found
- Known gaps/flaky areas: Docker-backed acceptance tests are outside pytest, the
  default local run omits `integration` tests, and test guidance warns that
  py_trees blackboard state can affect ordering-sensitive cases

### 6) Evidence

- `pyproject.toml`
- `test/AGENTS.md`
- `test/conftest.py`
- `test/adapters/driving/fastapi/test_outbox_monitor.py`
- `test/demo/test_two_actor_demo.py`
- `integration_tests/README.md`
- `.github/workflows/python-app.yml`
- `.github/workflows/demo-integration.yml`
