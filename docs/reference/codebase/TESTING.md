---
stakeholder_type: [project-contributor]
---

# Testing Patterns

## Core Sections (Required)

### 1) Test Stack and Commands

- **Primary test framework**: pytest >=9.1.1, with pytest-timeout and pytest-xdist
- **Assertion/mocking tools**: pytest built-in assertions; `unittest.mock` (standard library) and `monkeypatch`; no dedicated mocking library
- **Type checking in tests**: mypy (`.mypy.ini` packages `vultron, test`) and pyright (`pyrightconfig.json` includes `test`) both cover `test/` in CI

```bash
# Unit tests only (default — integration excluded)
uv run pytest --tb=short

# All tests (unit + integration) — what the CI test job runs
uv run pytest -m "" --tb=short

# Integration tests only
uv run pytest -m integration

# Specific test file
uv run pytest test/test_config.py --tb=short

# Gate form: redirect, read the exit line (never end a gate command with a pipe)
uv run pytest --tb=short > /tmp/last-test-run.log 2>&1; rc=$?; tail -5 /tmp/last-test-run.log; echo "exit: $rc"
```

### 2) Test Layout

- **Test directory**: `test/` at repo root; mirrors `vultron/` package layout (`test/core/`, `test/wire/`, `test/adapters/`, `test/metadata/`, `test/bt/`, `test/fuzzer/`)
- **Naming convention**: `test_<module>.py` files; test functions named `test_<behavior>()`.
  Files named `test_*_planned.py` hold strict-`xfail` tests for requirements whose implementation issue is still open.
- **Architecture tests**: `test/architecture/` — boundary-enforcement and ratchet tests (import-graph checks, write-site ratchets, naming/hygiene ratchets).
  Beyond the core/wire/demo import-boundary tests it includes, e.g., `test_no_bare_register_key_datalayer_nodes.py` (BTND-03-009), `test_no_dl_mutations_in_execute.py` (CLP-10-020), `test_receive_side_intake_first.py` and `test_receive_side_bt_commit_ordering.py` (ADR-0111), `test_trigger_registry_ratchets.py` and `test_trigger_port_single_method.py` (ADR-0110), `test_vocab_examples_dispatchable.py`, `test_role_authority_resolver.py`, `test_spec_coverage_ratchet.py`, `test_spec_kind_ratchet.py`, `test_codebase_docs_paths.py` (validates path references in these very docs), and `test_ratchet_hygiene.py`.
- **API contract snapshot**: `test/adapters/driving/fastapi/openapi_trigger_snapshot.json`, checked by `test_openapi_trigger_snapshot.py`, freezes the trigger and demo OpenAPI contract (TRIG-12-003); regenerate it deliberately when a request or response model changes.
- **Demo tests**: `test/demo/` holds the integration-tier demo and scenario tests (marked `integration` by `test/demo/conftest.py`); `test/demo_unit/` holds unit-tier tests of demo code (scenario registry, CLI factory, actor roles).
- **CI tests**: `test/ci/` checks workflow files (SHA pinning, path filters, failure notification, publication gates).
- **CI invariant harness**: `test/ci/invariants/universal_harness.py` — factory for the universal ledger-invariant test functions injected into each scenario module via `globals().update(make_universal_invariant_tests(...))` (ISSUE-2007).
  Read the inventory from the factory's `result` dict, not a count quoted here.
  Diagnostic guidance per invariant lives in `notes/demo-ci-diagnostics.md`, which `test/ci/invariants/test_diagnostic_map_sync.py` ratchets against the factory (ISSUE-3337).
- **Shared helpers**: `test/support/` (clock pinning, blank-string cases, core-vocab registry restore, trigger-result helpers)
- **Setup files**: `test/conftest.py` — root conftest; sets `VULTRON_DATABASE__DB_URL=sqlite:///:memory:` before any `vultron` import, registers the `spec` marker, applies the integration timeout tier, warns on unknown spec IDs, and provides `reset_datalayer()`-based isolation and the `isolated_core_registries` fixture.
  `test/core/behaviors/conftest.py` clears the py_trees blackboard before every BT test.

### 3) Test Scope Matrix

| Scope | Covered? | Typical target | Notes |
|-------|----------|----------------|-------|
| Unit | Yes | Domain models, use cases, BT nodes, state machines, config, metadata tooling | Default suite; excludes the integration marker |
| Integration | Yes | Full HTTP stack with FastAPI + SQLite; demo scenarios in-process | Marked `@pytest.mark.integration`; excluded from default `uv run pytest`, included in CI's `-m ""` run |
| Architecture boundary | Yes | Import graph enforcement, write-site and ordering ratchets | `test/architecture/` using AST/import scanning |
| Spec compliance | Yes | Any test with `@pytest.mark.spec("ID")` | Spec IDs validated against `SpecRegistry` at collection |
| API contract | Yes | Trigger/demo OpenAPI document | Golden snapshot (TRIG-12-003) |
| E2E (demo CI) | Yes | Multi-actor demo via Docker Compose | `.github/workflows/demo-integration.yml`, matrix from `.github/demo-scenarios.json`; separate from the pytest suite |
| Docker config | Yes | Compose file validity + env-var wiring | `test/docker/test_compose_env_vars.py`, `test/docker/test_docker_compose_config.sh`, `test/demo/test_multi_actor_compose.py` |

### 4) Mocking and Isolation Strategy

- **Database**: all tests use a real `sqlite:///:memory:` database — no DB mocking
- **HTTP**: outbound delivery tests patch `httpx2.AsyncClient.post` with `unittest.mock.AsyncMock` (`test/adapters/driven/test_delivery_backoff.py`); outbox-handler tests `monkeypatch` `handle_outbox_item` (`test/adapters/driving/fastapi/test_outbox_handler.py`)
- **BT blackboard**: the py_trees blackboard is process-global; the autouse fixture in `test/core/behaviors/conftest.py` clears `Blackboard.storage` before each BT test, and several other BT test modules clear it themselves
- **Registries**: tests that define local `CoreObject`/`CoreRecord` subclasses request `isolated_core_registries`, so `CORE_TYPE_MAP` is restored afterwards
- **Isolation guarantee**: per-actor in-memory stores are named shared-cache SQLite URLs, so the root conftest's autouse `_dispose_actor_stores_between_tests` fixture calls `reset_datalayer()` and `reset_store_claimants()` after every test (ADR-0073); without it, two tests using the same actor id would share rows
- **Common failure mode**: tests that import `vultron.*` before `os.environ["VULTRON_DATABASE__DB_URL"]` is set will bind to the on-disk default — prevented by conftest import ordering

### 5) Coverage and Quality Signals

- **Coverage tool**: [TODO] — no `pytest-cov` in `[dependency-groups].dev`; no coverage threshold configured
- **Current reported coverage**: [TODO]
- **Warnings**: `filterwarnings = ["error", ...]` turns every warning into a failure, except the two spec-gate warnings exempted after it
- **Known gaps/flaky areas**:
  - Core-boundary ratchet tests (`test_core_no_wire_imports.py`, `test_core_no_adapter_imports.py`) have `KNOWN_VIOLATIONS: frozenset()`, so a new violation fails CI immediately.
  - Wire-boundary test (`test_wire_core_import_allowlist.py`) is an allow-list, not a ratchet: wire MAY import `vultron/core/models/` and `vultron/core/states/` and nothing else under `vultron/core/` (ARCH-22-001 as amended by ADR-0099).
    A new core package is forbidden by default, and the rule is keyed on the importing directory so relocating a file cannot evade it.
    Imports under `if TYPE_CHECKING:` are exempt.
  - Case-ledger invariant tests require `devlogs/` JSONL artifacts (skipped when absent; `case_ledger_invariants` marker).
    The structural ratchets in the same directory (`test_universal_event_types.py`, `test_diagnostic_map_sync.py`) and the `test_common.py` helper tests carry no marker and run everywhere.
    The `_AllSkipGuard` in that directory's `conftest.py` (DEMOCI-10-005) fails a session in which every test skipped, so CI invokes one harness file at a time rather than the whole directory.
  - Demo CI integration tests run against Docker Compose and are not part of `uv run pytest`.
  - The pytest-timeout unit tier is 30 s (raised from 5 s in #2270; integration tier 60 s).
    `timeout_method = "thread"` kills the whole pytest process on a trip and prints no summary line, so a killed run can look like a passing run when piped through `tail`.
    Run with `--timeout=0` to disable when diagnosing suite-level hangs.
  - `caplog` captures log records emitted during fixture setup, not just the test body; set `caplog.set_level()` inside the test, not in a fixture.
  - Test-only TODO: `test/core/use_cases/test_reporting_workflow.py:111` asks whether dispatcher routing to the right handler should be tested there.

### 6) Evidence

- `pyproject.toml` `[tool.pytest.ini_options]`
- `.mypy.ini`
- `pyrightconfig.json`
- `test/conftest.py`
- `test/core/behaviors/conftest.py`
- `test/demo/conftest.py`
- `test/support/`
- `test/architecture/test_core_no_adapter_imports.py`
- `test/architecture/test_wire_core_import_allowlist.py`
- `test/architecture/test_no_bare_register_key_datalayer_nodes.py`
- `test/adapters/driving/fastapi/test_openapi_trigger_snapshot.py`
- `test/adapters/driven/test_delivery_backoff.py`
- `test/ci/invariants/common.py` (and per-scenario `test/ci/invariants/test_*_invariants.py`)
- `test/ci/invariants/universal_harness.py`
- `test/ci/invariants/test_diagnostic_map_sync.py`
- `.github/workflows/python-app.yml`
- `.github/workflows/demo-integration.yml`
