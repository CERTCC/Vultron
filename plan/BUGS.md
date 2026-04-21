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

Status: NEW — added 2026-04-17.

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
