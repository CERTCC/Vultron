# Bugs to fix

Items in this file supersede IMPLEMENTATION_PLAN.md.

Use format `BUG-YYMMDDXX` for bug IDs, where `YYMMDD` is the date the bug
was identified and `XX` is a sequential number for that day. For example,  
the first bug identified on March 26, 2026 would be `BUG-2026032601`.
Include a brief description in the title, and provide detailed reproduction
steps, root cause analysis, and resolution steps in the body.

---

## BUG-26041601 Unexpected dispatch errors in multi-vendor demo

I ran `make integration-test-multi-vendor > multi-vendor-log.txt` and found
the following error:

```text
% grep -i error *log.txt    
multi-vendor-log.txt:coordinator-1  | ERROR:    Unexpected error dispatching activity_id=urn:uuid:50efe8e3-9ca6-4648-9e32-861b84888bae actor_id=http://vendor:7999/api/v2/actors/2d5b03e8-2392-4cda-a4fb-da2bf28ec514 semantics=submit_report
multi-vendor-log.txt:coordinator-1  | AttributeError: 'NoneType' object has no attribute 'startswith'
```

## BUG-26041602 CaseActor is not logging CaseLogEntry sync messages

I notice that in the logs, `case-actor-1` appears to be receiving and
dispatching incoming messages, but I do not see any log entries indicating
that it is emitting `Announce` messages carrying `CaseLogEntry` activities
or that these are being delivered. These `Announce` messages are the primary
way for the `CaseActor` to sync the case log state to participants, so this
is a critical issue to resolve.
