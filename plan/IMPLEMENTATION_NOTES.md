## Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate
insights, issues, and learnings during the implementation process.

Add new items below this line

---

### 2026-03-16 — Refresh #34 findings

~~**P75-2c and P75-3 complete**: All handler use cases and trigger-service use
cases now live in `core/use_cases/`. The handler adapter layer is reduced to a
no-op `_shim.py`. The dispatcher is a formal driving port. Pattern objects use
`Pattern` suffix. Test count: 887 passed.~~
→ captured in `plan/IMPLEMENTATION_HISTORY.md`

~~**TECHDEBT-13 and TECHDEBT-14 complete**: V-24 resolved; `vultron_types.py`
split into per-type modules. All violations V-01 through V-24 resolved.~~
→ captured in `plan/IMPLEMENTATION_HISTORY.md`

~~**TECHDEBT-15 (new)**: `test_remove_embargo` remains flaky due to py_trees
blackboard global state. Spec TB-06-006 requires deterministic tests. Fix:
`autouse` fixture clearing `py_trees.blackboard.Blackboard.storage` in
`test/wire/as2/vocab/conftest.py`.~~
→ captured as TECHDEBT-15 in `plan/IMPLEMENTATION_PLAN.md` (marked complete)

~~**UseCase interface standardization needed before P75-4**: Per
`notes/use-case-behavior-trees.md`, define `UseCase[Req, Res]` Protocol with
`execute()` method (P75-4-pre) before wiring up CLI/MCP adapters (P75-4).~~
→ P75-4-pre and P75-4 both complete; see `plan/IMPLEMENTATION_PLAN.md`

~~**ActivityEmitter port gap**: `core/ports/emitter.py` does not exist yet.
Per `notes/architecture-ports-and-adapters.md`, this is the outbound driven
port ("Emit") counterpart to the inbound driving port `core/ports/dispatcher.py`
("Dispatch"). Added as OX-1.0 preceding the OUTBOX-1 tasks.~~
→ captured as OX-1.0 in `plan/IMPLEMENTATION_PLAN.md`

~~**Docs gaps confirmed**: `docker/README.md` lists obsolete individual demo
services (DOCS-1). `docs/reference/code/as_vocab/` references old
`vultron.as_vocab.*` paths (DOCS-2). Both captured as actionable tasks.~~
→ captured as DOCS-1 and DOCS-2 in `plan/IMPLEMENTATION_PLAN.md`

---

### 2026-03-16 — P75-4-pre complete

~~**UseCase Protocol now defined**: `UseCase[Req, Res]` lives in
`vultron/core/ports/use_case.py`. `UnknownUseCase` is the reference
implementation; the old function wrapper delegates to it.~~
→ captured in `plan/IMPLEMENTATION_HISTORY.md`; P75-4-pre and P75-4 complete

~~**CRITICAL constraint for P75-4**: P75-4 MUST refactor every use case it
touches to the class interface (`__init__(self, dl: DataLayer)` +
`execute(self, request) -> result`). Do NOT leave behind a mix of old-style
`fn(event, dl)` callables alongside new class-based use cases within a single
migration batch. The old-style callable wrapper on `unknown` is a temporary
bridge; it must be removed once the dispatcher supports class-based use cases.~~
→ P75-4 complete; no longer relevant as forward constraint

~~If necessary, expand `Req` and `Res` type variables to be a consistent
Pydantic model envelope (e.g., `UseCaseRequest` and `UseCaseResponse`) to
accommodate the fact that some use cases may require multiple input
parameters or multiple output values. This will future-proof the interface
and ensure it can handle more complex use cases without needing another
refactor.~~
→ captured as "UseCaseRequest Envelope (Future Direction)" in
`notes/use-case-behavior-trees.md`

---

### 2026-03-16 — `core/use_cases/` code-review findings

~~**Scope**: Critical review of `vultron/core/use_cases/` for DRY violations,
architecture violations, and code-quality issues.  Items marked
**FIX BEFORE P75-4** must be addressed before continuing development.~~

~~#### 1. Dead code in `embargo.py` — FIX BEFORE P75-4~~

~~Lines 335–614 of `embargo.py` contain **exact duplicates** of the class-based
use-case logic as bare functions (`create_embargo_event`,
`add_embargo_event_to_case`, etc.). These were the pre-refactor
implementations that should have been deleted when the classes were introduced.
They are not referenced anywhere in the routing table or tests.~~

~~**Action**: Delete lines 335–614 from `embargo.py`.~~
→ captured as TECHDEBT-17 in `plan/IMPLEMENTATION_PLAN.md`

~~#### 2. Dead code in `triggers/report.py` — FIX BEFORE P75-4~~

~~After the `SvcCloseReportUseCase` class definition (line 327), the file
re-imports every module-level dependency and re-defines
`_resolve_offer_and_report` a second time (lines 329–382). This is an
accidental duplication, likely an artifact of a failed merge or cut-paste
during migration.~~

~~**Action**: Delete lines 329–382 from `triggers/report.py`.~~
→ captured as TECHDEBT-18 in `plan/IMPLEMENTATION_PLAN.md`

~~#### 3. Architecture violation: `triggers/report.py` imports from
`vultron.api.v2.*` — FIX BEFORE P75-4~~

~~`triggers/report.py` imports `rehydrate` from
`vultron.api.v2.data.rehydration` and `OfferStatus`, `ReportStatus`,
`get_status_layer`, `set_status` from `vultron.api.v2.data.status`.  Core
modules (including `core/use_cases/triggers/`) MUST NOT import from the
application layer (`vultron.api.v2.*`) per ARCH-05 / CS-05-001.~~

~~**Action**: Move `rehydration.py` and `status.py` (or their relevant
interfaces) to a neutral shared location (`vultron/core/` or a new
`vultron/services/` layer), or promote the needed functions to the DataLayer
port, so that core modules can use them without importing from the adapter
layer.~~
→ captured as TECHDEBT-19 in `plan/IMPLEMENTATION_PLAN.md`

~~#### 4. Architecture violation: `case.py` and `triggers/_helpers.py` import
from wire layer~~

~~`CreateCaseUseCase.execute()` lazily imports `VulnerabilityCase` from
`vultron.wire.as2.vocab.objects.vulnerability_case`. Lazy imports are a code
smell per AGENTS.md and this particular import breaks the hexagonal
architecture constraint that core must not depend on wire types.
`triggers/_helpers.py` similarly imports `VulnerabilityCase` and
`ParticipantStatus` from the wire layer.~~

~~**Action**: Replace wire-layer type references in use cases with CaseModel /
ParticipantModel Protocol types from `core/use_cases/_types.py`, or introduce
a thin domain factory that core can call without importing wire types. The
lazy-import workaround in `case.py` should be resolved via reorganization, not
preserved.~~
→ captured as TECHDEBT-24 in `plan/IMPLEMENTATION_PLAN.md`

~~#### 5. DRY violation: `_as_id_str` pattern repeated ~7 times~~

~~The expression `x.as_id if hasattr(x, "as_id") else str(x) if x is not None
else None` (or close variants) appears across `case.py`, `actor.py`,
`embargo.py`, and `case_participant.py`. It represents the pattern of
normalising a field that may be either an object with `.as_id` or a plain
string.~~

~~**Action**: Extract a private helper `_as_id(obj) -> str | None` in
`_types.py` (or a new `_helpers.py` within `use_cases/`) and replace all
call-sites. This is low-risk and cleans up ~7 repetitions.~~
→ captured as TECHDEBT-25 in `plan/IMPLEMENTATION_PLAN.md`

~~#### 6. Inconsistent error handling — defer to later~~

~~Several use cases (e.g., `CreateReportUseCase`, `SubmitReportUseCase`) have no
outer `try/except` while others wrap their entire body. Stub use cases
(`RejectSuggestActorToCaseUseCase`, `RejectInviteActorToCaseUseCase`, etc.)
have `try/except Exception` wrapping a `logger.info()` call that can never
raise, which is meaningless noise. The silent-swallow pattern (`logger.error`
without re-raise) means callers cannot distinguish success from failure.~~

~~**Action (later)**: Standardize on letting domain exceptions propagate (remove
bare `except Exception` swallowers); let the dispatcher boundary catch and log
unexpected errors. This is a behaviour change and should wait until after the
P75-4 adapter work so error handling can be tested end-to-end.~~
→ captured in Deferred section of `plan/IMPLEMENTATION_PLAN.md`

~~#### 7. `result.status.name != "SUCCESS"` inconsistency — defer to later~~

~~`EngageCaseUseCase`, `DeferCaseUseCase`, and `CreateCaseUseCase` compare BT
result status via `result.status.name != "SUCCESS"` (string), while
`ValidateReportUseCase` uses `result.status == Status.SUCCESS` (enum import).
The enum comparison is correct; the string comparison is a latent bug if the
enum values ever change.~~

~~**Action (later)**: Normalise all BT result checks to
`result.status == Status.SUCCESS` / `result.status == Status.FAILURE`.~~
→ captured in Deferred section of `plan/IMPLEMENTATION_PLAN.md`

~~#### 8. `CloseCaseUseCase` constructs wire-type `VultronActivity` in core~~

~~`CloseCaseUseCase` in `case.py` imports `VultronActivity` from
`vultron.core.models.vultron_types` and constructs it with `as_type="Leave"`.
`as_type` is an ActivityStreams field name — this belongs in the wire layer,
not core. The use case is effectively constructing an outgoing AS2 activity
rather than emitting a domain event, which blurs the outbound boundary.~~

~~**Action (later)**: Once the `ActivityEmitter` port (OX-1.0) is defined,
`CloseCaseUseCase` should emit a domain event through that port instead of
directly constructing a wire activity.~~
→ captured in Deferred section of `plan/IMPLEMENTATION_PLAN.md` (defer until OX-1.0)

~~#### 9. `UseCase` Protocol generic types not enforced — defer to later~~

~~The `UseCase[Req, Res]` Protocol in `core/ports/use_case.py` exists but none
of the concrete use-case classes declare it as a base or use the Generic type
parameters. The result is that `execute()` return types vary (`None` vs
`dict`) with no static-analysis enforcement. Trigger use cases return `dict`
while handler use cases return `None` — these arguably should be different
subtypes of the protocol.~~

~~**Action (later, as part of P75-4)**: Decide on a consistent return type
envelope. If trigger use cases return structured data, define a
`UseCaseResult` Pydantic model. Ensure mypy can verify conformance via
structural subtyping.~~
→ captured in Deferred section of `plan/IMPLEMENTATION_PLAN.md`

~~#### Summary: priority ordering~~

~~| # | Item | Priority |~~
~~|---|------|----------|~~
~~| 1 | Delete dead functions from `embargo.py` (lines 335–614) | FIX BEFORE P75-4 |~~
~~| 2 | Delete dead code from `triggers/report.py` (lines 329–382) | FIX BEFORE P75-4 |~~
~~| 3 | Remove `api.v2.*` imports from `triggers/report.py` | FIX BEFORE P75-4 |~~
~~| 4 | Remove wire-layer imports from core use cases | Ongoing / per-file as touched |~~
~~| 5 | Extract `_as_id()` helper to remove repeated pattern | Soon (low-risk) |~~
~~| 6 | Standardize error handling | Defer to after P75-4 |~~
~~| 7 | Normalise BT status comparisons | Defer to after P75-4 |~~
~~| 8 | `CloseCaseUseCase` wire-type construction | Defer until OX-1.0 emitter port |~~
~~| 9 | UseCase Protocol generic enforcement | Defer to P75-4 |~~
→ all items captured in `plan/IMPLEMENTATION_PLAN.md` (TECHDEBT-17–25, Deferred section)

~~## UseCase interface should always be instantiated with a UseCaseRequest object~~

~~Instead of passing request parameters directly to the `execute()` method, we
should define a `UseCaseRequest` Pydantic model that encapsulates all input
parameters for a use case. The `UseCase` Protocol would then be defined as
`UseCase[Request, Response]` where `Request` is the request model and
`Response` is the response model. This approach has several benefits:~~
~~1. It provides a consistent and structured way to pass parameters to use cases,~~
~~   improving readability and maintainability.~~
~~2. It allows for better type checking and validation of input parameters, as the~~
~~   `UseCaseRequest` model can enforce required fields and types at the point~~
~~   of instantiation. The `UseCase` class can also enforce validation prior~~
~~   to `execute()` logic.~~
~~3. It future-proofs the interface, allowing for more complex use cases that~~
~~   may require multiple input parameters or nested data structures without~~
~~   needing to refactor the method signature again.~~
~~4. It aligns with common design patterns in clean architecture, where use cases~~
~~   typically accept a single request object and return a single response object,~~
~~   encapsulating all necessary data for the operation.~~
→ captured as "UseCaseRequest Envelope (Future Direction)" in
`notes/use-case-behavior-trees.md`

---

### 2026-03-16 — Second code-review pass: additional findings

~~**Scope**: Follow-up critical review of `vultron/core/use_cases/` against
DRY, naming conventions, architecture constraints, and code quality.
Previously captured items (FIX BEFORE P75-4 #1–9) remain outstanding and
are not repeated here.~~

~~#### 10. Dead import block in `triggers/embargo.py` — FIX BEFORE P75-4~~

~~Lines 279–303 of `triggers/embargo.py` are an **exact duplicate** of the
module-level imports, identical to the dead-code pattern already identified
in `triggers/report.py`. The block begins with a bare `import logging` after
the `SvcTerminateEmbargoUseCase` class definition and ends with a duplicate
`logger = logging.getLogger(__name__)`.~~

~~**Action**: Delete lines 279–303 from `triggers/embargo.py`.~~
→ captured as TECHDEBT-20 in `plan/IMPLEMENTATION_PLAN.md`

~~#### 11. Handler use cases lack `Received` suffix — FIX BEFORE P75-4~~

~~All use cases in the top-level `use_cases/` modules (`actor.py`, `case.py`,
`case_participant.py`, `embargo.py`, `note.py`, `report.py`, `status.py`)
represent **messages received from another party**. Their current names
(e.g. `RemoveEmbargoEventFromCaseUseCase`, `AcceptInviteActorToCaseUseCase`)
do not distinguish them from trigger (outgoing-action) use cases. The trigger
use cases already use the `Svc` prefix (`SvcEngageCaseUseCase`, etc.),
establishing a precedent for semantic disambiguation in names.~~

~~All handler use cases should be renamed to include a `Received` suffix, e.g.:~~

~~| Current name | Proposed name |~~
~~|---|---|~~
~~| `RemoveEmbargoEventFromCaseUseCase` | `RemoveEmbargoEventFromCaseReceivedUseCase` |~~
~~| `AcceptInviteActorToCaseUseCase` | `AcceptInviteActorToCaseReceivedUseCase` |~~
~~| `CreateReportUseCase` | `CreateReportReceivedUseCase` |~~
~~| (…all ~32 handler use cases) | (add `Received` suffix) |~~

~~The `USE_CASE_MAP` in `use_case_map.py` must be updated in the same commit.
Tests that import use-case class names must also be updated. This rename
should be done **before** P75-4 adds new use cases so that the naming
pattern is consistent from the start. It is a mechanical rename with no
behaviour change.~~
→ captured as TECHDEBT-21 in `plan/IMPLEMENTATION_PLAN.md`;
convention documented in `specs/code-style.md` CS-12-002

~~#### 12. `UseCase` Protocol not explicitly declared — FIX BEFORE P75-4~~

~~`core/ports/use_case.py` defines `UseCase[Req, Res]` but none of the
concrete use-case classes declare it as their Protocol base. Without the
explicit inheritance, mypy cannot verify structural conformance and there
is no static guarantee that a class satisfies the protocol contract.~~

~~**Action**: Add `UseCase[RequestType, ResponseType]` as the base Protocol
for every use case class, e.g.:~~

~~```python~~
~~from vultron.core.ports.use_case import UseCase~~

~~class CreateReportReceivedUseCase(UseCase["CreateReportReceivedEvent", None]):~~
~~    ...~~
~~```~~

~~For trigger use cases that return `dict`, use `UseCase[TriggerRequest, dict]`.
This is a low-risk addition that makes the design intent explicit and
enables future mypy enforcement.~~
→ captured as TECHDEBT-22 in `plan/IMPLEMENTATION_PLAN.md`

~~#### 13. `triggers/requests.py` DRY violation — do soon (low-risk)~~

~~All 8 trigger request models repeat `model_config = ConfigDict(extra="ignore")`
and all 8 include `actor_id: str`. Extract a base class:~~

~~```python~~
~~class TriggerRequest(BaseModel):~~
~~    model_config = ConfigDict(extra="ignore")~~
~~    actor_id: str~~
~~```~~

~~Each concrete model then subclasses `TriggerRequest` and adds only its
domain-specific fields. This eliminates 8 × 2 lines of repeated code with
zero behaviour change.~~
→ captured as TECHDEBT-23 in `plan/IMPLEMENTATION_PLAN.md`

~~#### 14. Idempotent-create boilerplate repeated ~6 times — defer~~

~~`CreateEmbargoEventUseCase`, `CreateNoteUseCase`, `CreateCaseParticipantUseCase`,
`CreateCaseStatusUseCase`, `CreateParticipantStatusUseCase`, and
`SuggestActorToCaseUseCase` (plus `AcceptSuggestActorToCaseUseCase`,
`InviteToEmbargoOnCaseUseCase`) all follow the same pattern:~~

~~```python~~
~~existing = self._dl.get(request.object_type, request.object_id)~~
~~if existing is not None:~~
~~    logger.info("... already stored — skipping (idempotent)", ...)~~
~~    return~~
~~obj = request.<domain_field>~~
~~if obj is not None:~~
~~    self._dl.create(obj)~~
~~    logger.info("Stored ...", ...)~~
~~else:~~
~~    logger.warning("... no object for event ...", ...)~~
~~```~~

~~A private helper `_idempotent_create(self, object_type, object_id, obj,
label)` in a shared base class or module-level function would eliminate ~40
lines of repeated code across these classes. Defer until after P75-4 to
avoid conflicts with in-flight work.~~
→ captured in Deferred section of `plan/IMPLEMENTATION_PLAN.md`

~~#### 15. Stub-only use cases wrap `logger.info()` in `try/except Exception`~~

~~`RejectSuggestActorToCaseUseCase`, `RejectCaseOwnershipTransferUseCase`,
`RejectInviteActorToCaseUseCase`, `RejectInviteToEmbargoOnCaseUseCase`, and
`AnnounceEmbargoEventToCaseUseCase` all wrap a single `logger.info()` call
in a `try/except Exception as e: logger.error(...)`. Since `logger.info()`
cannot raise a checked domain exception, the guard is dead code that creates
false safety and adds noise.~~

~~This is related to finding #6 (error handling standardization) which is
already deferred. When that work begins, these stubs should be the first
targets — simply remove the `try/except` wrapper entirely.~~
→ captured in Deferred section of `plan/IMPLEMENTATION_PLAN.md`

~~#### 16. Pending items from previous review still outstanding~~

~~Items 1–5 from the previous review section above (dead functions in
`embargo.py`, dead code in `triggers/report.py`, `api.v2.*` imports in
`triggers/report.py`, `_as_id()` helper extraction) are **confirmed still
present** in the code as of this review pass. They remain FIX BEFORE P75-4
unless P75-4 is explicitly scoped to not touch the affected files.~~
→ all captured in `plan/IMPLEMENTATION_PLAN.md` TECHDEBT-17–25

~~#### Summary: new items by priority~~

~~| # | Item | Priority |~~
~~|---|------|----------|~~
~~| 10 | Delete dead import block from `triggers/embargo.py` (lines 279–303) | FIX BEFORE P75-4 |~~
~~| 11 | Rename handler use cases with `Received` suffix | FIX BEFORE P75-4 |~~
~~| 12 | Declare `UseCase[Req, Res]` Protocol on every use case class | FIX BEFORE P75-4 |~~
~~| 13 | Extract `TriggerRequest` base class in `triggers/requests.py` | Soon (low-risk) |~~
~~| 14 | Extract idempotent-create helper | Defer to after P75-4 |~~
~~| 15 | Remove meaningless `try/except` from stub-only use cases | Defer (part of error-handling pass) |~~
→ all captured in `plan/IMPLEMENTATION_PLAN.md` TECHDEBT-20–26 and Deferred section
