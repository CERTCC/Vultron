# GitHub Copilot Instructions for Vultron

## Project Overview

Vultron is a research prototype for a federated, decentralized protocol for
Coordinated Vulnerability Disclosure (CVD), developed at CERT/CC. It is
**not production-ready**.

Core domain concepts: **CVD** (single-party), **MPCVD** (multi-party), three
interacting state machines — Report Management (RM), Embargo Management (EM),
Case State (CS) — modeled as Behavior Trees.

## Commands

```bash
# Setup
uv sync --dev

# Format (run before every commit)
# Format and lint Python sources before committing
uv run black vultron/ test/ && uv run flake8 vultron/ test/

# Full test suite — run exactly once, read the last 5 lines
uv run pytest --tb=short 2>&1 | tail -5

# Single test file
uv run pytest test/test_semantic_activity_patterns.py -v

# Lint
uv run flake8 vultron/ test/
uv run mypy
./mdlint.sh                     # markdown only

# Docs
uv run mkdocs serve
```

Always format Python sources with Black and run `flake8` before staging
changes for commit. Do not run Black on markdown files — use
`markdownlint-cli2` for those.

## Deep Reference

For Vultron-specific architectural rules, naming conventions, validation patterns,
GitHub label naming, and the complete reference index, see **`AGENTS.md`** — the
authoritative guide for Vultron coding agents. This file focuses on platform-agnostic
setup and quick tactical guidance.

---

## Common Pitfalls & Type Checking

### mypy/pyright: dict Variance and Protocol Types

mypy and pyright are strict about type variance. If you encounter an error like
"`dict[K, V]` is not assignable to `dict[K, V] | None`", the issue is likely
that `V` involves a callable with a `Protocol` type parameter. **Fix this by
switching to `Mapping[K, V]` (covariant in value type) instead of `dict`.**
Both `mypy` and `pyright` must pass before committing.

### Spec File Format & References

All Vultron specifications are **YAML files** (`.yaml`, not `.md`). When you
need to reference a spec, use `uv run spec-dump` or invoke the `load-specs`
skill to get the authoritative, inheritance-resolved JSON view. **Never
construct spec file paths manually** — the load-specs output is the source of
truth.

### History File Immutability Exceptions

`plan/history/` files are normally immutable (enforced by pre-commit), but you
**SHOULD override immutability in two cases**:
1. **Corrupt or impossible dates** — fix entries with future dates or other data
   errors using git blame to determine correct timestamps
2. **Explicit user override** — when the user explicitly asks you to override
   immutability rules

Use `uv run append-history` to add new history entries (never append directly).
Reference: `specs/history-management.yaml` § HM-03.

**`append-history` timestamp rule:** When migrating or backfilling historical
entries (not recording current work), **always** pass `--timestamp <ISO8601>`
derived from `git log`/`git blame`. Never let it default to today's date — this
produces corrupt history that requires an immutability override to fix.

### Test Suite Runtime Expectations

The full pytest suite can take **60–120+ seconds** to complete. Use
`initial_wait: 180` when running `pytest` in sync mode. Long-running tests are
normal. For faster feedback during development, run a single test file:
`uv run pytest test/test_semantic_activity_patterns.py -v`.

For the single-run rule and full test suite guidance, see **`AGENTS.md`**
§ Agent Quickstart and § Commit Workflow.

**CRITICAL — Demo/integration test requirement:** The default `pytest` run
**omits** `@pytest.mark.integration` tests. CI always runs all tests. If **any**
file under `vultron/demo/` or `test/demo/` was touched, you **must** run the
full suite before committing:

```bash
uv run pytest -m "" --tb=short 2>&1 | tail -5
```

Skipping this is how PRs end up blocked by 17-minute CI runs.

---

## Architecture

### Hexagonal (Ports and Adapters)

The core domain (`vultron/core/`) has **no imports** from FastAPI, AS2/wire,
or adapter layers. External protocols are translated by adapters.

```
HTTP POST /inbox
  → vultron/adapters/driving/fastapi/routers/actors.py   (202 immediately)
  → BackgroundTasks
  → vultron/wire/as2/parser.py        (structural parse)
  → vultron/wire/as2/extractor.py     (AS2 → MessageSemantics)
  → vultron/core/dispatcher.py        (route to use case)
  → vultron/core/use_cases/<name>.py  (business logic + DataLayer)
```

Key constraint: `extractor.py` is the **sole** AS2→domain mapping point.
Handlers never inspect AS2 types directly.

### Layer Rules

| Layer | Module path | Allowed imports |
|---|---|---|
| Core | `vultron/core/` | Core only + shared neutral modules |
| Wire | `vultron/wire/` | Core + wire internals |
| Adapters | `vultron/adapters/` | All layers |
| API router | `vultron/adapters/driving/fastapi/routers/` | FastAPI + adapter helpers only |

### Key Files

| File | Role |
|---|---|
| `vultron/core/models/events.py` | `MessageSemantics` enum (authoritative) |
| `vultron/enums.py` | Re-exports `MessageSemantics` + other enums |
| `vultron/wire/as2/extractor.py` | `ActivityPattern` defs + `SEMANTICS_ACTIVITY_PATTERNS` |
| `vultron/core/use_cases/use_case_map.py` | `USE_CASE_MAP`: `MessageSemantics` → use-case class |
| `vultron/core/dispatcher.py` | `DirectActivityDispatcher` + `get_dispatcher()` |
| `vultron/core/ports/datalayer.py` | `DataLayer` Protocol (port) |
| `vultron/adapters/driven/datalayer_sqlite.py` | SQLite/SQLModel implementation |
| `vultron/adapters/driving/fastapi/routers/actors.py` | Inbox endpoint |
| `vultron/errors.py` | `VultronError` base + all custom exceptions |

## Key Conventions

### Naming

See **`AGENTS.md`** § Naming Conventions for the complete set of Vultron naming
rules (22 detailed conventions): `as_` prefix usage, field naming with
reserved-word conflicts, handler vs. trigger case naming, pattern object
naming, and more. All conventions are binding and enforced by tests.

### Use-Case Protocol

All use-case classes must follow this structure:

```python
class CreateReportReceivedUseCase:
    def __init__(self, dl: DataLayer, request: CreateReportReceivedEvent) -> None:
        self._dl = dl
        self._request = request

    def execute(self) -> None:
        ...
```

### Adding a New Message Type (checklist)

1. Add `MessageSemantics` enum value in `vultron/core/models/events.py`
2. Define `ActivityPattern` named `<Type>Pattern` in `vultron/wire/as2/extractor.py`
3. Add to `SEMANTICS_ACTIVITY_PATTERNS` — **order matters, specific before general**
4. Implement use-case class in `vultron/core/use_cases/`
5. Register in `USE_CASE_MAP` in `vultron/core/use_cases/use_case_map.py`
6. Add tests: pattern matching, routing, use-case logic

### ActivityStreams Semantics

- Activities are **state-change notifications**, not commands
- Inbound: update local state to reflect sender's assertion; do not execute on their behalf
- Outbound: work causes the activity; the activity does not cause the work
- `Accept`/`Reject` in reply to `Offer`/`Invite`: set `object` to an **inline typed activity object** (not an ID string); `Accept.object_` must be the Invite activity itself, not the Case object
- Call `rehydrate()` on incoming activities before pattern matching

### Data Layer

- Use `dl.save(obj)` to persist Pydantic models (`object_to_record()` + `dl.update()` has been removed)
- `VulnerabilityCase.case_status` is a **list** (`list[CaseStatusRef]`); use `case.current_status` for the active one
- Do not write typed activities to `case_activity` (enum coverage issue); store the ID string instead
- Case events: always use `case.record_event(object_id, event_type)` — never copy activity timestamps

### Behavior Trees

- Use factory methods (not direct subclassing) for BT nodes
- BT blackboard keys use `{noun}_{last_url_segment}` (no slashes in keys)
- Clear `py_trees.blackboard.Blackboard.storage` in test fixtures to prevent state leakage
- Not every handler needs a BT: use BTs for complex branching/state transitions; use procedural code for simple CRUD

### Error Handling

- All custom exceptions inherit from `VultronError` (`vultron/errors.py`)
- Dispatcher errors: `vultron/dispatcher_errors.py` (avoids circular imports)
- FastAPI inbox: return 202 within ~100ms; schedule actual work with `BackgroundTasks`

### Testing

- Test structure mirrors source: `test/core/use_cases/` mirrors `vultron/core/use_cases/`
- Use full Pydantic objects in test data (not string primitives)
- Use full URIs: `actor="https://example.org/alice"` not `actor="alice"`
- Match `MessageSemantics` to actual activity structure in test events
- **DataLayer isolation:** each actor in tests must use a **distinct** `DataLayer`
  instance — sharing one across actors is a bug. `create_app()` must NOT mutate
  global singletons (`_default_emitter`, etc.); store per-app state on `app.state`.

### Task Branching

- Default base branch is always **`main`**. Do **not** infer the base from
  `PRIORITIES.md`, issue descriptions, or any other source — if the base branch
  is anything other than `main`, the user must explicitly state it.

## Architecture Decision Records

ADRs live in `docs/adr/`. Consult them before making architectural changes.
Use `docs/adr/_adr-template.md` for new ADRs. Non-trivial architectural
changes (new persistence paradigm, message format, component boundaries)
require an ADR before merging.

## Further Reference

**Primary reference for Vultron agents:**
- **`AGENTS.md`** — Comprehensive guide with: naming conventions, validation rules,
  architecture deep-dive, key files map, common pitfalls reference index, complete
  GitHub label naming rules, change protocol, and skill interaction rules. This is
  the authoritative source for Vultron-specific guidance.

**Supplementary:**
- `specs/` — Formal requirements with unique IDs (e.g., `HP-01-001`)
- `notes/` — Durable design insights (architecture, BT integration, AS2 semantics)
- `docs/adr/` — Architecture decision records
- `.agents/skills/format-code/SKILL.md`, `.agents/skills/run-linters/SKILL.md`,
  `.agents/skills/run-tests/SKILL.md` — Canonical format, lint, and test commands
