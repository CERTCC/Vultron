---
title: Bug #2762's body named a method and trigger condition that did not exist
type: learning
timestamp: 2026-09-01
source: ISSUE-2762
signal: process-issue
---

The defect in #2762 was real and still present, but four details in the body did
not survive contact with the code. Worth noting because each one could have sent
an agent down a wrong path or — worse — to a premature "cannot reproduce, close".

| Issue body said | Actually |
|---|---|
| `_prepare()` at `embargo.py:266` | No `_prepare()` on this class; the code is in `execute()`, at line 301 |
| falls back to `dl.actor_id` | Indirectly — via `resolve_receiving_actor_id()`, so grepping `dl.actor_id` in `embargo.py` finds nothing |
| recording the case actor's PEC as SIGNATORY | `PEC_Trigger.INVITE` → `PEC.INVITED`, not SIGNATORY |
| triggers when `receiving_actor_id` is `None` | Triggers whenever the processing store is not the addressee's; `None` is one route, not the condition |
| `invite.py` has an explicit guard at the same location | The file is `received/actor/invite.py`; its guard exists for the opposite reason (the invitee does *not* own the case store) and is deliberately not converted |

Two things made the pre-claim verification gate succeed anyway: searching for
the *symptom* (an invitee identity derived from the receiving actor) rather than
the quoted line number, and `git log -S` on the fix that introduced it
(`91c23a4e0`, #2446, one day before the issue was filed).

The generalisable rule, which the bugfix skill already states and this session
confirms: treat the issue body as a symptom report, not a map. Line numbers and
method names in a body written weeks earlier are the first things to rot. Verify
by behaviour, and use `git log -S` to find the introducing commit — that also
tells you the real trigger condition, which here was broader than the reporter
believed.
