## Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate
insights, issues, and learnings during the implementation process.

Add new items below this line

---

### 2026-03-19: mkdocs build ERROR — stale `:::` module references in case_states docs

**Issue**: `mkdocs build` failed with ERROR on `reference/code/case_states.md`
because it referenced modules that no longer exist:
`vultron.case_states`, `vultron.case_states.hypercube`,
`vultron.case_states.states`, `vultron.case_states.validations`,
`vultron.case_states.errors`.

**Root cause**: Commit `134f98c` (refactor VCR-019a) moved
`vultron/case_states/` into `vultron/core/` with the following renames:

- `vultron.case_states` → `vultron.core.case_states`
- `vultron.case_states.hypercube` → `vultron.core.case_states.hypercube`
- `vultron.case_states.states` → `vultron.core.states.cs`
- `vultron.case_states.validations` → `vultron.core.case_states.validations`
- `vultron.case_states.errors` — deleted; errors merged into `vultron.errors`

The docs file was not updated as part of that refactor.

**Resolution**:

- Updated `docs/reference/code/case_states.md` to use the new module paths.
- Removed the reference to the deleted `errors` submodule.
- Extended `test/test_docs_imports.py` with a new test
  `test_mkdocstrings_module_references_are_importable` that scans all docs
  for `:::` directives and asserts each referenced module is importable,
  preventing this class of regression.

---

### 2026-03-19: mkdocs markdown_exec errors — stale import paths in docs

**Issue**: `mkdocs build` reported `ModuleNotFoundError: No module named
'vultron.scripts.vocab_examples'` in numerous documentation code blocks.

**Root cause**: `vultron/scripts/vocab_examples.py` was refactored into
`vultron/wire/as2/vocab/examples/` (split into submodules:
`actor.py`, `case.py`, `embargo.py`, `note.py`, `participant.py`,
`report.py`, `status.py`, with `vocab_examples.py` as the aggregating
re-export module). The docs markdown code blocks were not updated to
use the new import path.

A secondary error was found in `docs/howto/activitypub/objects.md` where
`_case.add_participant()` was called with a plain string URL. The
`VulnerabilityCase.add_participant()` method now requires a full
`CaseParticipant` object (to populate the `actor_participant_index`).

**Resolution**:

- Updated all 32 affected docs files to import from
  `vultron.wire.as2.vocab.examples.vocab_examples`.
- Fixed `objects.md` to use `add_vendor_participant_to_case().as_object`
  and `add_finder_participant_to_case().as_object` for the participants.
- Added `test/test_docs_imports.py` to catch future regressions of this
  kind.

**Architectural note**: The `vocab_examples.py` aggregation module at
`vultron/wire/as2/vocab/examples/vocab_examples.py` serves as a stable
public API for documentation code examples. Docs should always import
from this single module path (not from individual submodules) to reduce
churn when internals are reorganized.

---

### 2026-03-18: Logging Error fix — `actors.py` verbose INFO logs

**Issue**: `ValueError: I/O operation on closed file` appeared in PyCharm
when running tests. The error originated in
`vultron/adapters/driving/fastapi/routers/actors.py` at lines 71 and 75
where `logger.info(f"results: {results}")` and `logger.info(f"rec: {rec}")`
dumped full raw database records.

**Root cause**: FastAPI runs sync route handlers in an anyio thread pool.
pytest captures log output via a `StreamHandler` whose underlying stream is
closed after each test. If the anyio thread logs after test teardown, Python's
logging system throws `ValueError: I/O operation on closed file`. The
immediate trigger was two unnecessary `logger.info()` calls that dumped
enormous raw DB record representations.

**Resolution**: Removed the two verbose `logger.info()` calls and replaced
them with a single `logger.debug()` message logging only the record count.
Added a regression test
(`test_get_actors_does_not_log_raw_records_at_info_level`) that uses `caplog`
to assert no INFO-level messages starting with `"results:"` or `"rec:"` are
emitted by the endpoint.

**Architectural note**: Per project logging guidelines, raw payload/object
dumps belong at DEBUG level at most. INFO-level logs should record lifecycle
events (e.g., "fetched N actors"), not full data representations.

### 2026-03-18: VCR-019c — Enum/state consolidation study

**Task**: VCR-019c — Study which enums across `case_states/` and
`bt/**/states.py` can be consolidated before implementing VCR-019a/b.

#### Inventory

**From `vultron/bt/` (sub-module `states.py` files):**

- `vultron/bt/report_management/states.py` — `RM` (StrEnum, 7 states),
  plus `RM_CLOSABLE`, `RM_UNCLOSED`, `RM_ACTIVE` groups
- `vultron/bt/embargo_management/states.py` — `EM` (StrEnum, 5 states)
- `vultron/bt/roles/states.py` — `CVDRoles` (Flag)
- `vultron/bt/messaging/states.py` — `MessageTypes` (Enum, protocol
  message codes RS/RI/RV/RD/RA/RC/EP/ER/EA/ET/CV/CF/CD/CP/CX/CA/GI etc.)
- `vultron/bt/states.py` — `CapabilityFlag` (Flag) + `ActorState`
  (Pydantic BaseModel combining all state enums with BT-runtime fields)

**From `vultron/case_states/`:**

- `case_states/states.py` — `CS` (Enum, 32 compound states), plus
  `CS_vfd` (4 states), `CS_pxa` (8 states), `VfdState`/`PxaState`/
  `CompoundState` (NamedTuples), six `IntEnum` components
  (`VendorAwareness`, `FixReadiness`, `FixDeployment`, `PublicAwareness`,
  `ExploitPublication`, `AttackObservation`), and helper functions
  (`state_string_to_enums`, `state_string_to_enum2`)
- `case_states/errors.py` — `CvdStateModelError` hierarchy (8 exception
  classes, all inherit from `VultronError`)
- `case_states/enums/` — scoring/assessment enums: `EmbargoViability`
  (IntEnum), SSVC-2 enums, CVSS-3.1 enums (stub), `Actions` (potential
  actions), VEP enums, zero-day type enums
- `case_states/patterns/`, `hypercube.py`, `validations.py`,
  `type_hints.py`, `make_doc.py` — supporting utilities (not pure enums)

#### Overlap analysis (no duplicates found)

`EM` (bt/) and `EmbargoViability` (case_states/enums/) are distinct:
`EM` is the state machine (NONE/PROPOSED/ACTIVE/REVISE/EXITED);
`EmbargoViability` is a scoring/assessment concept. No merge needed.
No other overlapping definitions found across the two packages.

#### Categorization for relocation

**Group A — Core protocol state machines (move to `vultron/core/` in
VCR-019a/b):**

- `RM` — used by core/, wire/, demo/, bt/
- `EM` — used by core/, wire/, demo/, bt/
- `CS`, `CS_vfd`, `CS_pxa`, component IntEnums, NamedTuple helpers —
  used by core/, wire/, demo/, bt/
- `CVDRoles` — used by core/, wire/, demo/, bt/ (domain-level concept)

Recommended target: `vultron/core/states/` (new sub-package with
`rm.py`, `em.py`, `cs.py`, `roles.py`, and `__init__.py` re-exporting
all).

**Group B — Error hierarchy (integrate in VCR-019a):**

- `CvdStateModelError` and subclasses → merge into `vultron/errors.py`
  or create `vultron/core/errors.py` (aligned with existing
  VultronError hierarchy).

**Group C — Assessment/scoring enums (move with case_states/ in
VCR-019a, but not to core/states/):**

- `EmbargoViability`, SSVC-2, CVSS-3.1, VEP, Actions, zero-day types
  — scoring/advisory enums, not protocol state machines. Keep together
  in `vultron/core/scoring/` (or `vultron/core/case_states/enums/`).

**Group D — BT-runtime-only (do NOT move to core/):**

- `MessageTypes` — BT-internal protocol codes; stay in
  `vultron/bt/messaging/states.py`
- `CapabilityFlag` — BT-simulator actor capability flags; stay in bt/
- `ActorState` — BT-simulator Pydantic model; stay in bt/

#### Implementation guidance for VCR-019a/b

1. Create `vultron/core/states/` package with `rm.py`, `em.py`,
   `cs.py`, `roles.py`; consolidate exports in `__init__.py`.
2. Move `RM` (with groups), `EM`, `CS`/`CS_vfd`/`CS_pxa`/etc.,
   `CVDRoles` to the new package. Do NOT alter enum members.
3. Move `case_states/errors.py` classes to `vultron/errors.py` (or
   `vultron/core/errors.py`).
4. Move `case_states/enums/` scoring enums to `vultron/core/scoring/`
   (or keep under `vultron/core/case_states/` as a rename).
5. Move `case_states/` utilities (`patterns/`, `hypercube.py`, etc.)
   to `vultron/core/case_states/` or `vultron/core/states/`.
6. Update all 60+ callers in vultron/ and 21+ in test/ in one batch;
   no shims.
7. `MessageTypes`, `CapabilityFlag`, `ActorState` stay in `vultron/bt/`.

**Note on VCR-019b scope**: `bt/states.py` contains `ActorState` (a
full Pydantic BaseModel for the BT simulator runtime) in addition to
`CapabilityFlag`. This file should NOT be moved wholesale; only the
enum definitions (`CapabilityFlag`) could theoretically move, but
since it is BT-simulator-specific it should stay in bt/.

---

### 2026-03-18: VultronActivity.actor now required — test fixture update

**Issue**: `VultronActivity.actor` was changed from `Optional[NonEmptyString]`
to required `NonEmptyString`. This caused 17 test failures because tests
instantiated `VultronActivity`, `VultronOffer`, `VultronAccept`, and
`VultronCreateCaseActivity` without providing `actor`.

**Root cause**: Every AS2 Activity MUST have an actor (the agent performing the
activity). Making `actor` required enforces this protocol invariant at the
model layer.

**Fix**: Updated test fixtures in three files to supply a valid `actor` URL:

- `test/core/models/test_base.py`: Added `actor` to `REQUIRED_KWARGS` for all
  four activity classes; updated `test_vultron_activity_as_type_required` and
  `test_domain_object_expected_as_types` inline instantiations.
- `test/test_behavior_dispatcher.py`: Added `actor` to `VultronActivity()`
  call.
- `test/core/behaviors/case/test_create_tree.py`: Added `actor` to
  `VultronOffer()` calls inside `FakeActivity` class bodies; also added
  `actor_id` as an explicit fixture parameter to both affected test functions.
  **Gotcha**: Python class bodies do NOT receive pytest fixture values from
  their enclosing function scope — the name `actor_id` at class-body level
  resolves to the fixture *function* object, not the string value, causing a
  Pydantic `ValidationError`. The fix is to add `actor_id` as a named
  parameter on the test function so pytest injects the string value into the
  function's local scope, making it accessible inside the class body.

## `wire` needs pydantic field aliases, `core` does not

The field aliases found in `BaseModel`-derived classes in `vultron/wire/as2`
are there to ensure that JSON serialization and deserialization produces the
correct field names as defined in the AS2 specification, which often include
names that are also python reserved keywords (e.g., `type`, `object`, `id`).
These aliases allow us to use valid Python identifiers in our code while
still adhering to the AS2 spec when converting to and from JSON.

However, in the parallel models in `vultron/core/models`, we do not want to  
use field aliases because these models are for internal core use so we don't
need to adhere to the AS2 field naming conventions in our internal code.
Using aliases in the core models just adds unneeded complexity and
indirection when working with these models in the core logic.

---

## Datalayer depends too much on wire format

The datalayer port used by core relies on an object registry for rehydration
that is currently implemented in a way that is tightly coupled to the AS2
wire format for type names. This was less of a problem before we separated
wire and core from each other but it is now showing up in complex ways in
rehydration, find_in_vocabulary, etc.,
hindering progress. We need to resolve this quickly.

The data model was roughly intended to map different AS2 types onto
different tables in the datalayer so that we could easily query for specific
types of objects. So now that that there is a separation between wire and
core types we are running into issues where the datalayer is expecting to
find AS2 type names, but the core would make better use of more semantically
relevant object types. If we need to continue storing raw AS2 objects in the
datalayer, we might need to separate those out from the core's interactions
with the datalayer so they are not conflicting with each other.

This requires some planning effort to understand the problem and determine
the best way forward. Refactoring both wire and core's interactions with the
datalayer may be necessary to resolve this issue.

---

## Refactor large tests

`test/api/v2/backend/test_handlers.py` is far too large and it no longer
maps to the current code structure. Refactor it to be more modular and
reflect the move from api/v2/backend to adapters.

## Unblocking VCR-030

VCR-030 (delete `vultron/sim/`) was found to have callers in `vultron/bt/`:

- `vultron/bt/states.py`
- `vultron/bt/messaging/outbound/behaviors.py`
- `vultron/bt/messaging/inbound/fuzzer.py`
- `vultron/bt/report_management/_behaviors/report_to_others.py`

All import `vultron.sim.messages.Message`. VCR-030 can be resolved by moving
the `Message` class into `vultron/bt/messaging/message.py` (create as new
module). This is a more appropriate location for `Message` anyway as it is
only relevant to the older `vultron/bt` simulator anyway.

---

## VCR-019a — Lessons Learned

**Sed-based bulk replacement works cleanly** for this type of module-rename
refactoring: `sed -i '' 's/old\.path/new\.path/g'` applied to each file is
faster and less error-prone than editing files individually.

**Test directory must mirror source directory.** Moving `test/case_states/`
to `test/core/case_states/` (with a `__init__.py`) ensures pytest discovers
tests under the new paths and that the test layout mirrors the source layout
per project conventions.

**No shims = immediate confidence.** With no compatibility re-exports left
behind, a clean test run proves all callers were updated correctly. Any missed
import site causes an immediate `ImportError` rather than a silent passthrough.

**`vultron.case_states.enums.*` files had no cross-imports** within the enums
package itself, so copying to `vultron/core/scoring/` required no import
updates inside those files — only in their callers.

---

## vultron.api.v2.backend.trigger_services should go away

The code in `vultron.api.v2.backend.trigger_services` is a thin residual
layer that has been mostly obsoleted in concept by the `vultron.adapters.
driven` and `vultron.core.use_cases` packages. This isn't a straight
replacement though, there is a need to study the trigger_services modules
compared to `vultron.adapters` and `vultron.core` and
determine a specific refactoring plan to merge `trigger_services` into them.

`vultron.api.v2.backend.trigger_services._helper.py` consists of a backwards
compatibility shim import block that should be refactored out by direct
imports, plus a `translate_domain_errors` function that belongs somewhere
near `vultron.adapters.driving.fastapi` because it's directly relevant to
the http api provided by that package.

`vultron.api.v2.backend.trigger_services._models.py` might belong in
`vultron.core.models` if appropriate, or if they are more like
adapter-specific models then maybe they belong in `vultron.adapters` somewhere.
This decision needs to be part of the evaluation.

The other modules in `vultron.api.v2.backend.trigger_services` (`case.py`,
`embargo.py`, and `report.py`) might be thin adapters that might be used by
multiple driving adapters later (fastapi, cli, etc.) so they might belong in
a `vultron.adapters.driving.common` package or something like that. They
don't seem like they belong in `vultron.core`.

---

## 2026-03-19: VCR-025 — ActivityDispatcher Protocol evaluation

**Decision**: Retain `ActivityDispatcher` in `vultron/core/ports/dispatcher.py`.

**Rationale**: The port is actively used in two places:

1. `vultron/core/dispatcher.py` — `get_dispatcher()` returns
   `ActivityDispatcher` as its annotated return type.
2. `vultron/adapters/driving/fastapi/inbox_handler.py` — module-level
   `_DISPATCHER: ActivityDispatcher | None = None` type annotation.

`ActivityDispatcher.dispatch(event, dl)` and `UseCase[Req, Res].execute()`
serve different roles in the dispatch pipeline. The dispatcher mediates
between a driving adapter and the routing table; a use case executes a
single business operation. Replacing one with the other would collapse
two distinct abstraction levels. Retaining both is architecturally correct.

No migration plan is needed; no action beyond documentation.

## VCR-019e clarification

Item 1: The IntEnum components in CS_*

The CS_vfd and CS_pxa enums use NamedTuples so they are not candidates for
StrEnum. However, they are composed of the six IntEnum components  
(VendorAwareness, FixReadiness, etc.) that do seem to potentially be
convertible to StrEnum with the right refactoring. Their existence as
IntEnums is a historical artifact of the original implementation and does
not necessarily represent a deliberate design choice. They carry more useful
meaning as StrEnum members than as IntEnum members, so converting them to
StrEnum and ensuring their string values are used consistently would be
worthwhile.

The general principle is that IntEnum is likely to be a historical artifact
rather than intent, and we should convert to StrEnum and pay off the
technical debt while we're here.

Item 2: Message types and 'duplicates'

With respect to MessageTypes, the apparent duplicate aliases for "EA", "EP",
and "ER" are the result of a post-design realization that revision proposal,
rejection, and acceptance messages are conceptually identical to the
existing proposal, rejection, and acceptance message types, so the same
codes were reused for both. EP = EV, ER = EJ, and EA = EC, and EP, ER, and
EA are the preferred shorthand. We don't need to perpetuate this
duplication forever, so as part of VCR-019e we need to re-evaluate
whether or not we
could just refactor the places where the
`VULTRON_MESSAGE_EMBARGO_REVISION_*` names or their aliases are used and
just replace them with the equivalent `VULTRON_MESSAGE_PROPOSAL_*` names or
their parallel aliases, with a strong preference for "yes we should do that"
unless there is a major reason not to.
This would eliminate the
duplication and make the
implementation a bit cleaner than the original design docs had it.

## Resolve VCR-022 vs TECHDEBT-16 once and for all

On your next evaluation pass, actually confirm whether VCR-022 is really
identical to TECHDEBT-16 and whether it should be marked complete or clarify
what is left to be completed. Do not accept assertions that they are
equivalent tasks without explicitly evaluating them against the codebase.

## Prefer `TypeHint | None` over `Optional[TypeHint]`

Style recommendation (SHOULD): use `TypeHint | None` instead of `Optional
[TypeHint]` for optional type hints. This is consistent with modern Python
syntax for union types and is more concise. Clean up the `Optional[TypeHint]
` usage when you encounter it during refactoring, but no need for a bulk
search-and-replace.

## VCR-005 Follow-up

This is a comment added after 486652d2d943f92a859abeaecde48a6b246e2441 was
committed and VCR-005 was marked complete. We need to ensure that the
profile endpoint only ever returns a link to the actor's inbox and outbox,
never the contents thereof. The line in `agentic-readiness.md` about "`inbox`
and
`outbox` MUST be
`OrderedCollection` objects whose `id` field is a resolvable URL" is
concerning in that it leaves open to misinterpretation that the requirement
might be to return the contents of the collection (which is not what we want).
This clarification should be made in the specs but also enforced with one or
more tests and potentially object validation in the code.

## Resolve ambiguity of BT-*vs OX-* vs ACT-* tasks

1. In the next LEARN or PLAN phase, we need to resolve the priority ambiguity
around BT-*vs OX-* vs ACT-* tasks. Information in plan/PRIORITIES.md takes
precedent over currently labeled priorities in plan/IMPLEMENTATION_PLAN.md.
2. Generalizing from this, we need to capture that PRIORITIES.md takes
   precedence and may change over time relative to what is captured in
   IMPLEMENTATION_PLAN.md. As a corollary to this point, the order of tasks
   in IMPLEMENTATION_PLAN.md reflects groupings of related tasks but does
   not reflect their priority. Tasks should note prerequisites or blockers
   but conflict between task order and stated priorities should be resolved
   in favor of stated priorities. This should be captured in the
   documentation to avoid confusion in the future.

---

### 2026-03-20: Wire-layer methods that should live on core domain objects

**Issue:** During state-machine refactoring analysis, several methods were
found on wire-layer objects (`vultron.wire.*`) that should rightfully belong on
their core domain counterparts.

**Known example:**

- `VulnerabilityCase.set_embargo()` in
  `vultron/wire/as2/vocab/objects/vulnerability_case.py` directly modifies
  `current_status.em_state = EM.ACTIVE`. This is a domain state transition that
  belongs in `vultron.core`, not in the wire layer. The wire layer was the
  original home for these objects before the hexagonal architecture refactor
  separated concerns; methods were left in place as a shortcut.

**Pattern:** The wire-layer class (e.g. `VulnerabilityCase`, `CaseParticipant`)
has a convenience method that mutates protocol state. The equivalent core
domain protocol type (`CaseModel`, `ParticipantModel` in
`vultron/core/models/protocols.py`) either lacks the method or only declares a
stub.

**Recommended sweep:** Audit all methods on wire-layer vocab objects and
determine whether each method represents:

1. Pure wire formatting (stays in wire layer), or
2. Domain state mutation (should move to or be mirrored on a core type)

For type (2), the method should be added to the relevant `Protocol` in
`vultron/core/models/protocols.py` and implemented in the core domain models.
The wire-layer method should then delegate to the core implementation or be
removed.

**Immediate instance to fix:** `VulnerabilityCase.set_embargo()` — tracked as
OPP-03 in `wip_notes/state-machine-findings.md`.

---

### 2026-03-20: Integrating `transitions` machines with Pydantic models

**Context:** Refactoring `SvcProposeEmbargoUseCase` to use `create_em_machine()`
(OPP-01) revealed two non-obvious constraints that apply to any future
`transitions` machine integration in this codebase.

**Lesson 1 — Pydantic models cannot be used directly as `transitions` models.**

`transitions` attaches trigger callables to the model object via `setattr`.
Pydantic v2 models reject `setattr` for unknown field names with:
`ValueError: "ClassName" object has no field "trigger"`.

**Solution:** Use a lightweight plain-Python adapter object:

```python
class _EMAdapter:
    def __init__(self, initial: EM) -> None:
        self.state = initial
```

Seed it from the Pydantic model's current state, pass it to
`machine.add_model()`, trigger the desired transition, then write back the
resulting `.state` to the Pydantic model field. This is the canonical
pattern for all `transitions` + Pydantic integrations in this project.

**Lesson 2 — Always pass `initial=` to `machine.add_model()`.**

`create_em_machine()` (and the other `create_*_machine()` factory functions)
define `initial=EM.NONE` at the machine level. When `add_model()` is called
without an `initial=` argument, the machine resets the adapter's `.state` to
the machine's default initial state — discarding the current state.

**Always call:**

```python
em_machine.add_model(adapter, initial=current_state)
```

**Never call (silently wrong):**

```python
em_machine.add_model(adapter)  # resets .state to machine's initial!
```

**Pattern summary (copy-paste template):**

```python
from transitions import MachineError
from vultron.core.states.em import EM, create_em_machine

class _EMAdapter:
    def __init__(self, initial: EM) -> None:
        self.state = initial

# In the use case:
current_state = case.current_status.em_state
adapter = _EMAdapter(current_state)
em_machine = create_em_machine()
em_machine.add_model(adapter, initial=current_state)
try:
    adapter.<trigger>()   # e.g. adapter.propose(), adapter.terminate()
except MachineError:
    raise VultronConflictError("...")
case.current_status.em_state = EM(adapter.state)
```

Apply the same pattern for `create_rm_machine()` (targeting `rm_state`)
when RM machine integration is implemented.

## wire-layer terminology leaking into core

There are use cases and triggers that use objects that have attribute names
like `object`, `target`, `context`, etc. that are directly mapped from the
AS2 spec. However, since core objects are supposed to be semantically
meaningful within the domain, it would be better if this interface was
clearer about what exactly was being passed in and what the expected types
were. So for example, if an Offer of a report has been received, then the
use case should receive something that talks about a report id rather than
object id. Similarly, if a note is added to a case, the use case should
receive something that mentions a case id rather than a generic target id.
This will help to make the core domain logic clearer for developers and
reduce confusion about the adapter-port interface.

## lack of clean separation at the core to datalayer port and adapter boundaries

We are frequently finding that core domain logic is having to figure out
what kind of object it got back from the datalayer and then do different
things based on that. It seems like it might be better to have a cleaner
separation at the datalayer port where the datalayer returns domain objects
consistently rather than sometimes returning raw dicts or ambiguous document
objects (which are really just a datalayer abstraction rather than a core
abstraction). The following subsections address this issue from different 
angles.

### Core should reliably get domain objects from datalayer, not raw dicts or datalayer-specific records

This will likely require some refactoring of the datalayer
port and its implementation (TinyDB) to ensure that it reliably returns
domain objects so that the core domain logic can rely on that and not have
to do extra work to figure out what it got back. The same should be true in
the outbound direction from core: core should not care about what the
adapter expects, it should be able to say "Store this domain object" and
expect that the port and adapter will handle the details on its behalf. This
improves separation of concerns between core, port, and adapters.

If a mapping layer is needed between core objects and datalayer records, 
then that mapping layer belongs in an adapter not in core. The datalayer 
port should really be about getting and storing domain objects, with 
translation happening in the adapters as needed to convert between core 
domain objects and datalayer records. That said, it may make sense for the 
datalayer adapters to have a tiered structure where a thin adapter unifies 
the translation (like everything is a document or key-value dicts etc. with 
pydantic object definitions) and then storage-specific adapters decide how 
to generically persist those (into TinyDB, MongoDB, SQL, etc. as needed).
The key point is that if core is struggling to identify what it got back 
from the datalayer, then we haven't got the right abstractions in place at 
the port and adapter layers yet.

## Datalayer storage records might need a rethink

Secondarily, this may also mean that we can re-think the datalayer storage
assumptions. The Record and StorableRecord classes might need to be
re-evaluated to determine if they are still the right abstractions for the
hexagonal architecture now that we have a clear delineation between wire,
core, and datalayer. Research into the codebase to understand the problem is
needed before implementing any refactoring. Both the investigation and the
refactoring should be tracked in the implementation plan.

Core should be agnostic to datalayer's storage structure and organization, 
not just the format. Core doesn't need to know if datalayer has separate 
tables per type or just a giant blob of JSON records with a type field, or 
whatever. Datalayer needs to care, but even that might be an 
adapter-specific concern rather than a port-level concern (except insofar as 
the port must provide sufficient abstractions to cover the core's need to do 
CRUD operations, plus find/search/query, usual database stuff.)

### Vocabulary registry entanglement across wire, core, and datalayer

Thirdly, the vocabulary registry was created when wire and core were the same 
thing 
and datalayer was a persistence detail. So there are places where the 
vocabulary registry is being used for lookups for things outside of wire, 
when in fact that is an artifact of the pre-hexagonal architecture. 
`db_record.py` and `rehydration.py` are specific examples of this problem. We
need to tease these apart. The interaction between core and datalayer should 
be in terms of core domain objects without the tight coupling to wire format 
that the vocabulary registry creates. This is not to say that the datalayer 
should be ignorant of data types or that the vocabulary registry should be 
abandoned, but rather that the datalayer should have its own way to 
recognize what kinds of objects it is handling and the core should be able 
to work with the datalayer just as robustly (with typed objects) even if the 
entire wire layer were removed.