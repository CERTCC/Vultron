# Bugs to fix

Items in this file supersede IMPLEMENTATION_PLAN.md.

Use format `BUG-YYYYMMDDXX` for bug IDs, where `YYYYMMDD` is the date the bug
was identified and `XX` is a sequential number for that day. For example,  
the first bug identified on March 26, 2026 would be `BUG-2026032601`.
Include a brief description in the title, and provide detailed reproduction
steps, root cause analysis, and resolution steps in the body.

---

## BUG-2026040901 Two actor demo fails due to timeout — **FIXED**

**Status**: Fixed in commit (see IMPLEMENTATION_HISTORY.md for details).

`integration_tests/demo/run_multi_actor_integration_test.sh` fails with a
timeout waiting for a case to appear in the finder's DataLayer after the  
vendor engages the case and outbox delivery is triggered. The test fails  
with an assertion error indicating that the case did not appear in the  
finder's DataLayer within the expected time frame, suggesting that the  
outbox delivery may not have completed successfully.

```text
demo-runner-1  | 2026-04-09 19:28:56,291 INFO     vultron.demo.utils: 🚥 Vendor engages case (RM.VALID → RM.ACCEPTED)
demo-runner-1  | 2026-04-09 19:28:56,291 INFO     vultron.demo.utils: Posting trigger 'engage-case' for actor '68ab4176-ec93-442e-aa17-95d2f8d1d5a1': {'case_id': 'urn:uuid:77a41273-ef39-4084-bef3-f3cc1d258e86'}
vendor-1       | INFO:     Set participant 'http://vendor:7999/api/v2/actors/68ab4176-ec93-442e-aa17-95d2f8d1d5a1' RM state to ACCEPTED in case 'urn:uuid:77a41273-ef39-4084-bef3-f3cc1d258e86'
vendor-1       | INFO:     Actor 'http://vendor:7999/api/v2/actors/68ab4176-ec93-442e-aa17-95d2f8d1d5a1' engaged case 'urn:uuid:77a41273-ef39-4084-bef3-f3cc1d258e86' (RM → ACCEPTED)
demo-runner-1  | 2026-04-09 19:28:56,325 INFO     vultron.demo.utils: 🟢 Vendor engages case (RM.VALID → RM.ACCEPTED)
vendor-1       | INFO:     Processing outbox for actor 68ab4176-ec93-442e-aa17-95d2f8d1d5a1
demo-runner-1  | 2026-04-09 19:28:56,342 INFO     vultron.demo.utils: 📋 Finder's DataLayer received case via Vendor outbox delivery
demo-runner-1  | 2026-04-09 19:29:06,450 ERROR    vultron.demo.utils: ❌ Finder's DataLayer received case via Vendor outbox delivery
demo-runner-1  | 2026-04-09 19:29:06,451 ERROR    vultron.demo.two_actor_demo: Two-actor demo failed: Timed out waiting for case 'urn:uuid:77a41273-ef39-4084-bef3-f3cc1d258e86' to appear in finder's DataLayer — outbox delivery may not have completed
demo-runner-1  | Traceback (most recent call last):
demo-runner-1  |   File "/app/vultron/demo/two_actor_demo.py", line 923, in main
demo-runner-1  |     run_two_actor_demo(
demo-runner-1  |     ~~~~~~~~~~~~~~~~~~^
demo-runner-1  |         finder_client=finder_client,
demo-runner-1  |         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
demo-runner-1  |     ...<3 lines>...
demo-runner-1  |         vendor_id=vendor_id,
demo-runner-1  |         ^^^^^^^^^^^^^^^^^^^^
demo-runner-1  |     )
demo-runner-1  |     ^
demo-runner-1  |   File "/app/vultron/demo/two_actor_demo.py", line 815, in run_two_actor_demo
demo-runner-1  |     wait_for_finder_case(
demo-runner-1  |     ~~~~~~~~~~~~~~~~~~~~^
demo-runner-1  |         finder_client=finder_client,
demo-runner-1  |         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
demo-runner-1  |         case_id=case.id_,
demo-runner-1  |         ^^^^^^^^^^^^^^^^^
demo-runner-1  |     )
demo-runner-1  |     ^
demo-runner-1  |   File "/app/vultron/demo/two_actor_demo.py", line 700, in wait_for_finder_case
demo-runner-1  |     raise AssertionError(
demo-runner-1  |     ...<2 lines>...
demo-runner-1  |     )
demo-runner-1  | AssertionError: Timed out waiting for case 'urn:uuid:77a41273-ef39-4084-bef3-f3cc1d258e86' to appear in finder's DataLayer — outbox delivery may not have completed
demo-runner-1  | 2026-04-09 19:29:06,453 ERROR    vultron.demo.two_actor_demo: ================================================================================
demo-runner-1  | 2026-04-09 19:29:06,453 ERROR    vultron.demo.two_actor_demo: ERROR SUMMARY
demo-runner-1  | 2026-04-09 19:29:06,453 ERROR    vultron.demo.two_actor_demo: ================================================================================
demo-runner-1  | 2026-04-09 19:29:06,453 ERROR    vultron.demo.two_actor_demo: Timed out waiting for case 'urn:uuid:77a41273-ef39-4084-bef3-f3cc1d258e86' to appear in finder's DataLayer — outbox delivery may not have completed
demo-runner-1  | 2026-04-09 19:29:06,453 ERROR    vultron.demo.two_actor_demo: ================================================================================
demo-runner-1 exited with code 1
```

## BUG-2026040902 Finder timeout (incomplete fix of BUG-2026040901)

**Status**: Open — alias fixes applied (2026-04-10) but Docker
integration test still fails with the same timeout symptom.

After the claimed fix to BUG-2026040901, the same test still fails.

`integration_tests/demo/run_multi_actor_integration_test.sh` fails with a
timeout waiting for a case to appear in the finder's DataLayer after the  
vendor engages the case and outbox delivery is triggered. Previous fix was
attempted but did not in fact resolve the issue.
BUG-2026040902 is not resolved until the shell script runs and exits with
"SUCCESS: scenario 'two-actor' passed."

### Root cause analysis (2026-04-09)

The full delivery pipeline was traced across 3 investigation phases. The logs
show that `validate-report` BT execution succeeds (case IS created in vendor
DL, line 92), but the `Create(VulnerabilityCase)` activity is **never
delivered to the finder**.

Key observations from the log:

- Line 91: `"Processing outbox for actor 54dacb37-..."` after validate-report
  — **no outbox items processed** (empty outbox at that point)
- Lines 99–100: `"Processing outbox for actor..."` + `"Processing outbox
  item...: urn:uuid:b70325d2-..."` after engage-case — ONE item processed,
  but this is `RmEngageCaseActivity` (has no `to=` recipients, so not
  delivered)
- No "Delivered Create..." log ever appears → the Create(Case) activity was
  either never queued or drained before the finder check

**Confirmed**: The `ReceiveReportCaseBT` (run during offer processing) writes
the `Create(VulnerabilityCase)` activity and outbox entry to the **shared**
DataLayer. However, `inbox_handler` (the background task for the offer)
drains the vendor outbox **after** the BT runs — but the log shows **no
outbox items** after validate-report. The validate-report trigger runs a
*different* BT (`ValidateReportBT`), not `ReceiveReportCaseBT`.

**Most likely root cause**: The `Create(VulnerabilityCase)` activity and
outbox entry are written during **offer inbox processing** (not during
validate-report). By the time the vendor's `wait_for_case_participants`
check passes and `wait_for_finder_case` is called, the offer's
`inbox_handler` background task may have already drained the outbox and
delivered the Create(Case) — but the finder's inbox handler (also a
background task) has not yet completed pre-storage or `CreateCaseReceivedUseCase`.

Alternatively, `UpdateActorOutbox` in `ReceiveReportCaseBT` may be writing
the outbox entry to the **actor-scoped** DataLayer (keyed by full URI) while
`outbox_handler` in `inbox_handler` reads from a **different** actor-scoped
DL instance. This race/mismatch scenario needs direct verification by adding
log statements or a targeted test.

**Secondary latent bugs** (do not block the fix but should be addressed):

1. `VultronCreateCaseActivity.type_` (and `VultronOffer.type_`,
   `VultronAccept.type_`) redefine `type_` **without**
   `Field(serialization_alias="type")`, so `model_dump(by_alias=True)`
   emits `"type_"` instead of `"type"`. These are currently bypassed because
   the activity is read back from DL as `as_Create` before delivery, but the
   bug would surface if the objects were serialized directly.
   - Files: `vultron/core/models/activity.py` lines 74, 84, 94

2. `VultronBase.id_` has no `serialization_alias="id"`, so
   `model_dump(by_alias=True)` produces `"id_"` instead of `"id"`. Since
   `as_Base` uses `validate_by_name=True`, round-tripping works, but the
   emitted payload is non-standard.
   - File: `vultron/core/models/activity.py` (VultronBase base class)

### Plan to fix

1. **Add targeted logging** (or a unit test) to confirm whether the outbox
   entry for `Create(VulnerabilityCase)` is ever written during offer
   processing, and whether it is successfully drained.

2. **Most probable fix**: In `ReceiveReportCaseBT` →
   `UpdateActorOutbox.update()`, confirm the DL used is the same instance that
   `outbox_handler` reads from. If there is a scoping mismatch (actor-scoped
   vs shared), align them.

3. **Alternative**: If timing is the issue (finder background task not
   finished before `wait_for_finder_case` times out), increase the poll
   timeout in `wait_for_finder_case` or add a short sleep after the outbox
   drain in `inbox_handler`.

4. **Address latent serialization bugs** in `vultron/core/models/activity.py`
   (items 1 and 2 above) as a follow-on cleanup.

5. Fix must be verified by running
   `integration_tests/demo/run_multi_actor_integration_test.sh` and
   confirming "SUCCESS: scenario 'two-actor' passed."

```text
demo-runner-1  | 2026-04-09 20:25:21,079 INFO     vultron.demo.utils: 🚥 Vendor validates the vulnerability report
demo-runner-1  | 2026-04-09 20:25:21,079 INFO     vultron.demo.utils: Posting trigger 'validate-report' for actor '54dacb37-6f78-44e0-9824-617859138a99': {'offer_id': 'urn:uuid:f17497b0-fe3c-4f02-a448-7ae2eca3e883'}
vendor-1       | INFO:     BT setup complete for actor http://vendor:7999/api/v2/actors/54dacb37-6f78-44e0-9824-617859138a99
vendor-1       | INFO:     EvaluateReportCredibility: Evaluating credibility for report urn:uuid:8f8d05a0-df30-4270-93a2-74a318ac5743 (stub: always accepts)
vendor-1       | INFO:     EvaluateReportValidity: Evaluating validity for report urn:uuid:8f8d05a0-df30-4270-93a2-74a318ac5743 (stub: always accepts)
vendor-1       | INFO:     Stored ParticipantStatus (report-phase RM.VALID) 'urn:uuid:932a53fd-0170-575c-8ca4-c5ba6e9e37b0'
vendor-1       | INFO:     RM → VALID for report 'urn:uuid:8f8d05a0-df30-4270-93a2-74a318ac5743' (actor 'http://vendor:7999/api/v2/actors/54dacb37-6f78-44e0-9824-617859138a99')
vendor-1       | INFO:     Set participant 'http://vendor:7999/api/v2/actors/54dacb37-6f78-44e0-9824-617859138a99' RM state to VALID in case 'urn:uuid:2b55d408-dcde-46c3-a615-ee09f32fcca3'
vendor-1       | INFO:     BT execution completed: Status.SUCCESS after 1 ticks - 
demo-runner-1  | 2026-04-09 20:25:21,209 INFO     vultron.demo.utils: 🟢 Vendor validates the vulnerability report
demo-runner-1  | 2026-04-09 20:25:21,209 INFO     vultron.demo.two_actor_demo: Validate-report trigger result for actor 54dacb37-6f78-44e0-9824-617859138a99
demo-runner-1  | 2026-04-09 20:25:21,209 INFO     vultron.demo.utils: 📋 VulnerabilityCase exists in Vendor's DataLayer
vendor-1       | INFO:     Processing outbox for actor 54dacb37-6f78-44e0-9824-617859138a99
demo-runner-1  | 2026-04-09 20:25:21,251 INFO     vultron.demo.two_actor_demo: Case created: urn:uuid:2b55d408-dcde-46c3-a615-ee09f32fcca3
demo-runner-1  | 2026-04-09 20:25:21,251 INFO     vultron.demo.utils: ✅ VulnerabilityCase exists in Vendor's DataLayer
demo-runner-1  | 2026-04-09 20:25:21,252 INFO     vultron.demo.utils: 🚥 Vendor engages case (RM.VALID → RM.ACCEPTED)
demo-runner-1  | 2026-04-09 20:25:21,252 INFO     vultron.demo.utils: Posting trigger 'engage-case' for actor '54dacb37-6f78-44e0-9824-617859138a99': {'case_id': 'urn:uuid:2b55d408-dcde-46c3-a615-ee09f32fcca3'}
vendor-1       | INFO:     Set participant 'http://vendor:7999/api/v2/actors/54dacb37-6f78-44e0-9824-617859138a99' RM state to ACCEPTED in case 'urn:uuid:2b55d408-dcde-46c3-a615-ee09f32fcca3'
vendor-1       | INFO:     Actor 'http://vendor:7999/api/v2/actors/54dacb37-6f78-44e0-9824-617859138a99' engaged case 'urn:uuid:2b55d408-dcde-46c3-a615-ee09f32fcca3' (RM → ACCEPTED)
demo-runner-1  | 2026-04-09 20:25:21,301 INFO     vultron.demo.utils: 🟢 Vendor engages case (RM.VALID → RM.ACCEPTED)
vendor-1       | INFO:     Processing outbox for actor 54dacb37-6f78-44e0-9824-617859138a99
vendor-1       | INFO:     Processing outbox item for actor '54dacb37-6f78-44e0-9824-617859138a99': urn:uuid:b70325d2-f5ac-4f26-8820-bb1ceb406093
demo-runner-1  | 2026-04-09 20:25:21,324 INFO     vultron.demo.utils: 📋 Finder's DataLayer received case via Vendor outbox delivery
demo-runner-1  | 2026-04-09 20:25:31,437 ERROR    vultron.demo.utils: ❌ Finder's DataLayer received case via Vendor outbox delivery
demo-runner-1  | 2026-04-09 20:25:31,437 ERROR    vultron.demo.two_actor_demo: Two-actor demo failed: Timed out waiting for case 'urn:uuid:2b55d408-dcde-46c3-a615-ee09f32fcca3' to appear in finder's DataLayer — outbox delivery may not have completed
demo-runner-1  | Traceback (most recent call last):
demo-runner-1  |   File "/app/vultron/demo/two_actor_demo.py", line 923, in main
demo-runner-1  |     run_two_actor_demo(
demo-runner-1  |     ~~~~~~~~~~~~~~~~~~^
demo-runner-1  |         finder_client=finder_client,
demo-runner-1  |         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
demo-runner-1  |     ...<3 lines>...
demo-runner-1  |         vendor_id=vendor_id,
demo-runner-1  |         ^^^^^^^^^^^^^^^^^^^^
demo-runner-1  |     )
demo-runner-1  |     ^
demo-runner-1  |   File "/app/vultron/demo/two_actor_demo.py", line 815, in run_two_actor_demo
demo-runner-1  |     wait_for_finder_case(
demo-runner-1  |     ~~~~~~~~~~~~~~~~~~~~^
demo-runner-1  |         finder_client=finder_client,
demo-runner-1  |         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
demo-runner-1  |         case_id=case.id_,
demo-runner-1  |         ^^^^^^^^^^^^^^^^^
demo-runner-1  |     )
demo-runner-1  |     ^
demo-runner-1  |   File "/app/vultron/demo/two_actor_demo.py", line 700, in wait_for_finder_case
demo-runner-1  |     raise AssertionError(
demo-runner-1  |     ...<2 lines>...
demo-runner-1  |     )
demo-runner-1  | AssertionError: Timed out waiting for case 'urn:uuid:2b55d408-dcde-46c3-a615-ee09f32fcca3' to appear in finder's DataLayer — outbox delivery may not have completed
demo-runner-1  | 2026-04-09 20:25:31,439 ERROR    vultron.demo.two_actor_demo: ================================================================================
demo-runner-1  | 2026-04-09 20:25:31,439 ERROR    vultron.demo.two_actor_demo: ERROR SUMMARY
demo-runner-1  | 2026-04-09 20:25:31,439 ERROR    vultron.demo.two_actor_demo: ================================================================================
demo-runner-1  | 2026-04-09 20:25:31,439 ERROR    vultron.demo.two_actor_demo: Timed out waiting for case 'urn:uuid:2b55d408-dcde-46c3-a615-ee09f32fcca3' to appear in finder's DataLayer — outbox delivery may not have completed
demo-runner-1  | 2026-04-09 20:25:31,439 ERROR    vultron.demo.two_actor_demo: ================================================================================
demo-runner-1 exited with code 1
```

### Attempted fix (2026-04-10) — did not resolve the issue

Two real Pydantic v2 serialization alias bugs were found and fixed
(committed in `38c0a764`), but the Docker integration test still
fails with the same timeout.

The bugs that were fixed (both are real bugs, correctly fixed):

1. **`VultronBase.id_` missing aliases** — `Field(default_factory=...)`
   with no `validation_alias="id"` or `serialization_alias="id"`.
   `model_dump(by_alias=True)` emitted `"id_"` instead of `"id"`, and
   `model_validate({"id": "..."})` generated a NEW UUID instead of
   preserving the original.

2. **Subclass `type_` overrides losing parent aliases** — Ten domain
   model classes redefined `type_` with bare `Literal[...] = ...`
   annotations, losing the parent's `Field(validation_alias="type",
   serialization_alias="type")` metadata.

These bugs were confirmed by 14 new unit tests and are correctly
fixed. However, they were not the primary cause of the Docker
integration failure. The outbox delivery log (see above) shows **only
one outbox item ever processed** (`RmEngageCaseActivity`, after
`engage-case`), and that item has no `to=` recipients so nothing is
delivered. The `Create(VulnerabilityCase)` activity is **never
processed from the outbox at all** — the problem is upstream of
serialization.

### Updated root cause hypothesis

The `Create(VulnerabilityCase)` activity is either:

**Hypothesis A** (most likely): Never queued into the outbox. The
activity IS created by `ReceiveReportCaseBT` / `UpdateActorOutbox`,
but the `record_outbox_item` call writes to a table keyed by the
vendor actor's canonical URI. If the BT node resolves the actor URI
differently than the outbox handler reads it, the entry is written to
a different table than is drained. Specifically: the BT may write
using the short UUID (e.g. `54dacb37-...`) while the outbox handler
reads from `http://vendor:7999/api/v2/actors/54dacb37-..._outbox`.

**Hypothesis B**: The activity IS queued but has an empty `to=`
recipients list. `UpdateActorOutbox` in `ReceiveReportCaseBT`
collects recipients from `case.actor_participant_index` — if the
finder is not yet registered there at the time the BT runs (offer
inbox processing happens before `validate-report` seeds the
participant index), the recipients list will be empty and delivery is
skipped silently.

**Hypothesis C**: The outbox IS drained after offer processing, but
the finder inbox handler (a background task) hasn't stored the case
yet when `wait_for_finder_case` starts polling. This is a timing
race, not a logic bug. Increasing the poll timeout or retry interval
would work around it but not fix the root cause.

### Next steps

1. **Instrument `record_outbox_item`** — add a DEBUG log line showing
   the exact table name written and the activity ID. Compare to the
   table name the outbox handler reads from. This will confirm or
   rule out Hypothesis A.

2. **Inspect `UpdateActorOutbox.update()`** — check what `to=`
   recipients are collected at BT runtime (offer inbox processing),
   specifically whether the finder participant appears in
   `case.actor_participant_index` at that point.

3. **Check timing of participant seeding** — `SubmitReportReceivedUseCase`
   processes the offer and runs `ReceiveReportCaseBT`. Does the finder
   get seeded as a case participant before `UpdateActorOutbox` runs?
   Look at `CreateInitialVendorParticipant` and peer participant nodes.

4. **Add an integration-level smoke test** that directly calls the
   offer inbox endpoint in-process and asserts that an outbox entry
   with a non-empty `to=` list is created. This would catch
   regressions without needing Docker.

5. **If Hypothesis B is confirmed**: Fix `ReceiveReportCaseBT` to
   ensure the finder/reporter is added as a case participant before
   `UpdateActorOutbox` runs, OR move the `Create(VulnerabilityCase)`
   outbox queuing to after participant seeding (e.g. end of
   `validate-report` trigger instead of offer inbox processing).
