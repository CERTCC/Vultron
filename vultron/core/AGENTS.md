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
- Register in `SEMANTIC_REGISTRY` (`vultron/semantic_registry.py`)
- Dispatcher raises `VultronApiHandlerNotFoundError` for unrecognised
  semantic types; do **not** add per-handler type validation decorators

---

## Adding a New Message Type

1. Add `MessageSemantics` enum value in `vultron/core/models/events/base.py`
2. Define an `ActivityPattern` named `<TypeName>Pattern` in
   `vultron/wire/as2/extractor.py`
3. Add a `SemanticEntry` to `SEMANTIC_REGISTRY` in
   `vultron/semantic_registry.py` (**order matters** — specific before
   general)
4. Implement a use-case class in `vultron/core/use_cases/`:
   - Follow `UseCase[Req, Res]` Protocol; accept `(dl, request)` in
     `__init__`; implement `execute() -> Any`
5. Register in `SEMANTIC_REGISTRY` in
   `vultron/semantic_registry.py`
6. Add tests:
   - Pattern matching in `test/test_semantic_activity_patterns.py`
   - Routing coverage in `test/test_semantic_registry.py`
   - Use-case logic in `test/core/use_cases/`

---

## Key Files Map — core layer

- **Enums**: `vultron/core/models/events/__init__.py` — re-exports
  `MessageSemantics`; defined in `vultron/core/models/events/base.py`
- **Semantic Registry**: `vultron/semantic_registry.py` — `SEMANTIC_REGISTRY`
  (ordered list), `find_matching_semantics()`, `use_case_map()`
- **Dispatcher**: `vultron/core/dispatcher.py` — `DirectActivityDispatcher`,
  `get_dispatcher()`; port: `vultron/core/ports/dispatcher.py`
- **Data Layer port**: `vultron/core/ports/datalayer.py` — `DataLayer`
  Protocol
- **BT Bridge**: `vultron/core/behaviors/bridge.py`
- **BT nodes/trees**: `vultron/core/behaviors/report/`, `case/`,
  `helpers.py`
- **Case Event Log**: `vultron/wire/as2/vocab/objects/case_event.py` — use
  `VulnerabilityCase.record_event(object_id, event_type)`

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
