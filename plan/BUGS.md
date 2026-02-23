# Bugs to fix

Items in this file supersede IMPLEMENTATION_PLAN.md.

---

## Case creation workflow currently neglects adding case creator as first participant and case owner

This is a problem in two parts:

1) In `initialize-case-demo.py`, the vendor validates the report, creates a 
   case, and eventually adds the reporter as a participant. But when a case 
   is created, the creator should add themselves first as a participant, 
   then add the reporter as a participant. This is because the creator needs 
   to be a participant in order to perform any actions on the case.
2) The creator should also indicated as the case owner of the new case. It 
   seems that `attributedTo` might be the right property to use for this, 
   but please confirm that this is semantically correct and that it is being 
   used correctly in the codebase. This part might be a non-issue, this is more
   of a check to confirm that it's behaving as intended since you will be 
    working with the case creation workflow in solving the first part of this issue.

---

## CreateParticipant activity "name" attribute is misleading

The "name" of the Create when creating a participant is misleading:
"name": "https://vultron.example/organizations/vendorco Create https://vultron.example/users/finndervul",
but it should be more like f"{actor_id} Create CaseParticipant 
{participant_id} from {other_actor_id}" so that it's obvious that this is 
creating a participant from an actor and not an actor itself. For log 
correlation, it may also be useful to include the case ID, which should be 
present in the `context` of the `Create` activity.

---

## Clarify intent in all demos

### Use INFO level log messages to declare what step of the workflow the demo is executing
Many demo scripts execute a workflow that is comprised of multiple steps. 
For example, the `initialize-case-demo.py` script executes the following steps:
1) Vendor receives report
2) Vendor validates report
3) Vendor creates case
4) Vendor adds themselves as participant and case owner
5) Vendor adds reporter as participant
6) etc.

In order to make this stand out in demo logs, it would be helpful if each of 
these steps were precede by an INFO level log message that declares what step
of the workflo the demo is executing. Prefixing the log message with a relevant 
emoji would also help it stand out in the logs. 🚥 for the beginning of a step,
🟢for successful completion of a step, 🟡for warnings, and 🔴for a failed 
step (if applicable).

Hint: These could be implemented as a context manager that takes a string
describing the step and logs the "before" message on entry and the "after" 
message on exit, with appropriate emojis. This would make it easy to wrap any 
block of code in a step declaration without having to write separate log 
messages before and after the block.


### Use INFO level log messages to clarify intent of side effect checks

Extending the above, many demo scripts use raw datalayer API calls to 
verify that side effects are
occurring as expected. This is good. But it would help if there were INFO level
log messages just before and after these API calls to clarify what the demo 
is looking for and what it found. That way, if we eventually want to turn off
the DEBUG level logging, it will still be clear from the logs that the demo 
did something, then checked for something, and found what it expected (or 
didn't find what it expected). Use of contextually relevant emojis at the 
beginning of those log messages would also help them stand out in the logs.
Suggesting 📋for the "before" to indicate a check is coming, and ✅ for the 
"after" to indicate a successful check, and ❌ to indicate a failed check.

Hint: This could be an extension of the context manager suggested in the 
previous item, or it could be a separate context manager that is 
specifically for these checks. 
