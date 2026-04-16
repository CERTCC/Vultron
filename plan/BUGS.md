# Bugs to fix

Items in this file supersede IMPLEMENTATION_PLAN.md.

Use format `BUG-YYMMDDXX` for bug IDs, where `YYMMDD` is the date the bug
was identified and `XX` is a sequential number for that day. For example,  
the first bug identified on March 26, 2026 would be `BUG-2026032601`.
Include a brief description in the title, and provide detailed reproduction
steps, root cause analysis, and resolution steps in the body.

---

## BUG-26041601 Unexpected dispatch errors in multi-vendor demo — **FIXED**

I ran `make integration-test-multi-vendor > multi-vendor-log.txt` and found
the following error:

```text
% grep -i error *log.txt    
multi-vendor-log.txt:coordinator-1  | ERROR:    Unexpected error dispatching activity_id=urn:uuid:50efe8e3-9ca6-4648-9e32-861b84888bae actor_id=http://vendor:7999/api/v2/actors/2d5b03e8-2392-4cda-a4fb-da2bf28ec514 semantics=submit_report
multi-vendor-log.txt:coordinator-1  | AttributeError: 'NoneType' object has no attribute 'startswith'
```

**Root cause**: `OfferCaseOwnershipTransferActivity` was built with
`object_=case.id_` (a bare string URI) in both demo files. When the
coordinator received the offer, rehydration failed silently (the case wasn't
in the coordinator's DataLayer yet), leaving `object_` as a string. The
`ActivityPattern._match_field` conservatively returns `True` for any string
URI, so both `SUBMIT_REPORT` and `OFFER_CASE_OWNERSHIP_TRANSFER` matched;
since `SUBMIT_REPORT` appeared first in `SEMANTICS_ACTIVITY_PATTERNS`, the
wrong use case was dispatched, crashing in `db_record.py`.

**Resolution**: Enforced at the model level — changed
`OfferCaseOwnershipTransferActivity.object_` from `VulnerabilityCaseRef`
(`VulnerabilityCase | str | None`) to `VulnerabilityCase | None`. This
requires the inline case to be sent, removing the pattern-matching ambiguity
at its source. Fixed the two demo files (`multi_vendor_demo.py`,
`transfer_ownership_demo.py`) to pass `object_=case` instead of
`object_=case.id_`. Added two regression tests in
`test/test_semantic_activity_patterns.py`.

## BUG-26041602 CaseActor is not logging CaseLogEntry sync messages

I notice that in the logs, `case-actor-1` appears to be receiving and
dispatching incoming messages, but I do not see any log entries indicating
that it is emitting `Announce` messages carrying `CaseLogEntry` activities
or that these are being delivered. These `Announce` messages are the primary
way for the `CaseActor` to sync the case log state to participants, so this
is a critical issue to resolve.
