## Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate
insights, issues, and learnings during the implementation process.

Append new items below any existing ones, marking them with the date and a
header.

### 2026-04-29 BUG-471.6 — BTBridge.get_failure_reason vs result.feedback_message

When a `py_trees` Sequence fails because a child fails, the root Sequence
node's `feedback_message` is always `""`. Use `BTBridge.get_failure_reason(tree)`
(depth-first walk to the first failing leaf) to get a meaningful message.
Apply this pattern consistently wherever `result.feedback_message` is logged
after a BT failure — not just for EngageCaseBT.

### 2026-04-30 P472-BUG386 — Closed via sender-side inline-object fix

TASK-BUG-386 (deferred handling for unresolvable `Accept.object_` URIs) was
resolved by commit `62cdc48e` which made the parser embed the full inline typed
object in every `Accept`/`Reject` activity before it leaves the outbox. The
receiver-side dead-letter path (`UnresolvableObjectUseCase`) remains in place
for non-compliant or legacy senders; it was not changed. If a future need arises
to auto-retry deferred activities, implement a `DeferredActivityRecord` model
and a dispatcher post-hook (see issue #386 description for design sketch).

### 2026-04-30 TASK-DL-REHYDRATE — Do not name a method `list` in a Python class

Defining `def list(self, ...)` on a class causes Python to shadow the built-in
`list` type in the class body scope. Any annotation `list[str]` that appears
AFTER the `def list(...)` definition is evaluated at class-body execution time
with `list` resolving to the method (a function), producing `TypeError:
'function' object is not subscriptable`. `# type: ignore[valid-type]` only
suppresses mypy — it does NOT prevent the runtime error. Fix: rename the method
to avoid collision (e.g., `list_objects`). This affects any method that shares
a name with a Python built-in type (`dict`, `set`, `tuple`, etc.).

### 2026-04-30 BUG-26043001 — append-history: always use a Pydantic model for structured file formats

When a CLI tool writes structured files (frontmatter, YAML, JSON), define a
Pydantic model for the structure upfront. Without it, required-field validation
is either missing or duplicated across callers. The fallback-to-default pattern
(`metadata.get("source", "")`) makes it impossible to distinguish "absent field"
from "empty field". A Pydantic model with `ValidationError` on missing fields is
the single source of truth and forces callers to handle the error path explicitly.

### 2026-04-30 AF.8-10 — Factory return types are wire types, not domain models

After migrating call sites in `vocab/examples/` and `demo/` from internal
activity classes to factory functions, 91 mypy/pyright type errors emerged.
Root cause: factory functions return base AS2 wire types (`as_Offer`,
`as_Create`, etc.) from `vultron.wire.as2.vocab.base.*`, but the migrated
code had `-> VultronActivity` return type annotations. `VultronActivity` is
a domain model (`vultron/core/models/`); it is NOT a supertype of `as_Offer`.

Key patterns and fixes:

- `vocab/examples/*.py`: change `-> VultronActivity` to the specific AS2 base
  type that the factory returns (e.g., `-> as_Offer`, `-> as_Accept`). Chain
  calls between example functions (e.g., `submit_report()` passed to
  `rm_validate_report_activity()`) require the specific AS2 type, not
  `as_Activity`, since factory parameters are typed precisely.
- `demo/utils.py#get_offer_from_datalayer`: was wrapping `as_Offer(**data)`
  in `VultronActivity.model_validate(...)`. Remove the wrapping; return the
  `as_Offer` directly. This fixes all exchange demo files that passed the
  offer to `rm_validate_report_activity(offer: as_Offer)`.
- Demo scenario files: trigger endpoint responses should be parsed as
  `as_Activity.model_validate(...)` (or a specific subtype), not
  `VultronActivity.model_validate(...)`.
- When the parsed activity's `.object_` field is needed, parse it as the
  specific transitive type (e.g., `as_Create`, `as_Invite`) since
  `as_Activity` (base class) doesn't have `object_`; only transitive subtypes do.
- Pyright `[attr-defined]` errors on subtype-only attributes (e.g.,
  `ChoosePreferredEmbargoActivity.one_of` not on `as_Question`) are fixed
  with a runtime `isinstance` assertion for type narrowing, not
  `# type: ignore`.

### 2026-05-04 BTND5.4 — Legacy bt/ isolation pattern for shared enums

When a `core/` enum is replaced by a new version (e.g. `CVDRoles Flag` →
`CVDRole StrEnum`), the legacy type used only by `bt/` should be moved to
`vultron/bt/roles/enums.py` (or similar bt/-local module) rather than kept
in `core/`. This keeps `core/` clean and signals clearly that the legacy
type is an implementation detail of the simulator layer.

Key decisions: `NO_ROLE` is removed from the StrEnum (empty list = no roles).
Serialization uses `.value` (lowercase), not `.name`. The centralized
`serialize_roles` / `validate_roles` helpers in `roles.py` are the single
source of truth for all models — don't duplicate per-class serializers.

### 2026-05-04 TASK-CFG — pydantic-settings 2.x source priority order

In pydantic-settings 2.14, `settings_customise_sources` returns a tuple where
the **first** source has the **highest** priority (it wins in the deep-merge
performed by `_settings_build_values`). The `notes/configuration.md` example
incorrectly commented "last = highest". The correct order to get env vars >
YAML is `(env_settings, YamlConfigSource(settings_cls))`.

### 2026-05-04 TASK-CFG — Config fixture teardown: clear cache, don't reload

When a test fixture calls `reload_config()` in teardown (after `yield`), it
fires BEFORE pytest's `monkeypatch` reverts env var changes. This locks in the
test's env state rather than the session-level defaults from `conftest.py`.
Pattern: set `_config_cache = None` directly in teardown, and let the next
test's first `get_config()` call reload with the correctly-restored env vars.

### 2026-05-04 TASK-ARCHVIO — Sync use cases violate ARCH-01-001 more broadly than `from_core()` alone

#### Problem scope is wider than originally described

TASK-ARCHVIO was scoped to "fix `from_core()` calls in core use cases." But
the real ARCH-01-001 violation in `received/sync.py` and `triggers/sync.py`
goes deeper: these files import **both** wire vocab types (`CaseLogEntry`,
`WireCaseLogEntry` from `vultron.wire.as2.vocab.objects.case_log_entry`) and
factory functions (`announce_log_entry_activity`,
`reject_log_entry_activity` from `vultron.wire.as2.factories`). Fixing only
`from_core()` while leaving wire factory imports in core still violates
ARCH-01-001.

#### Incremental fix: `SyncActivityPort` (driven port)

The agreed incremental fix introduces a narrow driven port
(`SyncActivityPort`) with two fire-and-forget methods:

- `send_reject_log_entry(entry, tail_hash, actor_id, to)` — converts
  domain `VultronCaseLogEntry` → wire `CaseLogEntry`, builds a
  `Reject(CaseLogEntry)` activity via factory, persists it, queues to outbox.
- `send_announce_log_entry(entry, actor_id, to)` — same pattern for
  `Announce(CaseLogEntry)`.

The adapter (`SyncActivityAdapter`) accepts `CaseOutboxPersistence` at
construction and owns the entire domain→wire→persist→outbox pipeline. Core
use cases call the port methods with domain objects and never touch wire
types. This is the "baton-pass" pattern: core hands off domain data and the
adapter handles the rest unidirectionally.

Port is injected as constructor parameter (for use-case classes) and function
parameter (for trigger helper functions). The dispatcher passes it via
`**kwargs` so only sync use cases receive it.

#### Correct end-state: BT-based sync flow (future task)

The incremental port fix is a stepping stone. The correct long-term
architecture (per project owner) is:

1. `AnnounceLogEntryReceivedUseCase` should pass the received log entry to
   a **behavior tree** (via `BTBridge`), not directly decide accept/reject.
2. The BT contains the decision logic (hash-chain validation, accept vs.
   reject branching).
3. BT leaf nodes use driven ports (like `SyncActivityPort`) for outbound
   actions.
4. Same pattern for `RejectLogEntryReceivedUseCase`: use case passes event
   to a BT, BT decides what to replay, BT nodes use the port.

This matches how other protocol flows (report, case, embargo) already work
through BTs. The sync flow is currently the exception — its logic lives
entirely in procedural use-case code.

**This BT integration is a separate task**, not part of TASK-ARCHVIO. The
port created in the incremental fix will be reused by BT nodes when the
sync BT is built.

#### Additional architectural observations

**Case-actor vs. non-case-actor distinction for log entries**: There is a
meaningful difference in how log entries should be handled depending on
whether the receiving actor is the case-actor (who owns the log) or a
non-case-actor (who is replicating it). Non-case-actors treat received
`Announce(CaseLogEntry)` as events that update their local case replica.
Case-actors receiving their own log entries (round-tripped through
outbox→inbox) can use the receipt as delivery confirmation. This distinction
is captured in IDEAS.md as a separate design question.

#### TASK-ARCHVIO subtask updates

The original plan subtasks remain valid for the incremental fix:

- ARCHVIO.1: Define `SyncActivityPort` in `vultron/core/ports/`
- ARCHVIO.2: Implement `SyncActivityAdapter` in
  `vultron/adapters/driven/sync_activity_adapter.py`
- ARCHVIO.3: Replace ALL wire imports (not just `from_core()`) in
  `received/sync.py` and `triggers/sync.py` with port calls
- ARCHVIO.4: Update tests; verify no core module imports wire types in
  these files

**New follow-up task needed**: Build sync behavior tree to replace
procedural logic in sync use cases. Depends on ARCHVIO completion (port
exists) and BT-07 spec group (if it exists, otherwise needs spec work).

#### Wire imports remaining in other core files

ARCHVIO only addresses `sync.py` files. Many other core files still import
from wire layer (behaviors/case/nodes.py, behaviors/report/nodes.py,
triggers/embargo.py, triggers/case.py, triggers/actor.py, etc.). These are
separate violations that should be tracked independently — likely each needs
its own driven port or the existing `ActivityEmitter` port needs to be
expanded. A comprehensive audit of all ARCH-01-001 violations in `core/`
would be valuable as a follow-up task.
