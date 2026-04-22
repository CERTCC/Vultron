# Bugs to fix

Items in this file supersede IMPLEMENTATION_PLAN.md.

Use format `BUG-YYMMDDXX` for bug IDs, where `YYMMDD` is the date the bug
was identified and `XX` is a sequential number for that day. For example,
the first bug identified on March 26, 2026 would be `BUG-26032601`.
Include a brief description in the title, and provide detailed reproduction
steps, root cause analysis, and resolution steps in the body.

---

## BUG-26041701 Outbound initiating activities have inline object_ as bare string/Link — NEW

I observed repeated errors during multi-vendor demo runs indicating outbound
initiating activities (Add/Invite/Join) were emitted with inline `object_`
values that are bare strings or Links rather than inline typed objects. Examples
from multi-vendor demo log:

```text
vendor-1       | ERROR:    Error processing outbox item for actor http://vendor:7999/...: Outbound Add activity 'urn:uuid:612d9084-0503-4efc-be82-ac7268a063c3' has an inline object_ that is a bare string or Link ('urn:uuid:a8e00b2f-07ad-45de-8944-03aab84fac1f'). Outbound initiating activities must carry fully inline typed objects (MV-09-001).
vendor-1       | ERROR:    Too many errors processing outbox for actor e5cff123-3cec-485f-8449-bab649dfb2ff, aborting.
```

Reproduction: run the multi-vendor demo (`make integration-test-multi-vendor` or
the demo runner) and inspect `multi-vendor-demo-log.txt` for MV-09-001 errors.

Hypothesis / root cause: demo helper code (or demo fixtures) constructs outbound
initiating activities using `object_=obj.id_` (a string/Link) instead of
embedding the inline typed `obj` (e.g., `Case`, `Participant`). This leads to
outbound validation failing in the Outbox processor.

Resolution steps:

- Update demo code to emit inline typed objects for initiating outbound
  activities (replace `object_=id_` with `object_=obj`).
- Add validation in Outbox processing (or regression test) to catch and
  fail-fast when an outbound initiating activity contains a bare string/Link as
  `object_`.
- Add a regression test that runs the demo flow and fails if MV-09-001 errors
  appear.

Verification update (2026-04-22):

- `vultron/core/behaviors/case/nodes.py` now emits
  `AddParticipantToCaseActivity(object_=case_participant, ...)`, so the
  case-participant Add path no longer queues a bare-string `object_`.
- `vultron/wire/as2/vocab/activities/` constrains initiating activity
  `object_` fields to typed inline objects, and the regression tests under
  `test/wire/as2/vocab/test_actvitities/` reject bare strings and Links.
- `vultron/adapters/driving/fastapi/outbox_handler.py` now expands legacy bare
  string `object_` values for `Create` / `Announce` / `Add` / `Invite` /
  `Accept`, then raises `VultronOutboxObjectIntegrityError` if the object is
  still unresolved.

Status: FIXED — verified 2026-04-22; the bug appears already resolved in the
current tree by existing INLINE-OBJ / outbox integrity changes.

## BUG-26041801

We don't actually know whether the `reporter` is the `finder` but we do know
that the `reporter` is the `attributed_to` of the `Offer` of a `Report`. So
we should not have attribute names including `finder` anywhere. We should
rename it the `reporter` everywhere.

` finder_actor_id: Actor ID of the party who submitted the report.
`

## BUG-26041802

The solution to P-247-BRIDGE might be incomplete. It seems like we probably
want this behavior to apply ot all activities that have an `object_`, not
just a specific list. All transitive activities need to require an object.

---

## BUG-26042101 — accept-embargo 409 on second acceptance in multi-party demos — NEW

**Symptoms:** `test/demo/test_multi_vendor_demo.py` and
`test/demo/test_three_actor_demo.py` fail with:

```text
  "message":"Cannot accept embargo: case '...' EM state 'ACTIVE'
  does not allow an ACCEPT transition."}}
```

**Root cause:** The `SvcAcceptEmbargoUseCase` updates the *case-level*
`current_status.em_state`. When participant A (e.g. finder) accepts the
embargo, the case EM state transitions `PROPOSED → ACTIVE`. When participant
B (e.g. vendor) then calls `accept-embargo` on the same shared case, the
state is already `ACTIVE` — which has no ACCEPT transition — so the trigger
raises `VultronInvalidStateTransitionError`.

**Related plan item:** The implementation plan already has a task to refactor
per-participant embargo consent into a dedicated 5-state machine
(`NO_EMBARGO → INVITED → SIGNATORY → LAPSED → DECLINED`) on each
`CaseParticipant`, replacing the single case-level EM state as the tracking
mechanism. When that task lands this bug will be resolved.

**Workaround until fix:** None — multi-party embargo acceptance is broken for
any case with more than one non-coordinating participant.

Status: NEW — added 2026-04-21.

## BUG-26042201 — Announce log-entry activities fail coercion and demos time out waiting for replication — NEW

**Symptoms:** Multiple demo logs show repeated warnings when processing
`as_Announce` activities that are expected to coerce to
`AnnounceLogEntryActivity`. In the two-actor demo, the run later fails while
waiting for the replicated log entry to appear in the recipient's DataLayer.

```text
multi-actor-demo-log.txt
vendor-1       | WARNING:  Could not coerce 'as_Announce' to semantic class 'AnnounceLogEntryActivity': 3 validation errors for AnnounceLogEntryActivity
vendor-1       | object.caseId
vendor-1       |   Field required [type=missing, input_value={'@context': 'https://www...e, 'attributedTo': None}, input_type=dict]

multi-actor-demo-log.txt
demo-runner-1  | ERROR    vultron.demo.scenario.two_actor_demo: Two-actor demo failed: Timed out waiting for log entry (hash='02218ef7d2dafbab9a5c24e30751ddb47f20432b27fc93e18b0108e091537f68') for case 'urn:uuid:7a3cc005-5932-4c65-80df-c86dd9b9319d' to appear in finder's DataLayer — replication may not have completed

three-actor-demo-log.txt
coordinator-1  | WARNING:  Could not coerce 'as_Announce' to semantic class 'AnnounceLogEntryActivity': 3 validation errors for AnnounceLogEntryActivity
coordinator-1  | object.caseId
```

**Brief description:** Log-entry announcement handling appears incomplete or
inconsistent across demos. The warnings are present in both the two-actor and
three-actor logs, and the two-actor scenario aborts after timing out while
waiting for the expected replicated log entry.

Status: NEW — added 2026-04-22.

## BUG-26042202 — Trigger flows skip outbox updates because actor record cannot be found with an outbox — NEW

**Symptoms:** Trigger-driven demo steps log warnings that
`add_activity_to_outbox` could not find the actor or an `outbox` field, so the
code skips the `outbox.items` update even though the trigger itself continues.

```text
multi-vendor-demo-log.txt
vendor-1       | WARNING:  add_activity_to_outbox: actor 'bc51a90a-830b-49ed-9e19-70b8bbf749a5' not found or has no outbox field; skipping outbox.items update
vendor-1       | INFO:     Actor 'bc51a90a-830b-49ed-9e19-70b8bbf749a5' created case 'urn:uuid:338a1bc3-bfde-410f-b59a-a0d827ffb9e9' (CreateCaseActivity 'urn:uuid:60c5ed6f-be50-4369-996e-fa1bac55d3f2')

three-actor-demo-log.txt
coordinator-1  | WARNING:  add_activity_to_outbox: actor '05ad9820-c910-4721-8636-0dfd133949eb' not found or has no outbox field; skipping outbox.items update
coordinator-1  | INFO:     Actor '05ad9820-c910-4721-8636-0dfd133949eb' created case 'urn:uuid:b1229615-f1dc-4fae-8cba-e44c8ce1d715' (CreateCaseActivity 'urn:uuid:45b3cad6-404a-42ac-a45b-3184169d23ff')
```

**Brief description:** At least the create-case path in the multi-party demos
is emitting a warning that the actor record used for outbox mutation is missing
or lacks an `outbox`. The scenarios continue past the warning, so this may be a
silent consistency problem rather than an immediate crash.

Status: NEW — added 2026-04-22.

## BUG-26042203 — Multi-party invite/accept activities retain unresolved references and can dead-letter inbound Accepts — NEW

**Symptoms:** The multi-vendor and three-actor logs show a recurring cluster of
warnings around invitation and acceptance activities: failed `target`
rehydration on `as_Invite`, failed coercion of `as_Accept` to
`RmAcceptInviteToCaseActivity`, and later failed `object_` rehydration that
causes an inbound `Accept` to be stored as a dead-letter record.

```text
multi-vendor-demo-log.txt
finder-1       | WARNING:  Could not rehydrate field 'target' with id 'urn:uuid:338a1bc3-bfde-410f-b59a-a0d827ffb9e9' on 'as_Invite'; keeping string reference.
finder-1       | WARNING:  Could not coerce 'as_Accept' to semantic class 'RmAcceptInviteToCaseActivity': 1 validation error for RmAcceptInviteToCaseActivity
finder-1       | object.actor
finder-1       |   Field required [type=missing, input_value={'@context': 'https://www...e, 'attributedTo': None}, input_type=dict]

multi-vendor-demo-log.txt
vendor-1       | WARNING:  Could not rehydrate field 'object_' with id 'urn:uuid:4adf4185-ea7f-446d-a584-7664a8308b43' on 'as_Accept'; keeping string reference.
vendor-1       | INFO:     Dispatching activity of type 'None' with semantics 'unknown_unresolvable_object'
vendor-1       | WARNING:  Unresolvable object_ URI 'urn:uuid:4adf4185-ea7f-446d-a584-7664a8308b43' in activity 'urn:uuid:1bdb9a0a-12c3-4d27-b351-0c82187918b7' (actor 'http://finder:7999/api/v2/actors/cde5f548-5f07-4a76-a92d-cacc4b61d258'); storing dead-letter record.

three-actor-demo-log.txt
coordinator-1  | WARNING:  Could not rehydrate field 'object_' with id 'urn:uuid:2e92889d-1cbe-4f61-b0f2-8af921b09d7f' on 'as_Accept'; keeping string reference.
coordinator-1  | INFO:     Dispatching activity of type 'None' with semantics 'unknown_unresolvable_object'
coordinator-1  | WARNING:  Unresolvable object_ URI 'urn:uuid:2e92889d-1cbe-4f61-b0f2-8af921b09d7f' in activity 'urn:uuid:43af50f0-baef-4f04-b32e-a7b9668009de' (actor 'http://finder:7999/api/v2/actors/8e15535a-2e7b-4e75-adc1-97da3c8af649'); storing dead-letter record.
```

**Brief description:** Multi-party coordination flows are producing inbound
activities whose referenced objects cannot be rehydrated back into the expected
typed form. This is visible before the demo-ending 409s and suggests a
separate interoperability/data-shape problem in invite/accept handling.

Status: NEW — added 2026-04-22.
