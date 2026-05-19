# Testing Patterns

## Core Sections (Required)

### 1) Test Stack and Commands

- Primary test framework: `pytest` with `pytest-timeout`
  (declared in dev dependencies)
- Assertion/mocking tools: builtin `assert`, `monkeypatch`, `caplog`,
  FastAPI dependency overrides, local `conftest.py` fixtures
- Commands:

```bash
uv run pytest --tb=short 2>&1 | tail -5
uv run pytest test/test_semantic_activity_patterns.py -v
uv run pytest -m integration
uv run pytest -m "" --tb=short 2>&1 | tail -5
```

Default local `pytest` runs exclude `@pytest.mark.integration`; CI runs the
full suite with `-m ""`.

### 2) Test Layout

- Test file placement pattern: dedicated `test/` tree mirroring `vultron/`
- Naming convention: `test_*.py`
- Setup files and where they run: root `test/conftest.py` establishes an
  in-memory SQLite default and spec marker behavior; nested `conftest.py`
  files add area-specific fixtures

### 3) Test Scope Matrix

| Scope | Covered? | Typical target | Notes |
|-------|----------|----------------|-------|
| Unit | yes | core use cases, adapters, vocabulary, behavior nodes | default pytest run excludes `integration` marker |
| Integration | yes | full HTTP stack and demo flows | `integration` marker exists in pytest config |
| E2E | yes | Docker-backed acceptance scenarios | manual scripts under `integration_tests/` are outside pytest |

### 4) Mocking and Isolation Strategy

- Main mocking approach: `monkeypatch`, dependency overrides, and fixture-based
  DataLayer setup
- Isolation guarantees: root test config sets `VULTRON_DB_URL` to in-memory
  SQLite, resets cached DataLayer instances before and after the session, and
  multi-actor integration tests require a distinct `DataLayer` per actor
- Common failure modes in tests: fixture scope matters because shared and
  actor-scoped DataLayer seams are injected through layered `conftest.py`
  files; the default timeout is 5 seconds unless a test opts into a longer
  `@pytest.mark.timeout(...)`

### 5) Coverage and Quality Signals

- Coverage tool + threshold: no committed `pytest-cov` or coverage-report
  configuration was found; coverage expectations are documented in
  `test/AGENTS.md` and `specs/testability.yaml` (80%+ overall, 100% for
  critical paths)
- Current reported coverage: no committed coverage report was found
- Known gaps/flaky areas: acceptance tests in `integration_tests/` are manual,
  and demo/integration tests are excluded from the default local pytest run
  unless invoked with `-m integration`, `test/demo/`, or `-m ""`

### 6) Evidence

- `pyproject.toml`
- `test/AGENTS.md`
- `test/conftest.py`
- `integration_tests/README.md`
- `.github/workflows/python-app.yml`
