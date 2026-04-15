# Bugs to fix

Items in this file supersede IMPLEMENTATION_PLAN.md.

Use format `BUG-YYMMDDXX` for bug IDs, where `YYMMDD` is the date the bug
was identified and `XX` is a sequential number for that day. For example,  
the first bug identified on March 26, 2026 would be `BUG-2026032601`.
Include a brief description in the title, and provide detailed reproduction
steps, root cause analysis, and resolution steps in the body.

---

## BUG-26041501 Two-actor demo fails when Finder receives Announce with bad type from Vendor

**Status: FIXED** — See `plan/IMPLEMENTATION_HISTORY.md` for resolution
summary.

### Summary

The two-actor demo fails when the Vendor (CaseActor) fans out a
`Announce(CaseLogEntry)` to the Finder. The Finder receives the activity with
`object: "urn:uuid:.../log/0"` (a plain URI string), cannot resolve it to a
typed `CaseLogEntry`, and crashes with
`AttributeError: 'VultronObject' object has no attribute 'case_id'`.

### Root Cause Chain (fully traced — 6 failure points)

**1. Dehydration collapses the object to an ID string.**

`_fan_out_log_entry` (`vultron/core/use_cases/triggers/sync.py`, line ~98)
creates `AnnounceLogEntryActivity(object_=entry)` with a full
`VultronCaseLogEntry` and calls `dl.save(announce)`.  `dl.save` →
`Record.from_obj` → `_dehydrate_data` (`vultron/adapters/driven/db_record.py`)
collapses `object_` (in `_AS_OBJECT_REF_FIELDS`) to the ID string
`"urn:uuid:.../log/0"`.  So the stored activity has only a URI for `object_`.

**2. Outbox handler does NOT expand Announce objects before sending.**

`handle_outbox_item` (`vultron/adapters/driving/fastapi/outbox_handler.py`,
lines 151–162) expands Create activities from ID strings to full inline
objects, but the expansion only runs for `activity_type == "Create"`.
Announce activities are sent as-is — with `"object": "urn:uuid:.../log/0"`.

**3. Rehydration on the Finder fails because `VultronCaseLogEntry` is not
`as_Object`.**

`rehydrate()` (`vultron/wire/as2/rehydration.py`, line 76) does:

```python
if not isinstance(resolved, as_Object): raise ValueError(...)
```

`VultronCaseLogEntry` extends core `VultronObject → VultronBase → BaseModel`
(NOT wire `as_Object`), so this check fails and the string is kept as-is.

**4. Even if the inline dict were sent, `parse_activity` can't reconstruct it.**

`parse_activity` (`vultron/wire/as2/parser.py`) looks up `"Announce"` in
`VOCABULARY` → returns generic `as_Announce`.  `as_Announce.object_` is typed
`as_Object | as_Link | str | None`.  Pydantic parses an inline CaseLogEntry
dict as a bare `as_Object`, which uses `extra="ignore"` — all CaseLogEntry-
specific fields (`case_id`, `log_index`, `entry_hash`, etc.) are silently
dropped.

**5. `extract_intent` gets a string or bare `as_Object`, not a `CaseLogEntry`.**

The `CASE_LOG_ENTRY` branch in `extract_intent` (`extractor.py`, lines
536–567) works correctly when `obj.type_ == "CaseLogEntry"` and the object
has the expected fields.  But with a string or bare `as_Object`, `_obj_type`
is `""` and the branch never fires.  `event.object_` is set to a minimal
`VultronObject(id_=..., type_=None)`.

**6. Use case crashes on the minimal object.**

`AnnounceLogEntryReceivedUseCase.execute()` calls `entry.case_id` on the
minimal `VultronObject` → `AttributeError`.

### Key Architectural Issue: Missing Wire-Layer `CaseLogEntry` Class

**Every other Vultron domain object has a proper wire-layer class** in
`vultron/wire/as2/vocab/objects/` that inherits from wire `VultronObject`
(→ `as_Object`): `CaseStatus`, `ParticipantStatus`, `VulnerabilityReport`,
`VulnerabilityCase`, `EmbargoEvent`, `CaseParticipant`, etc.

`VultronCaseLogEntry` is the **only** Vultron object that does NOT have a
wire-layer counterpart. `vultron/wire/as2/vocab/objects/case_log_entry.py`
only does a manual `VOCABULARY["CaseLogEntry"] = VultronCaseLogEntry`
re-export with no proper wire class. This causes:

- `rehydrate` rejects it (`isinstance(resolved, as_Object)` fails)
- `AnnounceLogEntryActivity.object_` has `# type: ignore[assignment]` because
  `VultronCaseLogEntry` is not `as_Object`
- `as_Announce.model_validate(body)` drops all CaseLogEntry fields

**The fix is to create:**

```python
# vultron/wire/as2/vocab/objects/case_log_entry.py
class CaseLogEntry(VultronObject):
    type_: Literal["CaseLogEntry"] = ...
    case_id: str
    log_index: int
    disposition: str
    log_object_id: str   # alias: logObjectId
    event_type: str      # alias: eventType
    payload_snapshot: dict  # alias: payloadSnapshot
    prev_log_hash: str   # alias: prevLogHash
    entry_hash: str      # alias: entryHash
    received_at: datetime  # alias: receivedAt
    reason_code: str | None  # alias: reasonCode
    reason_detail: str | None  # alias: reasonDetail
    term: int | None = None
```

Because it inherits from `VultronObject → as_Object`, `__init_subclass__`
auto-registers it in `VOCABULARY["CaseLogEntry"]`, `rehydrate` accepts it,
and `AnnounceLogEntryActivity.object_` can be typed without `# type: ignore`.
**The `@model_validator` that auto-computes `id_` should NOT be copied to the
wire class** — the wire class trusts the incoming `id` value from the network.

### Critical Constraint: Actors Do NOT Share DataLayers

**This is the core protocol assumption that the rehydration approach violates.**

In the current architecture, `rehydrate()` tries to resolve a URI string by
calling `dl.read(uri)` on the **receiving actor's** DataLayer. This works
locally (same-process tests) because both "actors" share a database.  In the
real federated demo, however:

- The Finder's DataLayer does NOT contain the Vendor's `CaseLogEntry` records.
- The Finder's DataLayer does NOT contain the Vendor's internal activities.
- Actors know only their **own** actor record, their own emitted activities,
  and objects that have been **explicitly sent to them** via inbox delivery.
- Nothing from the Vendor's internal state is accessible to the Finder except
  what arrives in the inbox payload itself.

This means **any use of `rehydrate()` for cross-actor objects is
architecturally unsound unless the full inline object is embedded in the
activity at send time.**  The fix for `Announce(CaseLogEntry)` must ensure
the Vendor embeds the full `CaseLogEntry` JSON inline in the outbound
activity, not just a URI reference. The same principle applies to any future
federated message type.

### Required Fixes

1. **Create wire `CaseLogEntry(VultronObject)`** in
   `vultron/wire/as2/vocab/objects/case_log_entry.py` with all domain fields
   and proper camelCase aliases (via `alias_generator=to_camel` inherited from
   `as_Base`). Auto-registration via `__init_subclass__`. No `@model_validator`
   for ID auto-computation.

2. **Update `AnnounceLogEntryActivity.object_`** and
   `RejectLogEntryActivity.object_` in
   `vultron/wire/as2/vocab/activities/sync.py` to use wire `CaseLogEntry`
   instead of core `VultronCaseLogEntry`. Remove `# type: ignore[assignment]`.

3. **Convert in `_fan_out_log_entry`** (`vultron/core/use_cases/triggers/sync.py`)
   from core `VultronCaseLogEntry` to wire `CaseLogEntry` before constructing
   `AnnounceLogEntryActivity`, so `dl.save` serializes all fields correctly
   (or alternatively, ensure outbox expansion happens before send).

4. **Fix outbox expansion** in `outbox_handler.py` (lines 151–162): extend the
   Create expansion block to also expand Announce activities when `object_` is
   a string, so the full inline object is sent over the wire regardless of
   dehydration. This is the guard against the federated isolation constraint.

5. **Graceful error handling** in `AnnounceLogEntryReceivedUseCase.execute()`
   and/or `AnnounceLogEntryReceivedEvent.log_entry`: add an `isinstance` guard
   so a malformed/missing object logs a clear error and returns rather than
   crashing.

6. **Add spec requirement** (in `specs/sync.md` or similar): `Announce(CaseLogEntry)`
   MUST carry the full inline `CaseLogEntry` object, never a URI-only reference,
   because receiving actors cannot resolve cross-actor URIs in their local
   DataLayer.

7. **Update existing tests** in `test/core/use_cases/received/test_sync.py`
   (the `_make_event` helper currently passes core `VultronCaseLogEntry`
   directly with `# type: ignore`, bypassing the serialization round-trip that
   exposes the bug). Tests should use wire `CaseLogEntry` and/or cover the
   full serialization → HTTP → deserialization path.

### Notes on `extractor.py`

The `CASE_LOG_ENTRY` branch in `extract_intent` (lines 536–567) already uses
`getattr(obj, "case_id", None)` etc. and works correctly once `obj` is a
proper wire `CaseLogEntry`. No changes needed there — fixing the wire class
and outbox expansion is sufficient to make this branch work.

### Conversion Round-Trip

`WireCaseLogEntry.model_validate(core_entry.model_dump(by_alias=True))` should
work because both classes produce the same camelCase aliases for all fields.
This needs a test to confirm.

The log message `Dispatching activity of type 'None'` is a secondary symptom:
the stored activity record has `type_=None` in the `name` field because
`AnnounceLogEntryActivity` is not registered under a unique type in VOCABULARY
(it's still serialized as `type="Announce"`). This is not the root cause but
should be noted.

Full log follows.

```text
demo-runner-1  | 2026-04-15 15:39:10,266 INFO     vultron.demo.two_actor_demo: Log entry committed for case 'urn:uuid:a344d2d8-3747-4128-b80c-b278f9ce5e9d': hash=6cde3f6c9cf03410, index=0
demo-runner-1  | 2026-04-15 15:39:10,266 INFO     vultron.demo.utils: 🟢 Committing case log entry on Vendor (CaseActor)
demo-runner-1  | 2026-04-15 15:39:10,266 INFO     vultron.demo.utils: 🚥 Waiting for Finder to receive replicated log entry
vendor-1       | INFO:     Processing outbox for actor 515663dc-3ab9-4aa9-a0bc-6a97e8b710c6
finder-1       | INFO:     Parsing activity from request body (type='Announce'):
finder-1       | {
finder-1       |   "id": "urn:uuid:6035c298-dec3-4881-ba21-f12ed8b74b9f",
finder-1       |   "type": "Announce",
finder-1       |   "name": "http://vendor:7999/api/v2/actors/515663dc-3ab9-4aa9-a0bc-6a97e8b710c6 Announce None",
finder-1       |   "published": "2026-04-15T15:39:10Z",
finder-1       |   "updated": "2026-04-15T15:39:10Z",
finder-1       |   "to": [
finder-1       |     "http://finder:7999/api/v2/actors/1e28e488-e7d1-475f-9b42-e1f20be1b6cf"
finder-1       |   ],
finder-1       |   "actor": "http://vendor:7999/api/v2/actors/515663dc-3ab9-4aa9-a0bc-6a97e8b710c6",
finder-1       |   "object": "urn:uuid:a344d2d8-3747-4128-b80c-b278f9ce5e9d/log/0"
finder-1       | }
finder-1       | INFO:     Parsing activity from body (type='Announce')
vendor-1       | INFO:     HTTP Request: POST http://finder:7999/api/v2/actors/1e28e488-e7d1-475f-9b42-e1f20be1b6cf/inbox/ "HTTP/1.1 202 Accepted"
finder-1       | INFO:     Processing inbox for actor http://finder:7999/api/v2/actors/1e28e488-e7d1-475f-9b42-e1f20be1b6cf
vendor-1       | INFO:     Delivered activity urn:uuid:6035c298-dec3-4881-ba21-f12ed8b74b9f to http://finder:7999/api/v2/actors/1e28e488-e7d1-475f-9b42-e1f20be1b6cf/inbox/ (HTTP 202)
vendor-1       | INFO:     Delivered Announce activity 'urn:uuid:6035c298-dec3-4881-ba21-f12ed8b74b9f' (object: urn:uuid:a344d2d8-3747-4128-b80c-b278f9ce5e9d/log/0) to 1 recipient(s) [http://finder:7999/api/v2/actors/1e28e488-e7d1-475f-9b42-e1f20be1b6cf] for actor '515663dc-3ab9-4aa9-a0bc-6a97e8b710c6'.
finder-1       | INFO:     Processing item 'http://vendor:7999/api/v2/actors/515663dc-3ab9-4aa9-a0bc-6a97e8b710c6 Announce None' for actor 'http://finder:7999/api/v2/actors/1e28e488-e7d1-475f-9b42-e1f20be1b6cf'
finder-1       | INFO:     Dispatching activity of type 'None' with semantics 'announce_case_log_entry'
finder-1       | ERROR:    Unexpected error dispatching activity_id=urn:uuid:6035c298-dec3-4881-ba21-f12ed8b74b9f actor_id=http://vendor:7999/api/v2/actors/515663dc-3ab9-4aa9-a0bc-6a97e8b710c6 semantics=announce_case_log_entry
finder-1       | Traceback (most recent call last):
finder-1       |   File "/app/vultron/core/dispatcher.py", line 68, in _handle
finder-1       |     use_case_class(dl, event).execute()
finder-1       |     ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^
finder-1       |   File "/app/vultron/core/use_cases/received/sync.py", line 152, in execute
finder-1       |     case_id: str = entry.case_id
finder-1       |                    ^^^^^^^^^^^^^
finder-1       |   File "/app/.venv/lib/python3.13/site-packages/pydantic/main.py", line 1026, in __getattr__
finder-1       |     raise AttributeError(f'{type(self).__name__!r} object has no attribute {item!r}')
finder-1       | AttributeError: 'VultronObject' object has no attribute 'case_id'
finder-1       | ERROR:    Error processing inbox item for actor http://finder:7999/api/v2/actors/1e28e488-e7d1-475f-9b42-e1f20be1b6cf: 'VultronObject' object has no attribute 'case_id'
finder-1       | INFO:     Processing item 'http://vendor:7999/api/v2/actors/515663dc-3ab9-4aa9-a0bc-6a97e8b710c6 Announce None' for actor 'http://finder:7999/api/v2/actors/1e28e488-e7d1-475f-9b42-e1f20be1b6cf'
finder-1       | INFO:     Dispatching activity of type 'None' with semantics 'announce_case_log_entry'
finder-1       | ERROR:    Unexpected error dispatching activity_id=urn:uuid:6035c298-dec3-4881-ba21-f12ed8b74b9f actor_id=http://vendor:7999/api/v2/actors/515663dc-3ab9-4aa9-a0bc-6a97e8b710c6 semantics=announce_case_log_entry
finder-1       | Traceback (most recent call last):
finder-1       |   File "/app/vultron/core/dispatcher.py", line 68, in _handle
finder-1       |     use_case_class(dl, event).execute()
finder-1       |     ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^
finder-1       |   File "/app/vultron/core/use_cases/received/sync.py", line 152, in execute
finder-1       |     case_id: str = entry.case_id
finder-1       |                    ^^^^^^^^^^^^^
finder-1       |   File "/app/.venv/lib/python3.13/site-packages/pydantic/main.py", line 1026, in __getattr__
finder-1       |     raise AttributeError(f'{type(self).__name__!r} object has no attribute {item!r}')
finder-1       | AttributeError: 'VultronObject' object has no attribute 'case_id'
finder-1       | ERROR:    Error processing inbox item for actor http://finder:7999/api/v2/actors/1e28e488-e7d1-475f-9b42-e1f20be1b6cf: 'VultronObject' object has no attribute 'case_id'
finder-1       | INFO:     Processing item 'http://vendor:7999/api/v2/actors/515663dc-3ab9-4aa9-a0bc-6a97e8b710c6 Announce None' for actor 'http://finder:7999/api/v2/actors/1e28e488-e7d1-475f-9b42-e1f20be1b6cf'
finder-1       | INFO:     Dispatching activity of type 'None' with semantics 'announce_case_log_entry'
finder-1       | ERROR:    Unexpected error dispatching activity_id=urn:uuid:6035c298-dec3-4881-ba21-f12ed8b74b9f actor_id=http://vendor:7999/api/v2/actors/515663dc-3ab9-4aa9-a0bc-6a97e8b710c6 semantics=announce_case_log_entry
finder-1       | Traceback (most recent call last):
finder-1       |   File "/app/vultron/core/dispatcher.py", line 68, in _handle
finder-1       |     use_case_class(dl, event).execute()
finder-1       |     ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^
finder-1       |   File "/app/vultron/core/use_cases/received/sync.py", line 152, in execute
finder-1       |     case_id: str = entry.case_id
finder-1       |                    ^^^^^^^^^^^^^
finder-1       |   File "/app/.venv/lib/python3.13/site-packages/pydantic/main.py", line 1026, in __getattr__
finder-1       |     raise AttributeError(f'{type(self).__name__!r} object has no attribute {item!r}')
finder-1       | AttributeError: 'VultronObject' object has no attribute 'case_id'
finder-1       | ERROR:    Error processing inbox item for actor http://finder:7999/api/v2/actors/1e28e488-e7d1-475f-9b42-e1f20be1b6cf: 'VultronObject' object has no attribute 'case_id'
finder-1       | INFO:     Processing item 'http://vendor:7999/api/v2/actors/515663dc-3ab9-4aa9-a0bc-6a97e8b710c6 Announce None' for actor 'http://finder:7999/api/v2/actors/1e28e488-e7d1-475f-9b42-e1f20be1b6cf'
finder-1       | INFO:     Dispatching activity of type 'None' with semantics 'announce_case_log_entry'
finder-1       | ERROR:    Unexpected error dispatching activity_id=urn:uuid:6035c298-dec3-4881-ba21-f12ed8b74b9f actor_id=http://vendor:7999/api/v2/actors/515663dc-3ab9-4aa9-a0bc-6a97e8b710c6 semantics=announce_case_log_entry
finder-1       | Traceback (most recent call last):
finder-1       |   File "/app/vultron/core/dispatcher.py", line 68, in _handle
finder-1       |     use_case_class(dl, event).execute()
finder-1       |     ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^
finder-1       |   File "/app/vultron/core/use_cases/received/sync.py", line 152, in execute
finder-1       |     case_id: str = entry.case_id
finder-1       |                    ^^^^^^^^^^^^^
finder-1       |   File "/app/.venv/lib/python3.13/site-packages/pydantic/main.py", line 1026, in __getattr__
finder-1       |     raise AttributeError(f'{type(self).__name__!r} object has no attribute {item!r}')
finder-1       | AttributeError: 'VultronObject' object has no attribute 'case_id'
finder-1       | ERROR:    Error processing inbox item for actor http://finder:7999/api/v2/actors/1e28e488-e7d1-475f-9b42-e1f20be1b6cf: 'VultronObject' object has no attribute 'case_id'
finder-1       | ERROR:    Too many errors processing inbox for actor http://finder:7999/api/v2/actors/1e28e488-e7d1-475f-9b42-e1f20be1b6cf, aborting.
finder-1       | INFO:     Processing outbox for actor http://finder:7999/api/v2/actors/1e28e488-e7d1-475f-9b42-e1f20be1b6cf
demo-runner-1  | 2026-04-15 15:39:25,448 ERROR    vultron.demo.utils: 🔴 Waiting for Finder to receive replicated log entry
demo-runner-1  | 2026-04-15 15:39:25,449 ERROR    vultron.demo.two_actor_demo: Two-actor demo failed: Timed out waiting for log entry (hash='6cde3f6c9cf03410a4e73557e0c4743bf0ef40cad790fb54846f13226c8c2a9f') for case 'urn:uuid:a344d2d8-3747-4128-b80c-b278f9ce5e9d' to appear in finder's DataLayer — replication may not have completed
demo-runner-1  | Traceback (most recent call last):
demo-runner-1  |   File "/app/vultron/demo/two_actor_demo.py", line 1211, in main
demo-runner-1  |     run_two_actor_demo(
demo-runner-1  |     ~~~~~~~~~~~~~~~~~~^
demo-runner-1  |         finder_client=finder_client,
demo-runner-1  |         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
demo-runner-1  |     ...<3 lines>...
demo-runner-1  |         vendor_id=vendor_id,
demo-runner-1  |         ^^^^^^^^^^^^^^^^^^^^
demo-runner-1  |     )
demo-runner-1  |     ^
demo-runner-1  |   File "/app/vultron/demo/two_actor_demo.py", line 1136, in run_two_actor_demo
demo-runner-1  |     wait_for_finder_log_entry(
demo-runner-1  |     ~~~~~~~~~~~~~~~~~~~~~~~~~^
demo-runner-1  |         finder_client=finder_client,
demo-runner-1  |         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
demo-runner-1  |         case_id=case.id_,
demo-runner-1  |         ^^^^^^^^^^^^^^^^^
demo-runner-1  |         entry_hash=entry_hash,
demo-runner-1  |         ^^^^^^^^^^^^^^^^^^^^^^
demo-runner-1  |     )
demo-runner-1  |     ^
demo-runner-1  |   File "/app/vultron/demo/two_actor_demo.py", line 846, in wait_for_finder_log_entry
demo-runner-1  |     raise AssertionError(
demo-runner-1  |     ...<3 lines>...
demo-runner-1  |     )
demo-runner-1  | AssertionError: Timed out waiting for log entry (hash='6cde3f6c9cf03410a4e73557e0c4743bf0ef40cad790fb54846f13226c8c2a9f') for case 'urn:uuid:a344d2d8-3747-4128-b80c-b278f9ce5e9d' to appear in finder's DataLayer — replication may not have completed
demo-runner-1  | 2026-04-15 15:39:25,451 ERROR    vultron.demo.two_actor_demo: ================================================================================
demo-runner-1  | 2026-04-15 15:39:25,451 ERROR    vultron.demo.two_actor_demo: ERROR SUMMARY
demo-runner-1  | 2026-04-15 15:39:25,451 ERROR    vultron.demo.two_actor_demo: ================================================================================
demo-runner-1  | 2026-04-15 15:39:25,451 ERROR    vultron.demo.two_actor_demo: Timed out waiting for log entry (hash='6cde3f6c9cf03410a4e73557e0c4743bf0ef40cad790fb54846f13226c8c2a9f') for case 'urn:uuid:a344d2d8-3747-4128-b80c-b278f9ce5e9d' to appear in finder's DataLayer — replication may not have completed
demo-runner-1  | 2026-04-15 15:39:25,451 ERROR    vultron.demo.two_actor_demo: ================================================================================
demo-runner-1 exited with code 1
 Compose Stopping Aborting on container exit...
 Container vultron-it-demo-runner-1 Stopping 
 Container vultron-it-demo-runner-1 Stopped 
 Container vultron-it-vendor2-1 Stopping 
 Container vultron-it-vendor-1 Stopping 
 Container vultron-it-coordinator-1 Stopping 
 Container vultron-it-finder-1 Stopping 
 Container vultron-it-case-actor-1 Stopping 
```
