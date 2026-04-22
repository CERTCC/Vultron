# Bugs to fix

Items in this file supersede IMPLEMENTATION_PLAN.md.

Use format `BUG-YYMMDDXX` for bug IDs, where `YYMMDD` is the date the bug
was identified and `XX` is a sequential number for that day. For example,
the first bug identified on March 26, 2026 would be `BUG-26032601`.
Include a brief description in the title, and provide detailed reproduction
steps, root cause analysis, and resolution steps in the body.

---

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

**Root cause:** The generic AS2 parser only pre-expanded the outer inline
`object`, so nested `Accept(Invite(...))` and `Reject(Invite(...))` payloads
lost actor/stub subtype fidelity before semantic extraction. That left inbound
responses classified as `unknown` or semantically incomplete, and invite
responses also omitted `inReplyTo` unless callers set it manually.

**Resolution:** The parser now recursively expands nested inline AS2 dicts to
their vocabulary classes, preserving actor subtypes and `VulnerabilityCase`
stub objects through semantic extraction and SQLite round-trips. Invite
accept/reject activities now default `inReplyTo` to the original invite ID, and
regression coverage was added for parser extraction, SQLite coercion, and the
accept-case-invite trigger response.

Status: FIXED — 2026-04-22.

## BUG-26042204 — three-actor demo never activates the case embargo after owner-gated accept flow — NEW

**Symptoms:** The full test suite with integration tests enabled
(`uv run pytest -m "" --tb=short`) currently fails with:

```text
FAILED test/demo/test_three_actor_demo.py::TestRunThreeActorDemo::test_full_workflow_succeeds
E   AssertionError: Expected ACTIVE embargo state, found PROPOSED
```

The failure is raised from
`vultron/demo/scenario/three_actor_demo.py:447` inside
`verify_case_actor_case_state()`.

**Likely root cause:** The demo scenario still has the **finder** and
**vendor** call the `accept-embargo` trigger, but never has the **case owner**
accept.

(Except note that as the case creator, the vendor in the scenario *is* the
case owner, so there's a logic gap here that will need to be resolved in the
fix.)

After the recent owner-gated embargo trigger change,
`SvcAcceptEmbargoUseCase` only advances the shared case EM state when the
triggering actor is the case owner (`_is_case_owner()` in
`vultron/core/use_cases/triggers/embargo.py`). Non-owner accepts now record
participant consent without changing `case.current_status.em_state`, so the
scenario can finish with the authoritative case still in `PROPOSED`.

**Likely components involved:**

- `vultron/demo/scenario/three_actor_demo.py`
- `vultron/core/use_cases/triggers/embargo.py`
- `test/demo/test_three_actor_demo.py`

**Brief description:** The three-actor demo orchestration appears to be out of
sync with the new embargo-accept semantics. It still expects participant
acceptances alone to drive the authoritative case into `EM.ACTIVE`.

Status: NEW — added 2026-04-22.
