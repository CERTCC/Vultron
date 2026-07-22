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
- **Setup files**: `test/conftest.py` — root conftest; sets `VULTRON_DATABASE__DB_URL=sqlite:///:memory:` before all imports and registers `spec` marker; `reset_datalayer()` fixture keeps tests isolated

### 3) Test Scope Matrix

| Scope | Covered? | Typical target | Notes |
|-------|----------|----------------|-------|
| Unit | Yes | Domain models, use cases, BT nodes, state machines, config | Default suite; fast; excluded integration marker |
| Integration | Yes | Full HTTP stack with FastAPI + SQLite | Marked `@pytest.mark.integration`; excluded from default `uv run pytest` |
| Architecture boundary | Yes | Import graph enforcement, BT execution ordering | `test/architecture/` using AST/import scanning |
| Spec compliance | Yes | Any test with `@pytest.mark.spec("ID")` | Spec IDs validated against `SpecRegistry` at collection |
| E2E (demo CI) | Yes | Two-actor demo via Docker Compose | `.github/workflows/demo-integration.yml`; separate from unit suite |

### 4) Mocking and Isolation Strategy

- **Database**: all tests use real `sqlite:///:memory:` — no DB mocking (mocking was abandoned after a prior incident where mocked tests passed but prod migration failed)
- **HTTP**: [TODO] — outbound HTTP delivery isolation strategy not confirmed from source scan
- **BT blackboard**: behavior tree tests typically construct a fresh `BtNode` tree per test; blackboard state does not persist across test functions
- **Isolation guarantee**: `reset_datalayer()` called in conftest ensures each test starts with a clean in-memory SQLite instance
- **Common failure mode**: tests that import `vultron.*` before `os.environ["VULTRON_DATABASE__DB_URL"]` is set will bind to the on-disk default — prevented by conftest import ordering

### 5) Coverage and Quality Signals

- **Coverage tool**: [TODO] — no `pytest-cov` in `[dependency-groups].dev`; no coverage threshold configured
- **Current reported coverage**: [TODO]
- **Known gaps/flaky areas**:
  - Architecture ratchet tests have `KNOWN_VIOLATIONS: frozenset()` — boundary is fully clean; a new violation causes immediate CI failure
  - Case-ledger invariant tests require `devlogs/` JSONL artifacts (skipped when absent)
  - Demo CI integration tests run against Docker Compose — not run in standard `uv run pytest`

### 6) Evidence

- `pyproject.toml` `[tool.pytest.ini_options]`
- `test/conftest.py`
- `test/architecture/test_core_no_adapter_imports.py`
- `test/ci/test_case_ledger_invariants.py`
- `.github/workflows/python-app.yml`
- `.github/workflows/demo-integration.yml`
