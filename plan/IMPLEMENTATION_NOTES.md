## Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate
insights, issues, and learnings during the implementation process.

Append new items below any existing ones, marking them with the date and a
header.

---

### 2026-04-07 Gap analysis observations (refresh #69)

~~**VOCAB-REG-1 confirmed open**: The vocabulary registry still uses manual~~
~~`@activitystreams_object` / `@activitystreams_activity` / `@activitystreams_link`~~
~~decorators; no auto-registration mechanism exists yet.~~
→ Already tracked as plan task VOCAB-REG-1 in `plan/IMPLEMENTATION_PLAN.md`;
status annotation "Confirmed still open as of 2026-04-07" added there.

## Treat-warnings-as-errors policy in pytest

~~`pyproject.toml` sets `filterwarnings = ["error"]` which causes any Python~~
~~`warnings.warn()` call during the test session to be treated as a test error.~~
~~**No warnings should be present before committing changes.** This is~~
~~intentional and enforced by CI.~~

~~**Scope caveat**: This policy applies to `warnings.warn()` calls captured~~
~~by pytest's warning machinery. It does NOT catch "Exception ignored in:"~~
~~messages printed by the Python interpreter at process teardown (e.g.,~~
~~`ResourceWarning: unclosed file ...`). Those warnings arise from finalizers~~
~~(`__del__`) running after pytest exits and are not visible to `filterwarnings`.~~
~~They are still bugs (see BUG-2026040103) — they just require a different fix~~
~~(explicitly closing resources in fixtures) rather than a `filterwarnings`~~
~~adjustment.~~

~~**Rule for agents**: Before committing, run `uv run pytest --tb=short 2>&1`~~
~~and verify the summary line shows no failures and no "warnings" count. Also~~
~~inspect the output for "ResourceWarning" or "Exception ignored in:" messages,~~
~~which signal unclosed resources that should be filed as bugs if not already~~
~~tracked.~~
→ Base policy captured in `specs/tech-stack.md` IMPL-TS-07-006;
ResourceWarning scope caveat and agent rule added to `AGENTS.md`
"Pytest filterwarnings Does Not Catch All Warnings".

## 2026-04-06 Priority 310 feedback tasks

### Open question: finder participant lifecycle (D5-6-STATE)

~~When the vendor receives a finder's `OfferReport`, should a `CaseParticipant`~~
~~record for the finder be created immediately (before a `VulnerabilityCase`~~
~~exists), or deferred until case creation? Current behavior defers finder~~
~~participant creation until `engage-case`. The D5-6-STATE task implies the~~
~~finder's RM state (`RM.ACCEPTED`) should be tracked from the moment the~~
~~report is received, even before a case exists. This may require a pre-case~~
~~participant status record, or a revision to the `CaseParticipant` lifecycle~~
~~so that it is always created at report receipt and retroactively attached to~~
~~the case during case creation.~~

#### Reflection

~~`CaseParticipant` is perhaps misleading, as the actual lifecycle is that a~~
~~work starts on a `report` and some reports turn into `cases`. (This is good~~
~~caterpillar/butterfly metamorphosis analogy.) The reality is that a "report"~~
~~needs to be treated as a sort of proto-case that has a reporter and a~~
~~receiver, each of whom are participants in the work of processing the report,~~
~~even if that report never fully emerges into a case. The RM, EM, and CS~~
~~state machines all have meaning in both the pre-case (report) and post-case~~
~~(case+report) stages, so it makes sense to have participant records created~~
~~for reporter and receiver before case creation, and they can be~~
~~retroactively linked to a case if one is created. However, we currently~~
~~don't really have a concept of "report participant", and so there's no~~
~~obvious linkage between a case participant object and the report object. It~~
~~seems like it's probably pretty easy to do using the `context` field of the~~
~~participant record, and then when moving the participant to a case you just~~
~~update the `context` of the participant to point to the case rather than the~~
~~report (the report is added to the case as part of the case creation, so~~
~~this should be a straightforward task to complete at case creation.)~~
→ Captured in `notes/case-state-model.md` "Report as Proto-Case: Finder
Participant Lifecycle" and tracked as `plan/IMPLEMENTATION_PLAN.md` FINDER-PART-1.

### Open question: vendor default embargo for D5-6-WORKFLOW

~~D5-6h requires the vendor default embargo to be initialized as part of case~~
~~creation. The relevant docs and specs (`docs/topics/process_models/em/defaults.md`,~~
~~`docs/topics/process_models/model_interactions/rm_em.md`, VP-13-*) exist, but~~
~~the vendor-default-embargo initialization may not be fully implemented yet.~~
~~The D5-6-WORKFLOW task should verify spec coverage and existing implementation~~
~~before coding begins.~~

#### Reflection

~~Default embargo is not really a thing yet in the code, although it exists as~~
~~a concept in the docs and specs. What we have in mind is that the Actor's~~
~~profile will include a blob that defines the default embargo parameters for~~
~~that actor, perhaps as simple as a duration (e.g., 90 days) expressed in a~~
~~standard format. Thoughts on the format follow:~~
~~Refined recommendation (what you should actually do)~~

##### Wire format

~~ISO 8601 duration strings, Example: "P90D"~~

~~Constrain the grammar to avoid ambiguous durations (1M could be 28, 29, 30,~~
~~or 31 days depending on context, 1Y could be 365 or 366 days depending on context).~~

~~MUST use only fixed-length units (D, H, M, S)~~
~~SHOULD use only day units for simplicity~~
~~MAY use time units if needed for highly-granular embargos (but discouraged~~
~~for typical use)~~
~~MUST NOT allow Y, M (date part)~~

##### Model structure

~~Use:~~
~~duration: "P90D"~~

##### Pydantic strategy

~~Internal: timedelta~~
~~External: ISO 8601 string via serializer~~

~~Semantics: Define explicitly: durations are absolute elapsed time, not calendar-relative~~
→ Duration format spec created as `specs/duration.md` (DUR-01 through DUR-07).
`specs/embargo-policy.md` updated to use ISO 8601 duration fields.
Implementation tracked as `plan/IMPLEMENTATION_PLAN.md` EMBARGO-DUR-1.

### Risk: D5-6-STORE and nested Pydantic serialization

~~The datalayer storage investigation should check whether the current `dl.save()`~~
~~path for activities preserves or expands nested Pydantic objects at~~
~~serialization time. The `AGENTS.md` pitfall note on `VulnerabilityCase.case_activity`~~
~~shows that enum coverage failures cause fallback to raw `Document` objects;~~
~~similar issues may affect activity serialization and should be checked as part~~
~~of D5-6-STORE.~~
→ D5-6-STORE is ✅ complete. Nested serialization behavior is documented
in `AGENTS.md` "VulnerabilityCase.case_activity Cannot Store Typed Activities"
pitfall note.

---

## 2026-04-06 D5-6i–l feedback tasks (refresh #68)

~~Continued reviewer feedback from `notes/two-actor-feedback.md` items D5-6i~~
~~through D5-6l. Items D5-6a–h were addressed in the prior four tasks (D5-6-LOG,~~
~~D5-6-STATE, D5-6-STORE, D5-6-WORKFLOW — all ✅). Items D5-6i–l introduce new~~
~~work, particularly D5-6l which raises a fundamental concern about demo~~
~~correctness.~~

New plan tasks:

~~- **D5-6-DUP**: Investigate/fix duplicate VulnerabilityReport warning (D5-6i).~~
~~- **D5-6-LOGCTX**: Improve outbox activity log messages with human-readable~~
~~  context (D5-6j).~~
~~- **D5-6-TRIGDELIV**: Fix trigger endpoints to call `outbox_handler` after~~
~~  use-case execution (D5-6k).~~
~~- **D5-6-DEMOAUDIT**: Audit and refactor all demos for protocol compliance~~
~~  (D5-6l).~~
→ All four tasks added to and completed in `plan/IMPLEMENTATION_PLAN.md`
(D5-6-DUP ✅, D5-6-LOGCTX ✅, D5-6-TRIGDELIV ✅, D5-6-DEMOAUDIT ✅).

### Critical finding: trigger endpoints do not deliver outbox activities

~~**Confirmed gap**: All three trigger routers (`trigger_report.py`,~~
~~`trigger_case.py`, `trigger_embargo.py`) execute use-case logic (which may~~
~~queue activities to the actor's outbox via `datalayer.record_outbox_item()`)~~
~~but do NOT schedule `outbox_handler` as a FastAPI `BackgroundTask`.~~

~~In contrast, the inbox endpoint (`actors.py` line 470) correctly calls~~
~~`inbox_handler` as a `BackgroundTask`, and `inbox_handler` (line 184) calls~~
~~`outbox_handler` after processing. The outbox POST endpoint (line 534) also~~
~~schedules `outbox_handler`. Triggers bypass both paths.~~

~~**Impact**: When the vendor validates a report via `POST /trigger/validate-report`,~~
~~the BT generates `CreateCaseActivity`, `Add(CaseParticipant)`, and~~
~~`AnnounceEmbargo` activities and queues them to the vendor's outbox. But those~~
~~activities are never delivered to the finder because `outbox_handler` is never~~
~~called. The finder only receives these messages if:~~

~~1. A subsequent inbox activity arrives for the vendor (triggering~~
~~   `inbox_handler` → `outbox_handler`), or~~
~~2. Someone manually POSTs to the vendor's outbox endpoint.~~

~~This violates `specs/outbox.md` OX-03-001 ("Activities in an actor's outbox~~
~~MUST be delivered to recipient inboxes") and OX-03-002 ("Delivery MUST occur~~
~~after the generating handler completes").~~

~~**Fix**: Add `BackgroundTasks` dependency to all trigger endpoint functions~~
~~and schedule `outbox_handler` after use-case execution. This is tracked as~~
~~task D5-6-TRIGDELIV.~~
→ Fixed in D5-6-TRIGDELIV ✅ (see `plan/IMPLEMENTATION_PLAN.md`).

### D5-6l: demo protocol compliance audit (significant)

~~D5-6l raises the most consequential concern: the multi-actor demos may be~~
~~demonstrating "puppeteered" workflows rather than genuine protocol-driven~~
~~behavior. Key observations from the gap analysis:~~

~~**Two-actor demo** (post D5-6-WORKFLOW): The validate-report BT now automates~~
~~case creation, participant setup, embargo initialization, and notification~~
~~activity generation. However, because trigger→outbox delivery is broken~~
~~(D5-6-TRIGDELIV), the finder never actually receives those notifications in a~~
~~multi-container run. The demo-runner also manually posts notes via~~
~~`post_to_inbox_and_wait()` rather than using trigger endpoints.~~

~~**Three-actor demo**: Uses `engage-case` and `propose-embargo` trigger~~
~~shortcuts in the demo-runner where the protocol flow should be automatic~~
~~(BT-driven after invitation acceptance). The demo-runner is doing intermediate~~
~~steps that should be consequences of primary events.~~

~~**Multi-vendor demo**: Same pattern as three-actor — multiple trigger shortcuts~~
~~for `validate-report`, `engage-case`, and `propose-embargo` where the protocol~~
~~expects automated behavior.~~

~~**Single-actor demos**: Already protocol-compliant (direct activity posts).~~
~~No changes needed.~~

~~**Dependency chain**: D5-6-TRIGDELIV → D5-6-DEMOAUDIT. Without trigger→outbox~~
~~delivery, the demo refactoring cannot verify end-to-end message flow.~~

### Where the BT automation is sufficient vs insufficient

~~**Sufficient** (no demo-runner shortcut needed):~~

~~- validate-report → case creation → participant setup → embargo init →~~
~~  notification queuing (7-node BT, fully automated)~~

~~**Insufficient** (demo-runner must still trigger or inject):~~

~~- submit-report: Finder must trigger this (correct — a primary event)~~
~~- validate-report: Vendor must trigger this (correct — a primary event)~~
~~- Note exchange: No BT automation for ad-hoc notes (acceptable — notes are~~
~~  actor-initiated primary events)~~
~~- Invitation acceptance: The `AcceptInviteActorToCaseReceivedUseCase` handles~~
~~  the received message, but engagement (RM→ACCEPTED) requires a separate~~
~~  `engage-case` trigger in the current implementation. The protocol docs~~
~~  suggest that accepting an invitation should automatically advance RM state,~~
~~  but the current BT does not do this.~~
~~- Embargo proposal: After case creation, the vendor BT initializes a default~~
~~  embargo, but in three-actor/multi-vendor scenarios the coordinator must~~
~~  explicitly propose via trigger. This is correct for the coordinator-mediated~~
~~  flow but may need a BT sequence for the case-creation-includes-embargo~~
~~  pattern.~~
→ BT automation analysis captured in `notes/protocol-event-cascades.md`;
remaining gaps tracked as D5-6-AUTOENG, D5-6-NOTECAST, D5-6-EMBARGORCP,
D5-6-CASEPROP in `plan/IMPLEMENTATION_PLAN.md`.
