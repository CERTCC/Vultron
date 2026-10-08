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
- **Trigger-side module functions** (e.g. `replay_missing_entries_trigger` in
  `use_cases/triggers/sync.py`): Use a `_trigger` **suffix** (not an `svc_`
  prefix). The `Svc` prefix is reserved for use-case class names only.
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

    def execute(self) -> HandlerResult:
        ...
```

- Accept `(dl, request)` in `__init__`; `execute()` takes no arguments and returns
  a `UseCaseResult` subtype (`HandlerResult` received-side), never `None`
  (HP-01-001, UCORG-05-001, ADR-0095); ratcheted in `test/architecture/`
- Report a `HandlerDisposition`, never `InboxOutcome` (HP-01-004); write with
  `dl.save()`/`dl.create()`, never hand-built records (HP-08-001); both ratcheted
  in `test/architecture/`
- Store-only received handlers call `run_store_only` (`received/_store_only.py`);
  verdict via `store_only_verdict`; pre-tree refusal: `refuse_after_intake`
- Register in `SEMANTIC_REGISTRY` (`vultron/semantic_registry/`)
- Dispatcher raises `VultronApiHandlerNotFoundError` for unknown semantic types;
  do **not** add per-handler type validation decorators

---

## Adding a New Message Type

1. Add `MessageSemantics` enum value in `vultron/core/models/events/base.py`
2. Define an `ActivityPattern` named `<TypeName>Pattern` in
   `vultron/wire/as2/extractor.py`
3. Add a `SemanticEntry` to the **domain sub-module** under
   `vultron/semantic_registry/` (e.g., `report.py`, `case.py`, `embargo.py`).
   **Do NOT add it directly to `__init__.py`** — see pitfall below.
   (**Order matters within the sub-module** — specific before general.)
4. Implement a use-case class in `vultron/core/use_cases/` following the
   `UseCase` Protocol (received: `execute() -> HandlerResult`)
5. Add tests: pattern matching (`test/test_semantic_activity_patterns.py`),
   routing (`test/test_semantic_registry.py`), use-case logic (`test/core/use_cases/`)

---

## Key Files Map — core layer

- **Enums**: `vultron/core/models/events/__init__.py` — re-exports
  `MessageSemantics`; defined in `vultron/core/models/events/base.py`
- **Registries** (domain-split, data + lookups only): `vultron/semantic_registry/`
  (`SEMANTIC_REGISTRY`, `find_matching_semantics()`, `use_case_map()`) and
  `vultron/trigger_registry/` (`TriggerEntry` per verb, `entries()`,
  `lookup_entry(verb)`; a per-verb method there is the facade ADR-0110 removed)
- **Dispatchers**: `vultron/core/dispatcher.py` (`DirectActivityDispatcher`,
  port `ports/dispatcher.py`); `vultron/core/trigger_dispatcher.py`
  (`RegistryTriggerDispatcher`, port `ports/trigger_dispatcher.py`:
  `trigger(request, dl) -> ResultT_co`, UCORG-05-006)
- **Data Layer port**: `vultron/core/ports/datalayer.py` — `DataLayer` Protocol
- **BT Bridge**: `vultron/core/behaviors/bridge.py`
- **BT nodes/trees**: `vultron/core/behaviors/report/`, `case/`, `helpers.py`
- **Predicate layer** (`vultron/core/predicates/`): Pure rule layer (ISSUE-3058) — MAY import
  `states/`/`enums/`; MUST NOT import `behaviors/`/`services/`. See [notes/predicates-rule-layer.md](../../notes/predicates-rule-layer.md).
- **Canonical Case History**: `CaseEvent` and `record_event()` removed in #792;
  history is in `CaseLedgerEntry` hash chain — `notes/case-ledger-authority.md`.

---

## Common Pitfalls — core layer

### Idempotency Responsibility Chain

Layered: Inbox MAY detect duplicates (IE-10); Message Validation SHOULD detect
duplicate submissions (MV-08); Handlers SHOULD implement idempotent logic — check
for existing records before creating (HP-07-001). Data Layer provides unique ID
constraints. Report handlers (`create_report`, `submit_report`) already do this.

### Multi-Object Mutations Touching `attributed_to` MUST Use `save_many()`

Any BT node `update()` that mutates `VulnerabilityCase.attributed_to` alongside
other objects (e.g., stripping/granting `CVDRole.CASE_OWNER` on participant
records) **MUST** commit all changes via a single `self.datalayer.save_many()`
call — never via sequential `self.datalayer.save()` calls.

**Why:** Sequential saves create a window where the DataLayer holds partial
state (e.g., the old owner's `CASE_OWNER` role stripped but the new owner's
role not yet granted). A crash in that window leaves the case with zero
`CASE_OWNER` holders — unrecoverable via normal protocol messages. `save_many()`
wraps all writes in one SQLite transaction that either commits fully or rolls
back entirely (CM-21-004). See `AcceptCaseOwnershipTransferNode` in
`vultron/core/behaviors/case/nodes/ownership_transfer.py` for the canonical
implementation pattern; the AST ratchet
`test/architecture/test_attributed_to_requires_save_many.py` enforces it (#1661).

<!-- Source: CONCERN-1653 -->

---

### Use `isinstance` for Pyright Attribute Narrowing, Not `# type: ignore`

When accessing an attribute that exists on a subtype but not its base type
(pyright `[attr-defined]` error), narrow with a runtime `isinstance`
assertion rather than suppressing the error with `# type: ignore`. Example:
`as_Offer.object_` is loosely typed but `_RmSubmitReportActivity.object_` is an
`as_VulnerabilityReport`, so `assert isinstance(activity, _RmSubmitReportActivity)`
before reading report fields off `activity.object_`. This keeps the type checker accurate and
makes implicit subtype assumptions explicit and runtime-verified.

### Untyped Closures Are Invisible to mypy — Extract to Named Functions

mypy does not check the body of an untyped function, so hidden type errors
surface only once logic is promoted to a named, typed function. Always
extract closures (e.g. inside `extractor.py`) rather than leaving logic in
lambdas or nested functions. Specifically: AS2 fields carrying an object or ID
reference (`context`, `origin`, `in_reply_to`) MUST be converted with `_get_id(field)`
before assignment to a `NonEmptyString | None` snapshot field — passing the raw AS2
object is an error mypy catches only after extraction.

### Domain Objects Belong in `core/models/`, Not `wire/as2/vocab/objects/`

`VulnerabilityCase`, `VulnerabilityReport`, `CaseParticipant`,
`EmbargoPolicy`, `CaseStatus`, `CaseLedgerEntry` and `VulnerabilityRecord` are
**domain objects** that still live under `vultron/wire/as2/vocab/objects/`
because the codebase was built wire-first. The wire layer imports and projects
from core, never the reverse — which is why `VultronActivity.object_` is typed
`Any | None`. Do **not** add new imports from `vultron/core/` into
`vultron/wire/as2/`. Migration tracked in #539; full direction in
[notes/domain-model-separation.md](../../notes/domain-model-separation.md).

### Adding SemanticEntry: Use Domain Sub-Module, Not `__init__.py`

`vultron/semantic_registry/` is a package whose `__init__.py` assembles
sub-module entry lists in the correct order and appends the `UNKNOWN`
fallback entries last. When adding a new message type, add the `SemanticEntry`
to the **domain sub-module** (`report.py`, `case.py`, `actor.py`,
`embargo.py`, `note.py`, `status.py`, or `sync.py`), not to `__init__.py`
directly. Editing `__init__.py` for individual entry additions defeats the
purpose of the split (reducing merge conflicts) and risks silently corrupting
the ordering invariant that keeps the `UNKNOWN` fallback last.

### EM State Writes Are Owned by `EmbargoLifecycle` (EMB-18-001)

The `caller_owns_em_io` guard and `WriteEmStateNode` are **retired** (#2712);
do not reintroduce them. BT nodes call `EmbargoLifecycle`; never apply a
register step or assign `case.current_status.em` inline (ADR-0122). Full rule:
`vultron/core/behaviors/AGENTS.md` § "EM State Reads and Writes Must Use
Canonical Nodes". *Source: ISSUE-1474; retired ISSUE-2712*

---

### Layer-Neutral Helpers Belong in `core/models/_helpers.py`, Not Use-Cases

When a utility function has **no dependencies above `models/`** (no ports, no
state machines, no use-case logic — only primitive types like `str`, `Any`,
`uuid`), its correct home is `vultron/core/models/_helpers.py`. That module
sits at the bottom of the hexagonal stack and is safely importable by **all**
layers (`behaviors/`, `use_cases/`, `services/`, `adapters/`).

Placing such a helper in `use_cases/_helpers.py` (or any higher-layer module) creates
silent transitive layer violations everywhere the helper is used. The right fix is to
move the helper down the stack, not to create a sidecar module at the same level.

**How to apply:** Before placing a new utility in `use_cases/_helpers.py`, ask:
does this function depend on anything above `models/`? If not, put it in
`core/models/_helpers.py`.

<!-- Source: ISSUE-1428 -->

---

### Receive-Side Object Validation: Use `type_` Duck-Typing Check

Per ADR-0034, `dl.read()` and `dl.read_case()` return fully rehydrated core
`VulnerabilityCase` objects. `isinstance(case_obj, VulnerabilityCase)` checks
are no longer needed after a `read_case()` call — use a `None` check instead.

At the received-side boundary where `case_obj` comes from `activity.object_`
(not from the DataLayer), use a `type_` duck-typing check to validate the type
without importing wire types (ARCH-01-001):

```python
if getattr(case_obj, "type_", None) != "VulnerabilityCase":
    # reject — not a VulnerabilityCase
    return
```

This works for both core `VulnerabilityCase` (which has `type_ = "VulnerabilityCase"`)
and any object claiming to be one, without importing from `vultron/wire/`.

<!-- Source: ISSUE-1504 -->

---

### A Message Subject Is Never `resolve_receiving_actor_id()`

`resolve_receiving_actor_id()` answers only *whose replica am I applying this
to?*; its sole legitimate consumer is `execute_with_setup(actor_id=...)`.
Every **subject** the message names (invitee, accepting/rejecting actor,
target actor) MUST be read from the message and threaded into the tree as
leaf-node data (ADR-0022), read **from the message, never `= receiving_actor_id`**
— an `Invite(EmbargoEvent)` names its invitee as the sole `to:` recipient
(EP-09-010; several or none is refused, never guessed). Full rule, both shapes:
[notes/bt-integration.md](../../notes/bt-integration.md). *ISSUE-2762*

---

### BT-related pitfalls

See [notes/bt-integration.md](../../notes/bt-integration.md) for:

- All Protocol-Significant Behavior MUST Be in the BT
- Protocol Event Cascades (Cascading Automation)
- Post-BT Procedural Cascade Anti-Pattern

See [notes/bt-pitfalls.md](../../notes/bt-pitfalls.md) for:

- py\_trees Blackboard Global State
- py\_trees `blackboard.get()` Raises KeyError for Unwritten READ Keys
- Duplicate Method Definitions Silently Shadow Correct BT Logic
- BT Blackboard Key Naming
- BT Failure Reason: Use `get_failure_reason()`, Not Generic Error Logs
- Note Attachment Idempotency: Check `case.notes`, Not DataLayer Existence
- Close Bugs With Evidence, Not Assumption

See [notes/bt-canonical-reference.md](../../notes/bt-canonical-reference.md) for:

- Canonical CVD Protocol BT subtree map
- Anti-patterns: BT node calling use cases, importing from use_cases/
