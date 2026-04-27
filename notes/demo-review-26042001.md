---
title: Demo Review — 2026-04-20
status: archived
description: >
  Point-in-time demo review from 2026-04-20; log analysis and findings from
  the demonstration run.
related_specs:
  - specs/architecture.yaml
relevant_packages:
  - transitions
  - vultron/demo
---

# Demo Review — 2026-04-20

Log files analysed:

- `devlogs/multi-actor-demo-log.txt` — two-actor scenario (finder + vendor)
- `devlogs/three-actor-demo-log.txt` — three-actor scenario (finder + coordinator +
  vendor + dedicated case-actor)
- `devlogs/multi-vendor-demo-log.txt` — multi-vendor scenario

All three demos failed. The same root-cause clusters appear in every run. Issues
are grouped by problem area below.

---

## 1. Activity Serialization: Domain Objects Stored Inline as `target`

Severity: High — causes cascading outbox failures in every demo run

**Symptom:** Every outbox processing cycle produces batches of:

```text
ERROR: Error processing outbox item for actor <id>: 1 validation error for VultronActivity
target
  Input should be a valid string [type=string_type,
    input_value={'@context': 'https://www...', ...}, input_type=dict]
```

Followed by:

```text
ERROR: Too many errors processing outbox for actor <id>, aborting.
```

**Affected actors:** finder, vendor (both short-UUID and full-URI forms).

**Root cause:** Activities stored in the outbox carry a full inline
`VulnerabilityCase` dict as their `target` field. The outbox delivery loop
reads each activity, deserializes it as `VultronActivity`, and `VultronActivity.target`
is typed as `str`, so validation rejects the nested object. The same item is
retried 3–4 times and then the outbox is aborted entirely.

The problem originates upstream when activities are constructed: the `target`
field is set to a live `VulnerabilityCase` model instance rather than its `id_`
string. The fix is to dehydrate `target` to the object's URI at construction
time, or to type `VultronActivity.target` as `str | dict | None` and coerce
on read.

**Impact:** Once the outbox aborts, pending deliveries are dropped. In the
two-actor demo this directly prevents the `add-note-to-case` activity from
being forwarded after the outbox encounters earlier failures, contributing
to the note-in-case timeout (see §7).

---

## 2. Activity `name` Field Contains Python `repr()` of Domain Objects

Severity: Medium — corrupt wire data visible to remote actors

**Symptom:** Log entries show activity `name` values like:

```text
"name": "http://coordinator:.../actors/24d63c7d-... Add Coordinated disclosure for
  dependency parser RCE to context_='https://www.w3.org/ns/activitystreams'
  type_=<VultronObjectType.VULNERABILITY_CASE: 'VulnerabilityCase'>
  id_='urn:uuid:6c1dc4f9-...' name='Three-Actor Demo Case' preview=None ..."
```

The Python `__repr__` of a `VulnerabilityCase` instance is embedded directly
in the `name` string of `Add`, `Invite`, and `Accept` activities.

**Root cause:** Activity name generation constructs the string with
`f"{actor} {type} {object}"` (or similar), where `object` is the live Python
model object rather than `object.name` or `object.id_`. This happens in the
BT nodes that construct outbound activities when the `object_` field holds a
`VulnerabilityCase`.

**Impact:** The raw Python repr is delivered over the wire to remote actors
and stored in their DataLayer. It is non-conformant ActivityStreams, makes
logs unreadable, and will cause semantic extraction issues on the receiving
end (pattern matchers see a non-JSON name string where they expect a concise
human-readable label).

---

## 3. Semantic Extraction: `Accept(Invite)` Incorrectly Matched to `validate_report`

Severity: High — use-case dispatch crash; repeated retries exhaust inbox

**Symptom:**

```text
WARNING: Could not rehydrate field 'object_' with id '<uuid>' on 'as_Accept';
  keeping string reference.
WARNING: Could not coerce 'as_Accept' to semantic class 'RmValidateReportActivity':
  1 validation error for RmValidateReportActivity
    object: Input should be a valid dictionary or instance of RmSubmitReportActivity
      [type=model_type, input_value='<uuid>', input_type=str]
ERROR: Unexpected error dispatching ... semantics=validate_report
  ValueError: ValidateReportReceivedEvent requires report_id and offer_id
ERROR: Error processing inbox item for actor <coordinator|vendor>:
  ValidateReportReceivedEvent requires report_id and offer_id
ERROR: Too many errors processing inbox for actor <id>, aborting.
```

Seen in: coordinator (three-actor), vendor (multi-vendor).

**Root cause:** The activity being dispatched is Finder's `Accept` of an
embargo `Invite` emitted by the coordinator. Rehydration fails because the
`Invite` referenced in the `Accept.object_` field is not present in the
receiving actor's DataLayer. The extractor falls through to a pattern that
matches `as_Accept(object=as_Offer(object=VulnerabilityReport))` — the
`validate_report` semantic — because it cannot distinguish a failed-rehydration
string from a plain `Offer`. The dispatcher then constructs a
`ValidateReportReceivedEvent` without the required `report_id` or `offer_id`,
and the use case raises a plain `ValueError` rather than a domain-typed error.

**Two independent bugs:**

1. **Pattern matching is not robust to failed rehydration.** When rehydration
   returns a bare string, `find_matching_semantics` should not match patterns
   that require a specific typed object. The fallback to `validate_report` is
   incorrect.
2. **`ValidateReportReceivedEvent` validates too late.** The use case raises
   `ValueError` inside `execute()` rather than at event construction time,
   bypassing the fail-fast invariant (see `specs/architecture.yaml` ARCH-10-001).

---

## 4. Semantic Coercion: Missing Fields in Nested `Invite` Objects

Severity: Medium — coercion warnings; dispatch proceeds on fallback

### 4a. `RmAcceptInviteToCaseActivity` — missing `object.actor`

```text
WARNING: Could not coerce 'as_Accept' to semantic class 'RmAcceptInviteToCaseActivity':
  1 validation error for RmAcceptInviteToCaseActivity
    object.actor: Field required
```

Seen in: case-actor (three-actor, multi-vendor).

The `Accept` activity's nested `object` is a full inline `VulnerabilityCase`
(not the `RmInviteToCaseActivity` that was originally invited). Dispatch still
succeeds on the fallback path, and the accept-invite BT runs correctly — but the
coercion warning is a sign that the `Accept.object_` is carrying the wrong
object type.

### 4b. `EmAcceptEmbargoActivity` — missing `object.actor` and `object.object`

```text
WARNING: Could not coerce 'as_Accept' to semantic class 'EmAcceptEmbargoActivity':
  2 validation errors for EmAcceptEmbargoActivity
    object.actor: Field required
    object.object: Field required
```

Seen in: case-actor (three-actor, multi-vendor).

Same pattern: the Accept's `object_` is a generic `as_Event`/`EmbargoEvent`
rather than the full inline `EmInviteToEmbargoOnCaseActivity` required by the
coercion target. The coercion log is a warning (not fatal), but it means the
`EmAcceptEmbargoActivity` semantic subclass is never successfully constructed.

**Root cause (both):** When constructing an `Accept` or `Reject` in response
to an `Invite`, the code is passing the case object or the embargo event object
as `object_` instead of the original `Invite` activity. See the AGENTS.md
"Accept/Reject `object` Field" pitfall entry.

---

## 5. Embargo State Machine: Multi-Party `accept-embargo` Fails with 409

Severity: High — demo-halting crash in three-actor and multi-vendor demos

**Symptom:**

```text
WARNING: Invalid EM state transition: actor '...' cannot ACCEPT proposal '<uuid>'
  on case '<uuid>' (EM state 'ACTIVE').
ERROR response: {"detail":{"status":409,"error":"Conflict",
  "message":"Cannot accept embargo: case '...' EM state 'ACTIVE' does not allow
  an ACCEPT transition."}}
```

**Sequence of events:**

1. Coordinator proposes embargo → EM state `PROPOSED`.
2. Demo runner delivers embargo invite to all participants.
3. Finder accepts via `accept-embargo` trigger → EM state transitions
   `PROPOSED → ACTIVE`.
4. Demo runner then calls `accept-embargo` for Vendor — rejected because EM
   is already `ACTIVE`.

**Root cause:** The EM state machine treats the first `accept-embargo` from
any participant as activating the embargo globally. In multi-party cases each
participant has a local view, but the shared `VulnerabilityCase.active_embargo`
/ EM state is updated on the first accept. Subsequent accepts from other
participants see an `ACTIVE` state and are rejected.

**Expected behaviour:** Either (a) the `accept-embargo` trigger on a per-actor
basis records the local actor's acceptance without globally activating the
embargo until a quorum is reached, or (b) idempotent acceptance of an already-
`ACTIVE` embargo should succeed (return 200) rather than fail with 409.

---

## 6. `AnnounceLogEntryActivity` Coercion Failure

Severity: Low — warning only; dispatch falls through to generic handler

**Symptom:**

```text
WARNING: Could not coerce 'as_Announce' to semantic class 'AnnounceLogEntryActivity':
  3 validation errors for AnnounceLogEntryActivity
    object.caseId: Field required
    object.logObjectId: Field required
    object.eventType: Field required
```

Seen in: finder and vendor when processing outbox items containing `Announce`
activities.

**Root cause:** The `Announce` activities in the outbox were emitted for
general case events (e.g., case creation, participant join) and do not carry
the `CaseLogEntry` object structure that `AnnounceLogEntryActivity` requires.
The pattern ordering in `SEMANTICS_ACTIVITY_PATTERNS` causes a more specific
pattern to be attempted before the general one succeeds.

---

## 7. `create_note` Use Case Does Not Attach Notes to the Case

Severity: High — demo-halting failure in two-actor demo

**Symptom:**

```text
INFO:  'urn:uuid:aa50b65f-...' already stored — skipping (idempotent)
...
ERROR: ❌ Question note delivered to Vendor's DataLayer
ERROR: Two-actor demo failed: Timed out waiting for note 'urn:uuid:aa50b65f-...'
  to appear in case 'urn:uuid:4e29fdf2-...'
AssertionError: Timed out waiting for note 'urn:uuid:aa50b65f-...' to appear in
  case 'urn:uuid:4e29fdf2-...'
```

The vendor receives the note (`Create(Note)`) and logs "already stored" on the
first delivery (the note was pre-seeded by the demo runner into the vendor's
DataLayer), then the `wait_for_note_in_case` check polls the vendor's case and
times out.

**Root cause:** The `create_note` use case persists the `Note` object into the
DataLayer but does not update the `VulnerabilityCase.notes` list. The demo's
`wait_for_note_in_case` check queries `case.notes`, which remains empty. The
"already stored — skipping" idempotency path is also a separate concern: the
note is being stored before the use case runs (by the demo runner as a
pre-check), so the first delivery hits the idempotency skip and never attempts
to attach the note to the case.

**Contributing factor:** The outbox abort issue (§1) occurs immediately after
the note delivery, meaning even if subsequent re-deliveries were attempted they
are suppressed.

---

## 8. `add_activity_to_outbox`: Actor Lookup by Short UUID Fails

Severity: Low — warning only; outbox items are skipped

**Symptom:**

```text
WARNING: add_activity_to_outbox: actor '24d63c7d-6b1e-4f61-a5e1-180d27192d0b'
  not found or has no outbox field; skipping outbox.items update
```

Seen for coordinator, finder, and vendor actors across all three demos.

**Root cause:** The function receives a short UUID (e.g., `24d63c7d-...`) but
the actor is indexed in the DataLayer under its full URI
(`http://coordinator:7999/api/v2/actors/24d63c7d-...`). The lookup finds no
matching record and silently skips the outbox update.

This is consistent: it happens early (when the actor ID is first obtained as a
short UUID before the full-URI form is established in the session context) and
also at later stages of the three-actor demo.

---

## 9. Rehydration Failure: `as_Invite.target` Cannot Be Resolved

Severity: Low — warning only; dispatch proceeds with string reference

**Symptom:**

```text
WARNING: Could not rehydrate field 'target' with id '<case-uuid>' on 'as_Invite';
  keeping string reference.
```

Seen in: finder and vendor (three-actor, multi-vendor).

**Root cause:** The `Invite` activity's `target` is a case UUID. The receiving
actor's DataLayer does not yet contain the `VulnerabilityCase` record (it has
not been synced or announced), so rehydration cannot expand the ID to a full
object. This is expected in some race conditions but the repeated occurrence
(three retries per poll cycle) suggests the case is never synced to the
receiving actor's DataLayer.

---

## 10. `PersistCase`: Duplicate Case Creation Warnings

Severity: Low — idempotency handled but noisy

**Symptom:**

```text
WARNING: PersistCase: Case urn:uuid:<id> already exists:
  record with id_='<id>' already exists in 'VulnerabilityCase'
```

Seen in: finder, case-actor (all demos).

**Root cause:** Multiple actors receive the `CreateCase` activity via outbox
delivery. Each runs `PersistCase` which attempts to write the record; the
second actor to write gets a duplicate-key rejection. The warning is handled
(not fatal), but it indicates that `PersistCase` is not checking for an
existing record before attempting an insert. An `upsert` or pre-check would
eliminate the noise.

---

## 11. `EngageCaseBT`: Silent BT Failure with No Diagnostic Detail

Severity: Medium — silent failure; no actionable log detail

**Symptom:**

```text
INFO:  BT execution completed: Status.FAILURE after 1 ticks -
WARNING: EngageCaseBT did not succeed for actor '...' / case '...':
```

(Note the trailing colon with no message.)

Seen in: coordinator (three-actor), vendor (multi-vendor).

**Root cause:** The BT failure message is constructed as
`f"EngageCaseBT did not succeed ... : {detail}"` where `detail` is empty
string. The BT returns `FAILURE` but the reason is not propagated out of the
tree to the log message. This makes debugging the underlying cause impossible
from logs alone.

---

## 12. `SubmitReportReceivedUseCase`: Missing `Offer.target` Suppresses Auto-Case-Creation

Severity: Medium — silent skip; demo works around it with manual trigger

**Symptom:**

```text
WARNING: SubmitReportReceivedUseCase: vendor actor_id not available
  (Offer.target not set) for report '<id>' — skipping case creation
```

Seen in: coordinator (three-actor).

**Root cause:** In the three-actor scenario the finder submits the report to
the coordinator with no `target` on the Offer (the coordinator is the MPCVD
coordinator, so the "vendor" is not known at submission time). The use case
skips automatic case creation and the demo script works around this with an
explicit `create-case` trigger call.

The issue is that in coordinator-mediated MPCVD, the coordinator receives a
report without a pre-specified vendor and should be able to create a case and
add vendors later. The current code path requires `Offer.target` to be set to
proceed, which is the two-actor assumption leaking into the three-actor flow.

---

## Summary Table

| # | Area | Severity | Affected Demos |
|---|------|----------|----------------|
| 1 | Outbox: `target` field serialization (inline object vs. string URI) | High | All |
| 2 | Activity `name` contains Python `repr()` of domain object | Medium | Three-actor, multi-vendor |
| 3 | Semantic extraction: `Accept(Invite)` → `validate_report` (wrong) | High | Three-actor, multi-vendor |
| 4 | Coercion: missing fields in nested `Invite` for Accept activities | Medium | Three-actor, multi-vendor |
| 5 | Embargo EM state: multi-party `accept-embargo` 409 Conflict | High | Three-actor, multi-vendor |
| 6 | `AnnounceLogEntryActivity` coercion warning | Low | Two-actor, multi-vendor |
| 7 | `create_note`: Note not attached to case; timeout failure | High | Two-actor |
| 8 | `add_activity_to_outbox`: short UUID vs. full-URI actor lookup | Low | All |
| 9 | Rehydration: `as_Invite.target` case not found | Low | Three-actor, multi-vendor |
| 10 | `PersistCase`: duplicate warning on create | Low | All |
| 11 | `EngageCaseBT`: silent failure, no detail in log message | Medium | Three-actor, multi-vendor |
| 12 | `SubmitReportReceivedUseCase`: `Offer.target` required for case creation | Medium | Three-actor |

---

## Priority Fixes

The following three issues are blocking every demo:

1. **§1 — Outbox `target` serialization.** Dehydrate case objects to URI
   strings when constructing outbound activities. This will also fix §2 as
   a side effect (the `name` field repr comes from the same inline-object
   anti-pattern).

2. **§5 — Multi-party embargo acceptance.** Record each participant's
   acceptance separately without immediately transitioning the shared EM
   state; or accept an already-`ACTIVE` embargo as idempotent success.

3. **§7 — `create_note` case attachment.** After persisting the `Note`,
   update `VulnerabilityCase.notes` to include the new note ID, then
   `dl.save(case)`.

Issue §3 is the next highest priority because it results in repeated inbox
abort cycles and silent data loss in multi-actor deployments.
