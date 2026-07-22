# Testing Patterns

## Core Sections (Required)

### 1) Test Stack and Commands

- **Primary test framework**: pytest >=9.1.1
- **Assertion/mocking tools**: pytest built-in assertions; `unittest.mock` (standard library); no dedicated mocking library
- **Type checking in tests**: mypy + pyright both run in CI against `test/` as well

```bash
# Unit tests only (default — integration excluded)
uv run pytest --tb=short

# All tests (unit + integration)
uv run pytest -m "" --tb=short

# Integration tests only
uv run pytest -m integration

# Specific test file
uv run pytest test/test_config.py --tb=short

# With verbose output
uv run pytest -v --tb=short
```

### 2) Test Layout

- **Test directory**: `test/` at repo root; mirrors `vultron/` package layout
- **Naming convention**: `test_<module>.py` files; test functions named `test_<behavior>()`
- **Architecture tests**: `test/architecture/` — dedicated boundary-enforcement tests (import graph checks, ratchet pattern for known violations)
- **BT harness**: `test/core/behaviors/bt_harness.py` — `BTTestScenario` class; `bt_scenario` and `bt_scenario_factory` fixtures; shared-DataLayer fixture `shared_dl_actors`
- **Setup files**: `test/conftest.py` — root conftest; sets `VULTRON_DATABASE__DB_URL=sqlite:///:memory:` before all imports and registers `spec` marker; `reset_datalayer()` fixture keeps tests isolated

### 3) Test Scope Matrix

| Scope | Covered? | Typical target | Notes |
|-------|----------|----------------|-------|
| Unit | Yes | Domain models, use cases, BT nodes (via `BTTestScenario`), state machines, config | Default suite; fast; excluded integration marker |
| Integration | Yes | Full HTTP stack with FastAPI + SQLite | Marked `@pytest.mark.integration`; excluded from default `uv run pytest` |
| Architecture boundary | Yes | Import graph enforcement, BT execution ordering | `test/architecture/` using AST/import scanning |
| Spec compliance | Yes | Any test with `@pytest.mark.spec("ID")` | Spec IDs validated against `SpecRegistry` at collection |
| E2E (demo CI) | Yes | Two-actor demo via Docker Compose | `.github/workflows/demo-integration.yml`; separate from unit suite |

### 4) Mocking and Isolation Strategy

- **Database**: all tests use real `sqlite:///:memory:` — no DB mocking (mocking was abandoned after a prior incident where mocked tests passed but prod migration failed)
- **HTTP**: [TODO] — outbound HTTP delivery isolation strategy not confirmed from source scan
- **BT blackboard**: py_trees uses a process-global `Blackboard.storage`; `BTTestScenario.run()` clears it before each execution; `unittest.TestCase`-based BT tests may show `SUBFAILED` due to ordering — clear storage in fixtures
- **BT factory injection**: when a tree builder's default `CallOutBackendFactory` is probabilistic, SUCCESS-asserting tests MUST pass an explicit deterministic factory — see `test/AGENTS.md` § "BT Factory Determinism"
- **Isolation guarantee**: `reset_datalayer()` called in conftest ensures each test starts with a clean in-memory SQLite instance
- **Demo/integration actor isolation**: each actor MUST use a distinct `DataLayer` instance; mark tests `@pytest.mark.integration`
- **Common failure mode**: tests that import `vultron.*` before `os.environ["VULTRON_DATABASE__DB_URL"]` is set will bind to the on-disk default — prevented by conftest import ordering

### 5) Coverage and Quality Signals

- **Coverage target**: 80%+ line coverage overall; 100% for message validation, semantic extraction, dispatch routing, error handling (`specs/testability.yaml`). No `pytest-cov` in `[dependency-groups].dev`; coverage is a stated goal, not a CI gate yet
- **Current reported coverage**: [TODO] — no CI coverage report configured
- **Known gaps/flaky areas**:
  - Architecture ratchet tests have `KNOWN_VIOLATIONS: frozenset()` — boundary is fully clean; a new violation causes immediate CI failure
  - Case-ledger invariant tests (`case_ledger_invariants` marker) require `devlogs/` JSONL artifacts (skipped when absent)
  - Demo CI integration tests run against Docker Compose — not run in standard `uv run pytest`
  - Trigger use cases have insufficient per-use-case tests; `test_trignotify.py` incidental coverage is not enough — see `notes/triggers-test-coverage.md`

### 6) Evidence

- `pyproject.toml` `[tool.pytest.ini_options]`
- `test/conftest.py`
- `test/AGENTS.md`
- `test/core/behaviors/bt_harness.py`
- `test/architecture/test_core_no_adapter_imports.py`
- `test/ci/test_case_ledger_invariants.py`
- `.github/workflows/python-app.yml`
- `.github/workflows/demo-integration.yml`
