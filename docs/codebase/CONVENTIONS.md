# Coding Conventions

## Core Sections (Required)

### 1) Naming Rules

| Item | Rule | Example | Evidence |
|------|------|---------|----------|
| Python modules | `snake_case.py` | `datalayer_sqlite.py`, `bt_node.py` | Any source file in `vultron/` |
| Classes | `PascalCase` | `VulnerabilityCase`, `SqliteDataLayer` | `vultron/core/models/case.py` |
| Wire-layer AS2 vocab classes | `as_` prefix + `PascalCase` | `as_VulnerabilityCase`, `as_Activity` | `vultron/wire/as2/vocab/objects/` |
| Received use-case classes | noun + `ReceivedUseCase` suffix | `CreateReportReceivedUseCase` | `vultron/core/use_cases/received/` |
| Trigger use-case classes | `Svc` prefix + noun + action + `UseCase` | `SvcCloseReportUseCase`, `SvcEngageCaseUseCase` | `vultron/core/use_cases/triggers/` |
| Trigger service functions | `_trigger` suffix (not `svc_` prefix) | `engage_case_trigger` | `vultron/core/use_cases/triggers/` |
| Use-case trigger request models | noun + `TriggerRequest` suffix | `AcceptCaseInviteTriggerRequest` | `vultron/core/use_cases/triggers/requests.py` |
| Functions / methods | `snake_case` | `get_config()`, `load_actor_config()` | `vultron/config/app.py` |
| Constants / env vars | `UPPER_SNAKE_CASE` | `VULTRON_CONFIG`, `VULTRON_DATABASE__DB_URL` | `vultron/config/app.py`, `.env.example` |
| Domain abbreviation | `vul` (not `vuln`) for vulnerability | `VulnerabilityCase`, `VulnDiscovery` | `AGENTS.md` |
| CVD sub-protocol abbreviations | `em` (embargo), `rm` (report management), `cs` (case state) | `vultron/bt/embargo_management/`, `vultron/core/states/em.py` | Directory listing |
| Test files | `test_<module>.py` | `test_config.py`, `test_states_em.py` | `test/` layout |
| Wire base class | `as_VultronObject` (not `VultronAS2Object` — retired) | `as_VultronObject` in `vocab/objects/base.py` | `vultron/wire/as2/AGENTS.md` (ARCH-14-002) |
| Wire field trailing underscore | Fields whose plain name collides with Python builtins use trailing `_`, Pydantic alias for JSON key | `id_`, `type_`, `object_`, `context_` | `vultron/wire/as2/AGENTS.md` (CS-07-002) |
| Optional string fields | "if present, then non-empty" — use `NonEmptyString`/`OptionalNonEmptyString` from `vultron/wire/as2/vocab/base/` | No per-field `@field_validator` stubs | `AGENTS.md` (CS-08-001, CS-08-002) |
| Spec IDs | `<TOPIC>-<NN>-<NNN>` | `ARCH-01-001`, `CFG-07-002` | `specs/*.yaml` |

### 2) Formatting and Linting

- **Formatter**: black, `line-length = 79`, targets Python 3.8–3.13 — config in `pyproject.toml` `[tool.black]`
- **Linter**: flake8 — config in `.flake8` (ignores E203, E501; max complexity 10; excludes `docs/`, `build/`, `dist/`)
- **Type checkers**: mypy + pyright (both run in CI, both must pass)
- **Import ordering**: isort with `profile = "black"` — config in `pyproject.toml` `[tool.isort]`
- **Markdown**: markdownlint-cli2 via `mdlint.sh`
- **Most relevant enforced rules**: line length 79, max cyclomatic complexity 10, unused imports allowed only in `__init__.py` (F401), both mypy and pyright must pass
- **Run commands**:

  ```bash
  uv run black .          # format
  uv run flake8 vultron/ test/  # lint
  uv run mypy             # type-check
  uv run pyright          # type-check (second pass)
  ./mdlint.sh             # markdown lint
  ```

### 3) Import and Module Conventions

- **Import grouping/order**: stdlib → third-party → local; isort enforces black profile
- **Absolute imports only**: no relative imports; all intra-package references use full `vultron.*` paths
- **Layer isolation**: `vultron/core/` must not import from `vultron/adapters/` or `vultron/wire/`; `vultron/config/` must not import from `vultron/adapters/` or `vultron/core/`
- **Backward-compat re-exports**: split modules re-export all public names from their `__init__.py` to avoid breaking callers (e.g., `vultron/adapters/driven/datalayer_sqlite.py`)
- **`__init__.py` F401 exception**: unused imports in `__init__.py` files are allowed (flake8 per-file-ignore)

### 4) Error and Logging Conventions

- **Error strategy by layer**:
  - Wire layer: raises `vultron.wire.errors` types on parse/validation failure
  - Core use cases: raises `vultron.errors.VultronValidationError` or similar domain errors; fail-fast at use-case boundary (ARCH-15)
  - Adapters: catch and translate errors into HTTP responses or log entries
- **Logging**: use `logging.getLogger(__name__)` at module level; `logger.debug(...)` for trace detail, `logger.warning(...)` for recoverable issues
- **Structured log fields**: include `activity_id` and `actor_id` when available — see `specs/structured-logging.yaml`
- **Sensitive data**: no specific redaction rules observed; [ASK USER] whether PII from vulnerability reports requires redaction at log points

### 5) Testing Conventions

- **Test file naming/location**: `test/` directory mirrors `vultron/` package layout; files named `test_<module>.py`
- **Spec marker**: `@pytest.mark.spec("SPEC-ID-NNN")` links tests to spec requirements; validated against `SpecRegistry` at collection time (warns on unknown IDs)
- **Integration marker**: `@pytest.mark.integration` for tests that exercise the full HTTP stack; excluded from default `pytest` run
- **Mocking strategy**: real `sqlite:///:memory:` database in all tests (no DB mocking); `conftest.py` forces in-memory DB via env var before any imports
- **Coverage expectation**: 80%+ line coverage overall; 100% for message validation, semantic extraction, dispatch routing, and error handling — see `specs/testability.yaml`. No `pytest-cov` configured in `pyproject.toml`; coverage is a target, not yet a CI gate
- **`filterwarnings = ["error"]`**: converts `warnings.warn()` to errors but does NOT catch `ResourceWarning` at process teardown; scan for `"Exception ignored in:"` after suite runs

### 6) Evidence

- `.flake8`
- `pyproject.toml` `[tool.black]`, `[tool.isort]`, `[tool.pytest.ini_options]`
- `AGENTS.md` "Coding Rules" section
- `test/conftest.py`
- `vultron/wire/as2/AGENTS.md`
