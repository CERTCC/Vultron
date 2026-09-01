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
implementation pattern. An AST ratchet in
`test/architecture/test_attributed_to_requires_save_many.py` enforces this
(tracked in #1661).

<!-- Source: CONCERN-1653 -->

---

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

### EM State Writes Are Owned by `EmbargoLifecycle` (EMB-18-001, retired in #2712)

The `caller_owns_em_io` guard and the `WriteEmStateNode` BT node are **retired**.
Do not reintroduce them.

**Current rule:** `EmbargoLifecycle` service methods always read `em_before` from
the DataLayer when not supplied and always write `em_after` back. BT nodes call
service methods directly; they never assign `case.current_status.em` inline.

See also `vultron/core/behaviors/AGENTS.md` § "EM State Reads and Writes Must Use
Canonical Nodes".

<!-- Source: ISSUE-1474; pattern retired ISSUE-2712 -->

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

`resolve_receiving_actor_id()` answers exactly one question — *whose replica
am I applying this to?* — and its only legitimate consumer is the `actor_id`
argument of `execute_with_setup()`. Every **subject** identity the message
names (invitee, accepting actor, rejecting actor, target actor) MUST be read
from the message and threaded into the tree as leaf-node data (ADR-0022).

Reusing the resolved receiving actor as a subject looks harmless when the two
coincide on the direct-delivery path, but it is a fabrication, and it is wrong
the moment the activity is processed in any store other than the subject's —
CLI dispatch, log replay, or the CaseActor handling a message on a
participant's behalf. The writes then land on the wrong participant record and
nothing raises: `#2762` put a PEC transition and an RSVP deadline
(CM-28-001, CM-28-003) on the CaseActor's own record, and the same tree factory
accepted a `rejecting_actor_id` it only logged, so the CaseActor declined its
own embargo instead of the actor who rejected.

```python
# ❌ WRONG — collapses "whose store" into "who is the subject"
receiving_actor_id = resolve_receiving_actor_id(self._dl, request.receiving_actor_id)
invitee_id = receiving_actor_id
```

```python
# ✅ CORRECT — subject from the message, receiving actor only as actor_id
receiving_actor_id = resolve_receiving_actor_id(self._dl, request.receiving_actor_id)
invitee_id = request.invitee_id          # typed property over activity.to
tree = invite_to_embargo_on_case_tree(case_id=case_id, invitee_id=invitee_id, ...)
bridge.execute_with_setup(tree=tree, actor_id=receiving_actor_id, ...)
```

Corollary for tree factories: a factory that takes a subject-identity argument
MUST pass it to the node that needs it. `OptionalLookupParticipantNode` falls
back to the BT execution actor when `target_actor_id` is falsy, so a subject
argument that is only logged is indistinguishable from one that was never
supplied. Prefer a typed property on the event class (e.g.
`InviteToEmbargoOnCaseReceivedEvent.invitee_id`) over reading `activity.to`
inline, and treat an absent `to:` as the OX-08-001 violation it is rather than
substituting another identity silently.

<!-- Source: ISSUE-2762 -->

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
