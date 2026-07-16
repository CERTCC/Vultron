# Coding Conventions

## Core Sections (Required)

### 1) Naming Rules

| Item | Rule | Example | Evidence |
|------|------|---------|----------|
| Files | Snake_case Python module names | `outbox_monitor.py`, `sync_activity_adapter.py` | `docs/reference/codebase/.codebase-scan.txt`, `vultron/adapters/driving/fastapi/outbox_monitor.py` |
| Functions/methods | Snake_case verbs; helper/private names often start with `_` | `get_default_emitter`, `_prepare_activity_object_for_delivery` | `vultron/adapters/driving/fastapi/outbox_handler.py` |
| Types/interfaces | PascalCase for classes and Protocols | `OutboxMonitor`, `SqliteDataLayer`, `DataLayer` | `vultron/adapters/driving/fastapi/outbox_monitor.py`, `vultron/adapters/driven/datalayer_sqlite/datalayer.py`, `vultron/core/ports/datalayer.py` |
| Wire-layer classes | `as_` prefix on wire vocabulary class names | `as_Activity` | `vultron/wire/as2/AGENTS.md`, `vultron/wire/as2/extractor/_extract.py` |
| Use cases | Received-side classes use `Received`; trigger-side classes use `Svc` prefix | `CreateReportReceivedUseCase`, `SvcValidateReportUseCase` | `vultron/core/AGENTS.md`, `vultron/semantic_registry/report.py`, `vultron/core/use_cases/triggers/report.py` |
| Constants/env vars | UPPER_CASE names | `DEFAULT_MAX_RETRIES`, `VULTRON_DATABASE__DB_URL` | `vultron/adapters/driven/demo_http_delivery.py`, `vultron/config.py` |

### 2) Formatting and Linting

- Formatter: `black` with `line-length = 79` in `pyproject.toml`
- Linter: `flake8` via `.flake8`; static analysis also uses `mypy` and
  `pyright`; markdown is checked by `markdownlint-cli2`
- Pre-commit hooks are **fail-only** (no auto-fix during commit): `black` runs
  with `--check`, `markdownlint-cli2` does not apply fixes. Auto-format before
  committing via the `format-code` and `run-linters` skills or `make black`.
- Most relevant enforced rules: flake8 ignores `E203` and `E501`,
  `__init__.py` may ignore `F401`, mypy checks packages `vultron` and `test`,
  and markdownlint disables `MD013`, `MD033`, `MD041`, `MD046`, `MD051`, and
  `MD060`
- Run commands: `uv run black vultron/ test/`, `uv run flake8 vultron/ test/`,
  `uv run mypy`, `uv run pyright`, `./mdlint.sh`

### 3) Import and Module Conventions

- Import grouping/order: sampled modules follow standard library, third-party,
  then `vultron.*` imports.
- Alias vs relative import policy: package-qualified absolute imports dominate;
  some package `__init__.py` files re-export public names for compatibility.
- Public exports/barrel policy: targeted re-export/facade modules exist, e.g.
  `vultron.wire.as2.extractor`, `vultron.adapters.driven.datalayer`, and
  `vultron.adapters.driving.fastapi.routers`.

### 4) Error and Logging Conventions

- Error strategy by layer: core raises project/domain exceptions; adapters log
  and translate failures at boundaries.
- Logging style and required context fields: project guidance calls for
  `DEBUG`/`INFO`/`WARNING`/`ERROR`/`CRITICAL`; root guidance requires
  `activity_id` and `actor_id` when available.
- Sensitive-data redaction rules: `[TODO]` no explicit runtime redaction policy
  was found in the sampled code/config files.

### 5) Testing Conventions

- Test file naming/location rule: `test/` mirrors `vultron/`; files are named
  `test_*.py`
- Mocking strategy norm: `monkeypatch`, `AsyncMock`/`MagicMock`, FastAPI
  dependency overrides, and isolated in-memory SQLite instances are common
- Coverage expectation: `test/AGENTS.md` states 80%+ overall coverage and 100%
  coverage for critical paths; `[TODO]` no committed coverage-report tool config
  was found

### 6) Evidence

- `AGENTS.md`
- `vultron/core/AGENTS.md`
- `vultron/wire/as2/AGENTS.md`
- `test/AGENTS.md`
- `pyproject.toml`
- `.flake8`
- `.mypy.ini`
- `.pre-commit-config.yaml`
- `.markdownlint-cli2.yaml`
- `vultron/adapters/driving/fastapi/outbox_handler.py`
