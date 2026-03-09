# Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate
insights, issues, and learnings during the implementation process.

Add new items below this line

---
## ~~TB prefix reused in specs~~

> ✅ Resolved: `triggerable-behaviors.md` requirements renamed to `TRIG-`
> prefix. `specs/README.md` updated with a prefix registry table. External
> reference in `notes/do-work-behaviors.md` updated from TB-02-003 →
> TRIG-02-003.

~~The TB prefix is currently used in specs for both `testability.md` and
`triggerable-behaviors.md`. This is confusing and must be resolved by
picking a different prefix for one of them. The `specs/README.md` file
should be updated to reflect the prefix for each file so that in the future
we can avoid reusing existing prefixes.~~

## ~~Triggers are intended to be synchronous for the caller~~

> ✅ Captured: `specs/triggerable-behaviors.md` TRIG-01-005.

~~Triggerable behaviors are intended to be synchronous for the caller, which
should mean that there's no async concerns about:~~

~~`TB-04-001` A successful trigger response SHOULD include the resulting
ActivityStreams activity in the response body under an `activity` key~~

~~This is important to clarify because while inbound message handling is
eventually meant to be asynchronous, the triggerable behavior interface is
intended to be synchronous for the caller.~~

## ~~P30-1 outbox-diff strategy for retrieving the resulting activity~~

> ✅ Captured: `notes/triggerable-behaviors.md` "Resolved Design Decisions:
> Trigger Implementation (P30-1 through P30-3)" section.

~~In `trigger_validate_report`, the BT's `UpdateActorOutbox` node writes the
new activity_id to `actor.outbox.items` in the DataLayer. To return the
resulting activity in the response, the endpoint snapshots the outbox ID
set before BT execution, then diffs after execution to find the newly added
activity ID. This avoids modifying the bridge or BT nodes for a specific
trigger use case. The diff is a set subtraction on string IDs, so it is
robust to multiple concurrent triggers only if each produces a distinct
activity ID (which is guaranteed by the UUID-based IDs used in the BT nodes).~~

## ~~Black format before full test suite~~

> ✅ Captured: `AGENTS.md` "Commit Workflow" section already covers this.

~~Running `black` is fast, running the full test suite is not. There is no
reason to run the full test suite, then run black, then run the full test
suite again. Just do the `black` formatting first then run the full test suite.~~

## ~~Be more deliberate about writing DRY code~~

> ✅ Captured: `specs/code-style.md` CS-09-001 and CS-09-002; `AGENTS.md`
> "Reuse request/response models before creating new ones" guidance.

~~Try to avoid just copying and pasting code and changing a few lines. Instead,
take the time to refactor and extract common logic into reusable functions or
classes.~~


## ~~P30-2: invalidate-report and reject-report triggers are procedural~~

> ✅ Captured: `notes/triggerable-behaviors.md` "Resolved Design Decisions:
> Trigger Implementation (P30-1 through P30-3)" section.

~~Unlike `validate-report` (which uses a BT tree because of the case creation
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
`@field_validator` on `RejectReportRequest.note`.~~

## ~~When implementing routers with request or response models be DRY~~

> ✅ Captured: `specs/code-style.md` CS-09-002; `AGENTS.md` "Reuse
> request/response models before creating new ones" guidance.

~~When implementing routers that have request or response models, try to be DRY
by checking existing models to see if they can be reused or extended rather
than creating new ones from scratch. For example, `ValidateReportRequest`
and `InvalidateReportRequest` are identical, and `RejectReportRequest` is
almost identical except for the required `note` field. This can be
refactored into a simpler base model that the specific request models can
inherit from.~~


## ~~P30-3: engage-case and defer-case triggers are procedural~~

> ✅ Captured: `notes/triggerable-behaviors.md` "Resolved Design Decisions:
> Trigger Implementation (P30-1 through P30-3)" section.

~~Like P30-2, `engage-case` and `defer-case` are implemented procedurally.
The trigger represents the LOCAL actor deciding to engage or defer (outgoing),
not reacting to a remote actor's state transition (which is the receive-side
handled by `EngageCaseBT`/`DeferCaseBT`). Both endpoints:

- Share a `CaseTriggerRequest` model with `case_id` field.
- Use a `_resolve_case()` helper that reads the case from DataLayer and
  returns 404 if absent or 422 if the object is not a `VulnerabilityCase`.
- Create `RmEngageCase` (Join) or `RmDeferCase` (Ignore) activity directly.
- Call `_update_participant_rm_state()` to update the actor's own
  `CaseParticipant.participant_statuses` in the DataLayer. Note: participants
  are stored as ID strings in `case.case_participants`, so the helper reads
  each participant object from the DataLayer before updating it.
- Update is persisted to the participant document, not the case document, to
  follow the existing pattern in the BT nodes.
- If no participant record exists for the actor, a WARNING is logged and the
  endpoint still returns 202 with the activity (non-blocking).~~

## ~~Triggered behaviors do not belong in trigger endpoints~~

> ✅ Captured: `AGENTS.md` "Trigger behavior logic belongs outside the API
> router" guidance added; `specs/architecture.md` ARCH-08-001.

~~Because we're going to be doing both an API-based and command-line based
implementation of triggered behaviors, we don't want the logic for the
triggered behaviors to be tightly coupled to the API endpoints. Instead, the API
endpoints should just be responsible for handling the request, validating it, and
then invoking the appropriate behavior (whether that's a BT or procedural
code) provided in a separate module. This keeps the concerns separated (api
routers are just for translating API to internal calls, then behavior
implementations are in separate modules that can be called from both API and
CLI contexts).~~

## ~~Consider "Ports and Adapters" architecture for triggerable behaviors~~

> ✅ Captured: `notes/architecture-ports-and-adapters.md` (full hexagonal
> architecture spec), `notes/architecture-review.md` (violation inventory),
> `specs/architecture.md` (formal requirements ARCH-01 to ARCH-08),
> `AGENTS.md` "Hexagonal Architecture" section.

~~This seems like a good use case for a "Ports and Adapters" (Hexagonal)
architecture, where the triggerable behavior implementations are the core
domain logic, and the API endpoints and CLI commands are just different
adapters that call into that core logic. This would allow us to keep the
core behavior implementations decoupled from the specific interfaces (API
vs CLI) and make it easier to maintain and extend in the future. The core
logic can be implemented in a way that is agnostic to how it's triggered,
and then the API and CLI can just be thin layers that translate their
respective inputs into calls to the core logic.~~

