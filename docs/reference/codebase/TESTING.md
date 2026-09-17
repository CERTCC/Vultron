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
- **Architecture tests**: `test/architecture/` — a large (~40 file) suite of boundary-enforcement and ratchet tests (import graph checks, write-site ratchets, naming/hygiene ratchets). Beyond the core/wire/demo import-boundary tests it now includes, e.g., `test_no_bare_register_key_datalayer_nodes.py` (BTND-03-009: no new `register_key()` bare DataLayer nodes), `test_no_dl_mutations_in_execute.py` (ARCH-13), `test_role_authority_resolver.py`, `test_spec_coverage_ratchet.py`, `test_codebase_docs_paths.py` (validates path references in these very docs), and `test_ratchet_hygiene.py`
- **CI invariant harness**: `test/ci/invariants/universal_harness.py` — factory for 16 universal ledger-invariant test functions injected into each scenario module via `globals().update(make_universal_invariant_tests(...))` (ISSUE-2007); eliminates copy-paste across scenario test files
- **Setup files**: `test/conftest.py` — root conftest; sets `VULTRON_DATABASE__DB_URL=sqlite:///:memory:` before all imports and registers `spec` marker; `reset_datalayer()` fixture keeps tests isolated

### 3) Test Scope Matrix

| Scope | Covered? | Typical target | Notes |
|-------|----------|----------------|-------|
| Unit | Yes | Domain models, use cases, BT nodes, state machines, config | Default suite; fast; excluded integration marker |
| Integration | Yes | Full HTTP stack with FastAPI + SQLite | Marked `@pytest.mark.integration`; excluded from default `uv run pytest` |
| Architecture boundary | Yes | Import graph enforcement, BT execution ordering | `test/architecture/` using AST/import scanning |
| Spec compliance | Yes | Any test with `@pytest.mark.spec("ID")` | Spec IDs validated against `SpecRegistry` at collection |
| E2E (demo CI) | Yes | Multi-actor demo via Docker Compose | `.github/workflows/demo-integration.yml`; separate from unit suite |
| Docker config | Yes | Compose file validity + env-var wiring | `test/docker/test_compose_env_vars.py`, `test/docker/test_docker_compose_config.sh`, `test/demo/test_multi_actor_compose.py` |

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
  - Core-boundary ratchet tests (`test_core_no_wire_imports.py`, `test_core_no_adapter_imports.py`) have `KNOWN_VIOLATIONS: frozenset()` — those boundaries are fully clean; a new violation causes immediate CI failure
  - Wire-boundary ratchet test (`test_wire_no_core_model_imports.py`) has 32 `KNOWN_VIOLATIONS` entries — direct `vultron.core.models` imports in wire modules (ARCH-22-001). Per ADR-0082 the goal is a declared structural exemption set, **not** `frozenset()`, and the `from_core()` seam is no longer the remedy; read the current inventory from the file, not a count quoted here
  - Case-ledger invariant tests require `devlogs/` JSONL artifacts (skipped when absent; `case_ledger_invariants` marker)
  - Demo CI integration tests run against Docker Compose — not run in standard `uv run pytest`
  - **pytest-timeout unit tier is 30 s** (raised from 5 s in #2270; integration tier 60 s). `timeout_method = "thread"` kills the whole pytest process on a trip, yielding no summary line — a killed run can look like a passing run. The prior 5 s ceiling tripped AST-walking architecture ratchets nondeterministically under load (re-misdiagnosed as flakiness across ISSUE-1925/1988/2086/2237). Run with `--timeout=0` to disable when diagnosing suite-level hangs
  - `caplog` captures log records emitted during fixture setup phase (before test body), not just the test body — set `caplog.set_level()` inside the test, not in a fixture, to avoid capturing noise

### 6) Evidence

- `pyproject.toml` `[tool.pytest.ini_options]`
- `test/conftest.py`
- `test/architecture/test_core_no_adapter_imports.py`
- `test/architecture/test_wire_no_core_model_imports.py`
- `test/architecture/test_no_bare_register_key_datalayer_nodes.py`
- `test/ci/invariants/common.py` (and per-scenario `test/ci/invariants/test_*_invariants.py`)
- `test/ci/invariants/universal_harness.py`
- `.github/workflows/python-app.yml`
- `.github/workflows/demo-integration.yml`
