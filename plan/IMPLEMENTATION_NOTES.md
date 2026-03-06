# Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate
insights, issues, and learnings during the implementation process.

Add new items below this line

---
## TB prefix reused in specs

The TB prefix is currently used in specs for both `testability.md` and 
`triggerable-behaviors.md`. This is confusing and must be resolved by 
picking a different prefix for one of them. The `specs/README.md` file 
should be updated to reflect the prefix for each file so that in the future 
we can avoid reusing existing prefixes.

## Triggers are intended to be synchronous for the caller

Triggerable behaviors are intended to be synchronous for the caller, which 
should mean that there's no async concerns about:

`TB-04-001` A successful trigger response SHOULD include the resulting
  ActivityStreams activity in the response body under an `activity` key

This is important to clarify because while inbound message handling is 
eventually meant to be asynchronous, the triggerable behavior interface is 
intended to be synchronous for the caller.

## P30-1 outbox-diff strategy for retrieving the resulting activity

In `trigger_validate_report`, the BT's `UpdateActorOutbox` node writes the
new activity_id to `actor.outbox.items` in the DataLayer. To return the
resulting activity in the response, the endpoint snapshots the outbox ID
set before BT execution, then diffs after execution to find the newly added
activity ID. This avoids modifying the bridge or BT nodes for a specific
trigger use case. The diff is a set subtraction on string IDs, so it is
robust to multiple concurrent triggers only if each produces a distinct
activity ID (which is guaranteed by the UUID-based IDs used in the BT nodes).

## Black format before full test suite

Running `black` is fast, running the full test suite is not. There is no 
reason to run the full test suite, then run black, then run the full test 
suite again. Just do the `black` formatting first then run the full test suite.

## Be more deliberate about writing DRY code

Try to avoid just copying and pasting code and changing a few lines. Instead,
take the time to refactor and extract common logic into reusable functions or
classes.


## P30-2: invalidate-report and reject-report triggers are procedural

Unlike `validate-report` (which uses a BT tree because of the case creation
side effects), `invalidate-report` and `reject-report` are implemented
procedurally. Per the AGENTS.md guidance, simple linear workflows with no
branching should use procedural code rather than BTs. Both endpoints:
- Create an `RmInvalidateReport` (TentativeReject) or `RmCloseReport` (Reject)
  activity directly.
- Store the activity via `dl.create()`.
- Update status via `set_status()` (in-memory STATUS dict, not DataLayer).
- Append the activity ID to `actor.outbox.items` and persist with `dl.update()`.
- Return `{"activity": activity.model_dump(by_alias=True, exclude_none=True)}`.

The shared `_add_activity_to_outbox()` helper was extracted to DRY up the
outbox append pattern across multiple trigger endpoints.

For `reject-report`, the `note` field is required in the request body
(TB-03-004). An empty `note` string logs a WARNING but is accepted (the spec
says the value SHOULD be non-empty, not MUST). This is enforced via a
`@field_validator` on `RejectReportRequest.note`.

## When implementing routers with request or response models be DRY

When implementing routers that have request or response models, try to be DRY
by checking existing models to see if they can be reused or extended rather 
than creating new ones from scratch. For example, `ValidateReportRequest` 
and `InvalidateReportRequest` are identical, and `RejectReportRequest` is 
almost identical except for the required `note` field. This can be 
refactored into a simpler base model that the specific request models can 
inherit from.

