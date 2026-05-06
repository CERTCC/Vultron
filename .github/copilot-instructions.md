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

- Wire-layer AS2 fields/types use `as_` prefix (e.g., `as_Activity`, `as_type`)
- Core domain models do **not** use `as_` prefix; use `field_: str = Field(alias="field")` for reserved-word conflicts
- Vulnerability abbreviation: **`vul`** (not `vuln`)
- Handler use cases (processing received messages): `XxxReceivedUseCase`
- Trigger use cases (actor-initiated): `SvcXxxUseCase` (class) / `xxx_trigger` (function)
- `ActivityPattern` objects: `<TypeName>Pattern` (e.g., `CreateReportPattern`)

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

## Architecture Decision Records

ADRs live in `docs/adr/`. Consult them before making architectural changes.
Use `docs/adr/_adr-template.md` for new ADRs. Non-trivial architectural
changes (new persistence paradigm, message format, component boundaries)
require an ADR before merging.

## Further Reference

- `AGENTS.md` — comprehensive agent rules and common pitfalls
- `specs/` — formal requirements with unique IDs (e.g., `HP-01-001`)
- `notes/` — durable design insights (architecture, BT integration, AS2 semantics)
- `docs/adr/` — architecture decision records
- `.agents/skills/format-code/SKILL.md`, `.agents/skills/run-linters/SKILL.md`,
  `.agents/skills/run-tests/SKILL.md` — canonical format, lint, and test commands
