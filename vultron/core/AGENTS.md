# AGENTS.md — vultron/core/

> For project-wide conventions see the root
> [AGENTS.md](../../AGENTS.md). This file covers rules specific to the
> domain core: use-case classes, behavior trees, and domain models.

---

## Naming Conventions (core layer)

- **Handler functions**: Named after semantic action (e.g., `create_report`,
  `accept_invite_actor_to_case`)
- **Handler use cases** (processing received messages): Use `Received` suffix
  (e.g., `CreateReportReceivedUseCase`). See CS-12-002.
- **Trigger use cases** (actor-initiated actions): Use `Svc` prefix
  (e.g., `SvcEngageCaseUseCase`). See CS-12-002.
- **Trigger service functions** in `trigger_services/`: Use a `_trigger`
  **suffix** (not an `svc_` prefix). For example: `engage_case_trigger`
  not `svc_engage_case`. The `Svc` prefix is reserved for use-case class
  names only.
- **Domain class names**: Use CVD-domain vocabulary, not wire-format parallels
  (e.g., `CaseTransferOffer` not `VultronOffer`). See CS-12-001.

---

## Use-Case Protocol

All use-case classes MUST follow this structure:

```python
class CreateReportReceivedUseCase:
    def __init__(self, dl: DataLayer, request: CreateReportReceivedEvent) -> None:
        self._dl = dl
        self._request = request

    def execute(self) -> Any:  # use None for fire-and-forget
        ...
```

- Accept `(dl, request)` in `__init__`; implement `execute() -> Any`
  (use `None` for fire-and-forget cases; see `vultron/core/ports/use_case.py`)
- Register in `SEMANTIC_REGISTRY` (`vultron/semantic_registry/`)
- Dispatcher raises `VultronApiHandlerNotFoundError` for unrecognised
  semantic types; do **not** add per-handler type validation decorators

---

## Adding a New Message Type

1. Add `MessageSemantics` enum value in `vultron/core/models/events/base.py`
2. Define an `ActivityPattern` named `<TypeName>Pattern` in
   `vultron/wire/as2/extractor.py`
3. Add a `SemanticEntry` to the **domain sub-module** under
   `vultron/semantic_registry/` (e.g., `report.py`, `case.py`, `embargo.py`).
   **Do NOT add it directly to `__init__.py`** — see pitfall below.
   (**Order matters within the sub-module** — specific before general.)
4. Implement a use-case class in `vultron/core/use_cases/`:
   - Follow `UseCase[Req, Res]` Protocol; accept `(dl, request)` in
     `__init__`; implement `execute() -> Any`
5. Add tests:
   - Pattern matching in `test/test_semantic_activity_patterns.py`
   - Routing coverage in `test/test_semantic_registry.py`
   - Use-case logic in `test/core/use_cases/`

---

## Key Files Map — core layer

- **Enums**: `vultron/core/models/events/__init__.py` — re-exports
  `MessageSemantics`; defined in `vultron/core/models/events/base.py`
- **Semantic Registry**: `vultron/semantic_registry/` — domain-split package;
  `SEMANTIC_REGISTRY` (ordered list), `find_matching_semantics()`,
  `use_case_map()`
- **Dispatcher**: `vultron/core/dispatcher.py` — `DirectActivityDispatcher`,
  `get_dispatcher()`; port: `vultron/core/ports/dispatcher.py`
- **Data Layer port**: `vultron/core/ports/datalayer.py` — `DataLayer`
  Protocol
- **BT Bridge**: `vultron/core/behaviors/bridge.py`
- **BT nodes/trees**: `vultron/core/behaviors/report/`, `case/`,
  `helpers.py`
- **Canonical Case History**: `CaseEvent` and `record_event()` were
  removed in #792. All protocol-significant history is now in the
  `CaseLedgerEntry` hash chain; see `notes/case-ledger-authority.md`.

---

## Common Pitfalls — core layer

### Idempotency Responsibility Chain

Layered: Inbox MAY detect duplicates (IE-10); Message Validation SHOULD
detect duplicate submissions (MV-08); Handlers SHOULD implement idempotent
logic — check for existing records before creating (HP-07-001). Data Layer
provides unique ID constraints. Report handlers (`create_report`,
`submit_report`) already follow this pattern.

### Use `isinstance` for Pyright Attribute Narrowing, Not `# type: ignore`

When accessing an attribute that exists on a subtype but not its base type
(pyright `[attr-defined]` error), narrow with a runtime `isinstance`
assertion rather than suppressing the error with `# type: ignore`. Example:
if `as_Question` does not have `one_of` but `ChoosePreferredEmbargoActivity`
does, add `assert isinstance(activity, ChoosePreferredEmbargoActivity)`
before accessing `activity.one_of`. This keeps the type checker accurate and
makes implicit subtype assumptions explicit and runtime-verified.

### Untyped Closures Are Invisible to mypy — Extract to Named Functions

When refactoring or extracting logic from an untyped function body or closure
(e.g., inside `extractor.py`), mypy does not check the body of untyped
functions. Hidden type errors only surface once the code is promoted to a
named, typed function. Always extract closures to named, fully-typed helper
functions; do not leave logic inside untyped lambda or nested-function
bodies. Specifically: AS2 fields that carry an object or ID reference (e.g.,
`context`, `origin`, `in_reply_to`) MUST be converted to `str | None` using
`_get_id(field)` before assigning to a `NonEmptyString | None` snapshot
field — passing the raw AS2 object directly is a type error that mypy will
catch only after extraction.

### Domain Objects Belong in `core/models/`, Not `wire/as2/vocab/objects/`

`VulnerabilityCase`, `VulnerabilityReport`, `CaseParticipant`,
`EmbargoPolicy`, `CaseStatus`, `CaseLedgerEntry`, and `VulnerabilityRecord` are
**domain objects**. They currently live in `vultron/wire/as2/vocab/objects/`
because the codebase was built wire-first, but their correct home is
`vultron/core/models/`. The wire layer should import and project from core,
not the other way around.

Consequence: `VultronActivity.object_` is typed `Any | None` because core
cannot import wire types. Referencing wire-layer domain objects in core code
is a layer-boundary violation. Do **not** add new cross-layer imports from
`vultron/core/` into `vultron/wire/as2/`. The migration of these objects to
core is tracked in issue #539. See
[notes/domain-model-separation.md](../../notes/domain-model-separation.md)
for the full architectural direction.

### Adding SemanticEntry: Use Domain Sub-Module, Not `__init__.py`

`vultron/semantic_registry/` is a package whose `__init__.py` assembles
sub-module entry lists in the correct order and appends the `UNKNOWN`
fallback entries last. When adding a new message type, add the `SemanticEntry`
to the **domain sub-module** (`report.py`, `case.py`, `actor.py`,
`embargo.py`, `note.py`, `status.py`, or `sync.py`), not to `__init__.py`
directly. Editing `__init__.py` for individual entry additions defeats the
purpose of the split (reducing merge conflicts) and risks silently corrupting
the ordering invariant that keeps the `UNKNOWN` fallback last.

### `caller_owns_em_io` Guard: BT/Service Layer Handoff for EM State

When a BT node needs to read EM state before calling a service and write it
after, use a `caller_owns_em_io` bool to distinguish two paths:

- **BT path** (`em_before` passed): caller already read EM state and will write
  it via named BT nodes. Service skips its own DataLayer read/write.
- **Legacy path** (`em_before=None`): service reads and writes internally.

```python
caller_owns_em_io = em_before is not None
if not caller_owns_em_io:
    em_before = EM(case.current_status.em_state)
assert em_before is not None  # narrows EM | None → EM for mypy
# ...compute em_after...
if not caller_owns_em_io and em_after != em_before:
    case.current_status.em_state = em_after
    case_mutated = True
```

The `assert em_before is not None` after the conditional is required for mypy
to narrow the type; without it mypy keeps the `EM | None` union and flags
downstream uses.

<!-- Source: ISSUE-1474 -->

---

### Layer-Neutral Helpers Belong in `core/models/_helpers.py`, Not Use-Cases

When a utility function has **no dependencies above `models/`** (no ports, no
state machines, no use-case logic — only primitive types like `str`, `Any`,
`uuid`), its correct home is `vultron/core/models/_helpers.py`. That module
sits at the bottom of the hexagonal stack and is safely importable by **all**
layers (`behaviors/`, `use_cases/`, `services/`, `adapters/`).

Placing such a helper in `use_cases/_helpers.py` (or any higher-layer module)
creates silent transitive layer violations everywhere the helper is used. The
right fix is to move the helper down the stack, not to create a sidecar module
at the same level.

**How to apply:** Before placing a new utility in `use_cases/_helpers.py`, ask:
does this function depend on anything above `models/`? If not, put it in
`core/models/_helpers.py`.

<!-- Source: ISSUE-1428 -->

---

### Receive-Side Wire Objects: Dual `isinstance` / `type_` Check for Core Types

Core received-side use cases process incoming wire-layer activities before
objects are stored in the DataLayer. At this boundary `case_obj` may be a
wire-layer `as_VulnerabilityCase`, not a core `VulnerabilityCase` — so
`isinstance(case_obj, VulnerabilityCase)` returns `False`.

Without importing wire types in core (which would violate ARCH-01-001), use a
dual check:

```python
if (
    not isinstance(case_obj, VulnerabilityCase)
    and getattr(case_obj, "type_", None) != "VulnerabilityCase"
):
    # reject — neither core type nor wire type claiming to be a VulnerabilityCase
    return
```

This accepts both `VulnerabilityCase` objects from `dl.read()` and
`as_VulnerabilityCase` objects from incoming activities, and rejects anything
else, without importing from `vultron/wire/`.

<!-- Source: ISSUE-1504 -->

---

### BT-related pitfalls

See [notes/bt-integration.md](../../notes/bt-integration.md) for:

- All Protocol-Significant Behavior MUST Be in the BT
- Protocol Event Cascades (Cascading Automation)
- Post-BT Procedural Cascade Anti-Pattern
- py\_trees Blackboard Global State
- py\_trees `blackboard.get()` Raises KeyError for Unwritten READ Keys
- Duplicate Method Definitions Silently Shadow Correct BT Logic
- BT Blackboard Key Naming
- BT Failure Reason: Use `get_failure_reason()`, Not Generic Error Logs
- Note Attachment Idempotency: Check `case.notes`, Not DataLayer Existence
- Close Bugs With Evidence, Not Assumption
