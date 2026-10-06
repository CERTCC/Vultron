---
stakeholder_type: [project-contributor]
---

# Coding Conventions

## Core Sections (Required)

### 1) Naming Rules

| Item | Rule | Example | Evidence |
|------|------|---------|----------|
| Python modules | `snake_case.py`; leading `_` for package-private modules | `datalayer.py`, `bt_node.py`, `_routes.py` | Any source file in `vultron/` |
| Classes | `PascalCase` | `VulnerabilityCase`, `SqliteDataLayer` | `vultron/core/models/case.py` |
| Wire-layer AS2 vocab classes | `as_` prefix + `PascalCase` for unpaired AS2 vocabulary; for paired domain types the `as_` name is an alias of the core class (ADR-0099, ARCH-14-001) | `as_Activity`, `as_Link`; `as_VulnerabilityCase is VulnerabilityCase` | `vultron/wire/as2/vocab/objects/`, `vultron/wire/as2/AGENTS.md` |
| Trigger use-case classes | `Svc` + verb + noun + `UseCase` | `SvcCloseCaseUseCase`, `SvcEngageCaseUseCase` | `vultron/core/use_cases/triggers/` |
| Received use-case classes | verb/noun + `ReceivedUseCase` suffix | `CreateReportReceivedUseCase` | `vultron/core/use_cases/received/`, `vultron/core/AGENTS.md` |
| Trigger request models | noun + `TriggerRequest` suffix; HTTP body models without `actor_id` in `request_bodies.py` | `AcceptCaseInviteTriggerRequest` | `vultron/core/use_cases/triggers/requests.py`, `vultron/core/use_cases/triggers/request_bodies.py` |
| Trigger functions (non-class) | `_trigger` suffix, never an `svc_` prefix | `replay_missing_entries_trigger()` | `vultron/core/use_cases/triggers/sync.py`, `vultron/core/AGENTS.md` |
| Functions / methods | `snake_case` | `get_config()`, `load_actor_config()` | `vultron/config/app.py` |
| Constants / env vars | `UPPER_SNAKE_CASE` | `VULTRON_CONFIG`, `DEFAULT_MAX_RETRIES` | `vultron/config/app.py`, `vultron/adapters/driven/http_delivery.py` |
| Domain abbreviation | `vul` (not `vuln`) for vulnerability | `vul_discovery`, `assign_vul_id` | `AGENTS.md`, `vultron/bt/vul_discovery/` |
| CVD sub-protocol abbreviations | `em` (embargo), `rm` (report management), `cs` (case state), `pec` (participant embargo consent) | `vultron/bt/embargo_management/`, `vultron/core/states/em.py` | Directory listing |
| Test files | `test_<module>.py`; `test_*_planned.py` holds strict-`xfail` tests for planned requirements | `test_config.py`, `test_states_em.py`, `test_case_joining_planned.py` | `test/` layout |
| Spec IDs | `<TOPIC>-<NN>-<NNN>` | `ARCH-01-001`, `CFG-07-002` | `specs/*.yaml` |

### 2) Formatting and Linting

- **Formatter and linter**: ruff (ADR-0094), `line-length = 79`, `target-version = "py312"`.
  Config lives in `pyproject.toml` `[tool.ruff]`, which also declares the scope, so every caller runs it with no path arguments (IMPLTS-07-021).
  `ruff format` excludes `**/*.md`.
- **Selected rule families**: `E`, `W`, `F`, `C90`, `I`, `B`, `UP`, `SIM`, `RUF`, `PL`, `TRY`, `DTZ`, `BLE`, `S`, `TC`, `RET`, `G`, `PYI`.
  Every entry in `ignore` carries a comment stating why it is not enforced (IMPLTS-07-019).
  `PLC0415` (import outside top level) is ignored only per file, for `test/**` and `docs/_scripts/render_trigger_api.py`; `G004` is enforced.
- **Baselined findings**: residual findings are suppressed inline as `# noqa: <RULE>  # ruff-baseline #<issue>`, citing the issue that removes them; `per-file-ignores` is reserved for permanent, justified exemptions (`notes/lint-tooling.md`).
- **Type checkers**: mypy (`.mypy.ini`, packages `vultron` and `test`) and pyright (`pyrightconfig.json`, `basic` mode, includes `vultron` and `test`); both run in CI and both must pass.
- **Import ordering**: ruff's `I` rules (CS-02-001) with `combine-as-imports = true`, fixed by `ruff check --fix`
- **Markdown**: markdownlint-cli2 via `mdlint.sh`; codespell on docs via pre-commit
- **Most relevant enforced rules**: max cyclomatic complexity 10 (C901), unused imports allowed only in `__init__.py` (F401), unused `# noqa` directives are errors (RUF100), timezone-aware datetimes (DTZ, CS-13-001), no blind `except Exception` without a baseline marker (BLE, CS-23-001)
- **Run commands**:

  ```bash
  uv run ruff format      # format
  uv run ruff check       # lint
  uv run mypy             # type-check
  uv run pyright          # type-check (second pass)
  ./mdlint.sh             # markdown lint
  ```

### 3) Import and Module Conventions

- **Import grouping/order**: stdlib → third-party → local; ruff's `I` rules enforce it
- **Absolute imports preferred**: intra-package references mostly use full `vultron.*` paths.
  Relative imports remain in some package `__init__.py` files and in the `vultron/adapters/driven/datalayer_sqlite/` and `vultron/adapters/driven/trigger_activity_adapter/` subpackages; no ruff rule bans them.
- **Layer isolation**: `vultron/core/` must not import from `vultron/adapters/`, `vultron/wire/` or `vultron/demo/`; `vultron/config/` must not import from `vultron/adapters/` or `vultron/core/`
- **Split modules re-export**: a module split into a subpackage re-exports its public names from `__init__.py` (CS-18-003), for example `vultron/adapters/driven/datalayer_sqlite/` and `vultron/core/services/embargo_lifecycle/`
- **`__init__.py` F401 exception**: unused imports in `__init__.py` files are allowed (ruff `per-file-ignores`)

### 3a) BT Node Blackboard Conventions

- **Typed ports (preferred)**: BT DataLayer nodes must declare blackboard key dependencies as typed class attributes (`INPUT_PORTS`/`OUTPUT_PORTS` on the `WithPorts` variants) rather than calling `register_key()` at runtime.
  The ratchet test `test_no_bare_register_key_datalayer_nodes.py` enforces this, so adding a node with `register_key()` in `setup()` fails CI (BTND-03-009).
- **Wire render via port**: when a BT node needs wire-shaped (AS2 JSON) output from a domain object, it must use `WireRenderPort` (`vultron/core/ports/wire_render.py`) injected via the adapter.
  It must never import from `vultron/wire/` inside core, and never call `model_dump(by_alias=True)` in core (the ratchet baseline in `test_core_by_alias_dumps.py` is empty).
  A node reads the port with `_require_wire_render_port()`, which raises `VultronWiringError` when the port is missing.
- **Helpers raise**: core helpers raise on failure instead of returning `None`; a node's `update()` is the one place that catches and returns `FAILURE` (`notes/bt-pitfalls.md` § BT-HELPER-01).

### 4) Error and Logging Conventions

- **Error strategy by layer**:
  - Wire layer: raises `VultronWireError` subclasses (`vultron/wire/errors.py`; parse errors such as `VultronParseMissingPublishedError` in `vultron/wire/as2/errors.py`)
  - Core use cases: raise `vultron.errors` domain errors (`VultronValidationError`, `VultronNotFoundError`, `VultronWiringError`, and others); fail fast at the use-case boundary (ARCH-15)
  - Adapters: the FastAPI layer translates domain errors to HTTP responses with `domain_error_translation()` (`vultron/adapters/driving/fastapi/errors.py`)
- **Pydantic validator exceptions**: any custom exception raised from a `model_validator` or `field_validator` MUST inherit from `ValueError` (or `TypeError`/`AssertionError`) so Pydantic wraps it in `ValidationError` rather than letting it escape `model_validate()`.
  `VultronProtocolViolationError` in `vultron/errors.py` is the canonical example, and its docstring explains the requirement (issue #2905).
- **Logging**: use `logging.getLogger(__name__)` at module level; `logger.debug(...)` for trace detail, `logger.warning(...)` for recoverable issues
- **Log-call shape (SL-01-005)**: the message argument is a literal template and its values are lazy positional arguments, as in `logger.info("Actor %s engaged case %s", actor_id, case_id)`.
  Never build the message before the call with an f-string, `str.format()`, `%`-formatting, or concatenation; `!r` in a former f-string becomes `%r`.
  Ruff's `G` family (`G001`–`G004`) enforces this with no `ignore` entry and no `# noqa` markers.
  A message already built for another consumer, such as a node's `feedback_message`, is passed as one argument: `logger.warning("%s", self.feedback_message)`.
  A plain `py_trees` node's `self.logger` takes one pre-rendered message and no lazy arguments, so a helper logging on a node's behalf binds `log = node_logger(node)` from `vultron/core/behaviors/node_logger.py` and calls `log.warning(...)`.
  Lazy arguments defer only rendering, not evaluation, so a guard such as `isEnabledFor(logging.DEBUG)` stays only around a value produced by an expensive call, with a comment saying so.
  The reasoning is in `notes/structured-logging.md` § "Log-Call Shape: Template Plus Lazy Arguments (SL-01-005)".
- **Sensitive data**: `_log_label()` in `vultron/core/use_cases/_helpers.py` replaces raw actor/activity identifiers with a short hash in some use-case log messages.
  No general redaction policy was observed; [ASK USER] whether PII from vulnerability reports requires redaction at log points.

### 5) Testing Conventions

- **Test file naming/location**: `test/` directory mirrors `vultron/` package layout; files named `test_<module>.py`
- **Spec marker**: `@pytest.mark.spec("SPEC-ID-NNN")` links tests to spec requirements; validated against `SpecRegistry` at collection time (warns on unknown IDs, SR-05-002)
- **Integration marker**: `@pytest.mark.integration` for tests that exercise the full HTTP stack; excluded from default `pytest` run.
  Everything under `test/demo/` is marked by a `test/demo/conftest.py` collection hook, not by `pytestmark`.
- **Other registered markers** (`pyproject.toml` `[tool.pytest.ini_options].markers`): `case_ledger_invariants` (require `devlogs/` JSONL artifacts; skip when absent), `executes_as(actor_id)` (actor identity the test's BT runs under; opens that actor's store per ADR-0073), `spec_corpus` (tests that load real `specs/` YAML; gated on `specs/**` changes via `spec-check.yml`)
- **Warnings are errors**: `filterwarnings = ["error", ...]`, with the two spec-gate warnings exempted by `always::` entries placed after `"error"`
- **Per-test timeout**: `pytest-timeout` unit tier is 30 s (raised from 5 s in #2270; `timeout_method = "thread"`), integration tier 60 s (`INTEGRATION_TIMEOUT_SECONDS` in `test/conftest.py`)
- **Registry isolation**: tests that define a local `CoreObject`/`CoreRecord` subclass request the `isolated_core_registries` fixture (TB-06-003, TB-06-004)
- **Mocking strategy**: real `sqlite:///:memory:` database (no DB mocking); `test/conftest.py` sets the env var before any `vultron` import
- **Coverage expectation**: [TODO] — no coverage tool configured in `pyproject.toml`; CI does not report coverage percentage

### 6) Evidence

- `pyproject.toml` `[tool.ruff]`, `[tool.pytest.ini_options]`
- `.mypy.ini`
- `pyrightconfig.json`
- `notes/lint-tooling.md`
- `AGENTS.md` "Coding Rules" section
- `vultron/core/AGENTS.md`
- `vultron/errors.py`
- `vultron/wire/errors.py`
- `vultron/adapters/driving/fastapi/errors.py`
- `test/conftest.py`
- `test/demo/conftest.py`
- `vultron/wire/as2/AGENTS.md`
