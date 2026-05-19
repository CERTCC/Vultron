# Coding Conventions

## Core Sections (Required)

### 1) Naming Rules

| Item | Rule | Example | Evidence |
|------|------|---------|----------|
| Files | Snake_case Python module names | `datalayer_sqlite.py`, `outbox_monitor.py` | `docs/reference/codebase/.codebase-scan.txt`, `vultron/adapters/driven/datalayer_sqlite.py` |
| Functions/methods | Snake_case verbs; internal/private helpers use leading `_` | `get_trigger_service`, `_deliver_with_retry` | `vultron/adapters/driving/fastapi/deps.py`, `vultron/adapters/driven/delivery_queue.py` |
| Types/interfaces | PascalCase for classes and Protocols | `SqliteDataLayer`, `OutboxMonitor`, `DataLayer` | `vultron/adapters/driven/datalayer_sqlite.py`, `vultron/core/ports/datalayer.py` |
| AS2 wire-layer classes | Use the `as_` prefix in the wire layer | `as_Activity`, `as_Actor` | `AGENTS.md`, `vultron/wire/as2/vocab/base/objects/activities/base.py` |
| Reserved-word field names | Use a trailing underscore with a Pydantic alias | `id_`, `type_`, `object_`, `context_` | `AGENTS.md`, `specs/code-style.yaml`, `vultron/wire/as2/vocab/base/objects/base.py` |
| Constants/env vars | UPPER_CASE module constants and env names | `DEFAULT_MAX_RETRIES`, `VULTRON_DB_URL` | `vultron/adapters/driven/delivery_queue.py`, `vultron/adapters/driven/datalayer_sqlite.py` |

### 2) Formatting and Linting

- Formatter: `black` with line length `79` in `pyproject.toml`
- Linters: `flake8`, `mypy`, and `pyright`; markdown is linted by
  `markdownlint-cli2` via `./mdlint.sh`
- Most relevant enforced rules: flake8 ignores `E203` and `E501`,
  `__init__.py` may ignore `F401`, and markdownlint enforces dash-style
  unordered lists while disabling `MD013`, `MD033`, `MD041`, `MD046`,
  `MD051`, and `MD060`
- Run commands: `uv run black vultron/ test/`, `uv run flake8 vultron/ test/`,
  `uv run mypy`, `uv run pyright`, `./mdlint.sh`

### 3) Import and Module Conventions

- Import grouping/order: standard library, third-party, then Vultron package
  imports is the dominant pattern in sampled files.
- Alias vs relative import policy: package-qualified absolute imports dominate;
  thin façade modules and convenience re-exports exist for callers.
- Public exports/barrel policy: selective re-exports exist in modules such as
  `vultron/enums.py`, `vultron/adapters/driven/datalayer.py`, and
  `vultron/adapters/driving/fastapi/routers/__init__.py`; no repo-wide
  barrel-export policy beyond those targeted facades was evident.

### 4) Error and Logging Conventions

- Error strategy by layer: core raises domain-specific exceptions; driving
  adapters translate failures into HTTP errors or log-and-retry behavior.
- Logging style and required context fields: the repo guidance expects log
  levels `DEBUG`/`INFO`/`WARNING`/`ERROR`/`CRITICAL` and encourages
  `activity_id` and `actor_id`; FastAPI logging is wired through Uvicorn
  handlers and `LOG_LEVEL`.
- Sensitive-data redaction rules: `[TODO]` no explicit redaction policy was
  found in the sampled runtime/config files.

### 5) Testing Conventions

- Test file naming/location rule: `test/` mirrors `vultron/`, and test modules
  use `test_*.py`
- Mocking strategy norm: prefer `monkeypatch`, dependency overrides, and cheap
  real components such as in-memory SQLite where possible; demo integration
  tests must keep distinct `DataLayer` instances per actor
- Coverage expectation: `test/AGENTS.md` states 80%+ overall coverage and 100%
  for several critical paths; no committed coverage-report config was found

### 6) Evidence

- `AGENTS.md`
- `test/AGENTS.md`
- `pyproject.toml`
- `.flake8`
- `.pre-commit-config.yaml`
- `.markdownlint-cli2.yaml`
- `vultron/adapters/driving/fastapi/deps.py`
- `vultron/adapters/driven/delivery_queue.py`
