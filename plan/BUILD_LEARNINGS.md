## Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate
insights, issues, and learnings during the implementation process.

### 2026-06-18 PROTOCOL-FIELD-SYNC-792 — CaseModel Protocol fields must stay in sync with concrete type

When removing a field from a concrete domain model (e.g., `VulnerabilityCase.events`),
also remove the matching declaration from any structural `Protocol` that lists it
(e.g., `CaseModel.events` in `protocols.py`). Static type checkers (mypy/pyright)
check conformance in the concrete→Protocol direction, so a Protocol member that no
longer exists on the concrete class will not produce a lint error — but it will
silently break future callers who accept `CaseModel` and access the removed attribute.
The pre-PR code review caught this gap; the fix was one-line deletion in `protocols.py`.

### 2026-06-18 IS-CASE-MODEL-DISCRIMINATOR-888 — is_case_model() must not use removed methods as discriminators

`is_case_model()` in `vultron/core/models/protocols.py` used
`hasattr(obj, "record_event")` as one of its structural checks. Removing
`record_event()` from the wire-layer `VulnerabilityCase` silently broke
this type guard: `find_case_by_report_id()` returned `None` because the
stored wire case no longer matched, causing 440 test failures.

Rule: discriminators in `is_case_model()` (and similar type guards) MUST
use fields/methods declared on the `CaseModel` Protocol itself. The fix
replaced `hasattr(obj, "record_event")` with `hasattr(obj, "case_statuses")`,
which is a declared Protocol member present on both wire and core
`VulnerabilityCase`. Always audit type-guard discriminators when removing
a method from a class matched by one of these guards.

Append new items below any existing ones, marking them with the date and a
header.

### 2026-06-11 OUTBOX-873-TEST-COVERAGE — make acceptance criteria explicit in one file

Issue #873 found that most delivery-path coverage already existed but was split
across sections/files. Adding explicit tests in
`test/adapters/driving/fastapi/test_outbox.py` for direct `to` extraction and
malformed bare-string `object_` integrity checks keeps OX-08/OX-09 validation
discoverable in the canonical outbox test module and reduces ambiguity during
future outbox refactors.

### 2026-06-11 NODES-SPLIT — VulnerabilityCase.case_statuses has a default initial CaseStatus

`VulnerabilityCase.case_statuses` is auto-populated with one `CaseStatus`
(em_state=EM.NONE, UUID id) when the object is created. Tests that check
`len(case.case_statuses) == 1` after a single append will fail with `2`.
Use `initial_count + 1` pattern or check only SUCCESS status.

### 2026-06-11 OUTBOX-874-HELPER-EXTRACTION — split protocol invariants from flow wiring

The outbox handler became easier to reason about after extracting nested
protocol checks into explicit helper functions (`_coerce_reference_value`,
`_prepare_activity_object_for_delivery`, `_recover_typed_inline_object_from_dict`,
etc.). Keeping the main delivery function focused on sequence-level orchestration
reduces churn risk when adding future outbox requirements while preserving
existing OX/MV invariants.

### 2026-06-11 SYNC — Isolated two-app replication harness for CaseLogEntry

For SYNC happy-path replication integration coverage (#901), the most stable
test seam is two isolated FastAPI apps created with `create_isolated_actor_app`
plus a shared `_TestASGIRouter` wired as each app's emitter fallback and as the
module-level default emitter. This setup exercises outbox -> ASGI delivery ->
inbox processing with distinct actor-scoped DataLayers and avoids real HTTP
retry delays.

### 2026-06-11 SYNC-902-MISMATCH-TEST-SEAM — mismatch assertions need dispatch-level injection

For predecessor-mismatch coverage (#902), injecting `Announce(CaseLogEntry)`
through `post_actor_inbox` can mask mismatch behavior because nested object
persistence can make `CheckLogEntryAlreadyStored` short-circuit before hash
validation. A stable test seam is `handle_inbox_item(...)` with a typed
activity object, then normal outbox-driven replay from the CaseActor.

### 2026-06-11 NODES-SPLIT-883 — mirror flat-to-subpackage splits in tests

When converting a behavior area from `nodes.py` to `nodes/`, preserve
`from ...nodes import ...` import paths with an explicit `nodes/__init__.py`
re-export list, and move node-level tests into `test/.../nodes/` with
per-submodule files. Keep tree composition tests in the parent workflow test
module so node behavior and tree wiring remain independently reviewable.

### 2026-06-12 CASE-LOG-925-RATCHET — guard hash-chain fields before comparing

When implementing the local hash-chain invariant for JSONL case-log replicas,
assert that `entryHash` and `prevLogHash` fields are non-empty before
comparing them. Missing fields produce `"" == ""` false positives that mask
serializer or schema-migration bugs. Add an explicit presence assertion
before every chain comparison.

### 2026-06-11 OX-10-004-STUB-GUARD — keep stub adapters under explicit test

`ProdHttpDeliveryAdapter` is intentionally unimplemented and must fail fast
with a spec-linked `NotImplementedError`. A dedicated adapter-level unit test
prevents future placeholder edits from silently downgrading the fail-fast
signal into a no-op module.

### 2026-06-12 RENAME-934 — pytest mark registration must mirror class/file renames

When renaming a pytest mark (e.g., `case_log_invariants` → `case_ledger_invariants`),
update **both** `pyproject.toml` markers AND any `.github/workflows/` YAML files that
reference the mark by name. A renamed mark in test files without a corresponding
workflow update causes `pytest` to select 0 tests and exit with code 5 (no tests
collected), failing CI even though the rename itself is correct.

### 2026-06-12 USE-CASE-SPLIT-881 — flat-to-subpackage test migration pattern

When migrating flat test files into per-submodule subdirectories, the existing
test classes map cleanly onto the semantic clusters already established by the
source split. Removing the old flat files and creating new per-submodule files
(rather than leaving both) avoids duplicate test collection and keeps the
layout strictly mirrored. The parent `conftest.py` fixtures are automatically
inherited via pytest's upward conftest search, so only the vocabulary
registration side-effect import needs copying into each new subdirectory
conftest.

### 2026-06-15 LEDGER-LOGGING-949 — PersistLogEntryNode tests require log_entry in blackboard

When testing `PersistLogEntryNode` logging via `bridge.execute_with_setup()`,
pass the `VultronCaseLedgerEntry` as `log_entry=entry` in kwargs — the bridge
writes it to the blackboard before executing the node. The conftest `_make_entry()`
helper builds a ready-to-use entry from a `HashChainLedgerRecord`. Use
`caplog.at_level(logging.INFO, logger="vultron.core.behaviors.sync.nodes.chain")`
to scope capture to just the chain node logger; without scoping, other node
loggers at DEBUG can fill caplog with unrelated records.

### 2026-06-15 DEMO-CI-DIAGNOSTICS-951 — inbox logger is uvicorn.error, not module path

When documenting or grepping container logs for the inbox receipt layer
(Layer 2 of the 3-layer model), the logger is `uvicorn.error` — not the
Python module path `vultron.adapters.driving.fastapi.routers.actors`.
The actors router explicitly overrides the module-default logger with
`logging.getLogger("uvicorn.error")`. Similarly, `PersistLogEntryNode`
uses a class-qualified logger name:
`vultron.core.behaviors.sync.nodes.chain.PersistLogEntryNode` (not the
bare module path). Always verify logger names from source before writing
diagnostic docs or log-filter commands.

### 2026-06-15 TRIGGER-927-CASEACTOR-ROUTING — report trigger fallback must fail fast on missing CaseActor

Switching sender-side case-scoped report trigger routing from
`case_addressees()` to CaseActor-only routing exposed hidden fixtures and
legacy trigger paths that emitted `to=None`. Once case-scoped routing is
CaseActor-only, emit nodes must fail fast before queueing when no routable
CaseActor recipient exists; otherwise outbox enforcement raises
`VultronOutboxToFieldMissingError` later and masks the true sender-side
routing defect.

### 2026-06-16 INBOX-972-SPLIT — monkeypatch compatibility requires re-exporting moved names

When splitting a module that is used as `import module as m` in tests with
`monkeypatch.setattr(m, "name", ...)`, moved names must be re-imported into
the original module's namespace (not just defined in the new submodule). The
re-import makes the name patchable via `m.*` and ensures internal call sites
in the original module resolve the patched value from their own module globals.
Use `# noqa: F401` on re-export lines to suppress unused-import lint warnings.

### 2026-06-16 ACTORS-ROUTER-SPLIT-970 — re-export get_shared_dl when converting a router module to a subpackage

When a test file does `app.dependency_overrides[actors_router.get_shared_dl]`,
it accesses `get_shared_dl` as an attribute of the module. Converting
`actors.py` to an `actors/` package breaks this unless `get_shared_dl` is
explicitly re-exported in `actors/__init__.py`. Always scan for
`module.dependency_object` patterns in tests before finalizing subpackage
`__init__.py` exports.

### 2026-06-15 BTND07-913-PARTIAL-WRITE — note trigger tree partial-write on send failure

`add_note_to_case_trigger_bt` uses a `memory=False` Sequence. When
`SenderSideBT` (third child) fails (e.g., no CASE_MANAGER), the first two
steps (`CreateNoteNode`, `AttachNoteFromResultNode`) have already succeeded
and committed local state. The note IS attached to the case locally even
though the overall tree returns FAILURE. Tests should assert on this partial-
write behavior explicitly so readers do not assume FAILURE → no writes.

### 2026-06-16 CATCHUP-791 — empty ledger is trivially fresh for catch-up gate

When implementing the SYNC-10 catch-up gate, an actor with no local ledger
entries for a case is treated as trivially fresh (acknowledged prefix is the
empty prefix, which is contiguous). This aligns with SYNC-10-005: the gate
MUST NOT require the actor's tip to equal the CaseActor's tip. Test fixtures
for the gate can safely start with a clean DataLayer and expect SUCCESS.

### 2026-06-16 ABC-HIERARCHY-TEMPLATE — transient instance attributes require care in abstract template methods

When a template method sets transient per-call attributes (e.g.,
`self._captured`, `self._actor_id`, `self._factory`) in `execute()` before
calling abstract hooks, pyright does not always infer they are set at the
call sites inside the abstract methods. Initialising them at the top of
`execute()` (rather than in `__init__`) keeps them visible to pyright and
avoids "possibly unbound" errors without introducing unnecessary sentinel
values into `__init__`. Use `cast()` in `_prepare()` to restore specific
request type narrowing lost by widening to `object` in the base `__init__`.

### 2026-06-18 AUTOCLOSE-1030 — AutoCloseBranchNode must be CASE_MANAGER-only; use CheckIsCaseManagerNode role guard

`AutoCloseBranchNode` fired in every actor context that processed an
`Add(ParticipantStatus)` broadcast, because received-side use cases run the
BT with `actor_id=sender` (the identity-spoofing pattern). On vendor-1, the
BT sometimes ran with `actor_id=finder-actor` — a phantom fire that queued
the Leave into a never-drained outbox slot. A module-level per-case
idempotency set made things worse: the phantom claimed the slot and blocked
the real fire, producing zero canonical `close_case` entries.

Fix: wrap `AutoCloseBranchNode` in the standard role-guard composite at tree
composition time (in `add_participant_status_tree.py`), using the existing
`CheckIsCaseManagerNode`:

```python
Selector("AutoCloseIfCaseManager", children=[
    Sequence("CaseManagerAutoClose", children=[
        CheckIsCaseManagerNode(case_id=case_id),
        AutoCloseBranchNode(case_id=case_id),
    ]),
    Success("AutoCloseSkippedNotCaseManager"),
])
```

Keep the module-level idempotency set to prevent duplicate fires when
multiple qualifying broadcasts arrive in the same process. The same
`CheckIsCaseManagerNode` pattern is used in
`create_guarded_commit_case_ledger_entry_tree` — reach for it any time a
BT step is CASE_MANAGER-only.

### 2026-06-18 DEMO-DEVLOG-RACE — wait for replica before dumping devlogs

Demo phases that dump JSONL devlogs (e.g., `_phase_dump_case_ledgers`) will
miss recently committed canonical entries if they run before the async
`Announce(CaseLedgerEntry)` fan-out is processed by the replica. In the
failing run the finder devlog was written 580 ms *before* finder received
and stored the final `close_case` entry.

Pattern: after any phase that commits a new canonical ledger entry, query
vendor's current tail hash and call `wait_for_finder_log_entry` before the
dump:

```python
vendor_entries = _get_log_entries_for_case(vendor_client, case.id_)
if vendor_entries:
    tail = max(vendor_entries, key=lambda e: e["log_index"])
    wait_for_finder_log_entry(finder_client, case.id_, tail["entry_hash"])
```

This is the same poll-until-hash pattern used in `_phase_sync_verification`.
Apply it after every phase that introduces a new tail before a devlog dump.

### 2026-06-18 MODULE-IDEM-SET — module-level idempotency sets are per-process, not per-container

A module-level `set[str]` used to track "already fired" in a BT node is
isolated to the Python process. In the Docker demo, vendor-1 and finder-1
are separate processes with separate sets. A phantom fire on finder-1
(with the wrong `actor_id`) adds the `case_id` to finder-1's set — it does
NOT affect vendor-1's set. This means the REAL fire on vendor-1 can still
proceed. Conversely, two phantom fires in the SAME process on vendor-1
(one with `actor_id=finder-actor`, then one with `actor_id=case-actor`) can
race: the phantom claims the set slot first and blocks the real fire.
Always pair a module-level idempotency set with a role guard so the set is
only ever claimed by the correct actor.

### 2026-06-16 BASE-HOOK-1005 — SvcBTTriggerBase needs _extra_execute_kwargs() for trees that read case_id from blackboard

`UpdateActorOutbox` reads `case_id` from the blackboard (registered via
`execute_with_setup` kwargs). The original `_execute_add_object_trigger_bt`
standalone function passed `case_id=case_id` explicitly. When converting to
`SvcBTTriggerBase`, the base `execute()` only passes `actor_id` to
`execute_with_setup`. Fix: add a `_extra_execute_kwargs() -> dict[str, Any]`
hook (default `{}`) to `SvcBTTriggerBase`; classes whose BTs need extra
blackboard keys override it. The return type must be `dict[str, Any]` (not
`dict[str, object]`) to satisfy mypy when the dict is spread into
`execute_with_setup`'s `**context_data: Any` parameter.

### 2026-06-18 REMOVE-EMBARGO-1033 — single-BT pattern requires receiving_actor_id in all callers

Switching `RemoveEmbargoEventFromCaseReceivedUseCase` from two `execute_with_setup`
calls to a single call with `actor_id=receiving_actor_id` exposed that several
existing tests called `make_payload(activity)` without specifying
`receiving_actor_id`. With the new guard, a `None` `receiving_actor_id` returns
early and the BT never runs. Pattern: any test for a received-side use case that
exercises BT operations MUST pass a `receiving_actor_id` in `make_payload`. Tests
that don't need the guarded commit to fire can use the sender actor as the
`receiving_actor_id` — `CheckIsCaseManagerNode` will reject it silently.

### 2026-06-18 BROADCAST-834-STALE-BLACKBOARD — clear broadcast_activity_id sentinel on no-op path

`py_trees.blackboard.Blackboard.storage` is process-global and
`execute_with_setup` only cleans `datalayer` and `trigger_activity_factory`
keys on exit — it does NOT clean domain-specific keys like `broadcast_*`.
When `CreateBroadcastActivityNode` takes the no-op path (empty recipient
list), it must write `None` to `broadcast_activity_id` to clear any stale
value from a prior execution.  `BroadcastQueueToOutboxNode` must treat both
`KeyError` (first-ever run) and `None` (cleared by prior no-op) as equivalent
no-op sentinels and skip `record_outbox_item`.  Always add regression tests
that intentionally do NOT clear the blackboard between two `execute_with_setup`
calls to catch this class of bug.
