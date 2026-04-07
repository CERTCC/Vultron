## Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate
insights, issues, and learnings during the implementation process.

Append new items below any existing ones, marking them with the date and a
header.

---

## 2026-04-07 Current active priority (refresh #69)

**PRIORITY-310** (address demo feedback) is the active focus. Remaining
open tasks in order of dependency:

1. **D5-6-DUP** — fix duplicate VulnerabilityReport warning on report receipt
2. **D5-6-LOGCTX** — add human-readable context to outbox activity log messages
3. **D5-6-TRIGDELIV** — fix trigger endpoints to schedule `outbox_handler`
   (prerequisite for D5-6-DEMOAUDIT)
4. **D5-6-DEMOAUDIT** — audit and refactor all multi-actor demos for protocol
   compliance
5. **D5-7** — project owner sign-off (human only; blocked until D5-6-* done)

D5-7 sign-off gates entry into PRIORITY-350 (maintenance/tooling).

### 2026-04-07 Gap analysis observations (refresh #69)

**D5-6-TRIGDELIV confirmed gap (re-verified 2026-04-07)**: All three trigger
routers (`trigger_report.py`, `trigger_case.py`, `trigger_embargo.py`) still
import no `BackgroundTasks` and make no call to `outbox_handler`. This is
the blocking gap for end-to-end multi-container message flow.

**VOCAB-REG-1 confirmed open**: The vocabulary registry still uses manual
`@activitystreams_object` / `@activitystreams_activity` / `@activitystreams_link`
decorators; no auto-registration mechanism exists yet.

**Completion notes captured**: Implementation patterns from D5-1-G6 (FastAPI
router test `_shared_dl` override) and BUG-2026040102 (circular import fix)
have been added to `notes/codebase-structure.md`.

---

## Treat-warnings-as-errors policy in pytest

`pyproject.toml` sets `filterwarnings = ["error"]` which causes any Python
`warnings.warn()` call during the test session to be treated as a test error.
**No warnings should be present before committing changes.** This is
intentional and enforced by CI.

**Scope caveat**: This policy applies to `warnings.warn()` calls captured
by pytest's warning machinery. It does NOT catch "Exception ignored in:"
messages printed by the Python interpreter at process teardown (e.g.,
`ResourceWarning: unclosed file ...`). Those warnings arise from finalizers
(`__del__`) running after pytest exits and are not visible to `filterwarnings`.
They are still bugs (see BUG-2026040103) — they just require a different fix
(explicitly closing resources in fixtures) rather than a `filterwarnings`
adjustment.

**Rule for agents**: Before committing, run `uv run pytest --tb=short 2>&1`
and verify the summary line shows no failures and no "warnings" count. Also
inspect the output for "ResourceWarning" or "Exception ignored in:" messages,
which signal unclosed resources that should be filed as bugs if not already
tracked.

---

## 2026-04-06 Priority 310 feedback tasks

Reviewer feedback from a live run of the two-actor multi-container demo is
captured in `notes/two-actor-feedback.md` (items D5-6a through D5-6h). These
have been converted into four plan tasks in the new PRIORITY-310 section of
`plan/IMPLEMENTATION_PLAN.md`:

- **D5-6-LOG**: Log quality and completeness across finder/vendor containers
  (D5-6a, b, e, f, g).
- **D5-6-STATE**: RM state log clarity + initialize finder `CaseParticipant`
  at `RM.ACCEPTED` on report receipt (D5-6c).
- **D5-6-STORE**: Verify/fix datalayer stores nested object ID references, not
  full copies (D5-6d).
- **D5-6-WORKFLOW**: Validate-report BT executes the complete case creation
  sequence automatically — no separate engage-case or invite-finder steps
  needed (D5-6h).

### Open question: finder participant lifecycle (D5-6-STATE)

When the vendor receives a finder's `OfferReport`, should a `CaseParticipant`
record for the finder be created immediately (before a `VulnerabilityCase`
exists), or deferred until case creation? Current behavior defers finder
participant creation until `engage-case`. The D5-6-STATE task implies the
finder's RM state (`RM.ACCEPTED`) should be tracked from the moment the
report is received, even before a case exists. This may require a pre-case
participant status record, or a revision to the `CaseParticipant` lifecycle
so that it is always created at report receipt and retroactively attached to
the case during case creation.

### Open question: vendor default embargo for D5-6-WORKFLOW

D5-6h requires the vendor default embargo to be initialized as part of case
creation. The relevant docs and specs (`docs/topics/process_models/em/defaults.md`,
`docs/topics/process_models/model_interactions/rm_em.md`, VP-13-*) exist, but
the vendor-default-embargo initialization may not be fully implemented yet.
The D5-6-WORKFLOW task should verify spec coverage and existing implementation
before coding begins.

### Risk: D5-6-STORE and nested Pydantic serialization

The datalayer storage investigation should check whether the current `dl.save()`
path for activities preserves or expands nested Pydantic objects at
serialization time. The `AGENTS.md` pitfall note on `VulnerabilityCase.case_activity`
shows that enum coverage failures cause fallback to raw `Document` objects;
similar issues may affect activity serialization and should be checked as part
of D5-6-STORE.

---

## 2026-04-06 D5-6i–l feedback tasks (refresh #68)

Continued reviewer feedback from `notes/two-actor-feedback.md` items D5-6i
through D5-6l. Items D5-6a–h were addressed in the prior four tasks (D5-6-LOG,
D5-6-STATE, D5-6-STORE, D5-6-WORKFLOW — all ✅). Items D5-6i–l introduce new
work, particularly D5-6l which raises a fundamental concern about demo
correctness.

New plan tasks:

- **D5-6-DUP**: Investigate/fix duplicate VulnerabilityReport warning (D5-6i).
- **D5-6-LOGCTX**: Improve outbox activity log messages with human-readable
  context (D5-6j).
- **D5-6-TRIGDELIV**: Fix trigger endpoints to call `outbox_handler` after
  use-case execution (D5-6k).
- **D5-6-DEMOAUDIT**: Audit and refactor all demos for protocol compliance
  (D5-6l).

### Critical finding: trigger endpoints do not deliver outbox activities

**Confirmed gap**: All three trigger routers (`trigger_report.py`,
`trigger_case.py`, `trigger_embargo.py`) execute use-case logic (which may
queue activities to the actor's outbox via `datalayer.record_outbox_item()`)
but do NOT schedule `outbox_handler` as a FastAPI `BackgroundTask`.

In contrast, the inbox endpoint (`actors.py` line 470) correctly calls
`inbox_handler` as a `BackgroundTask`, and `inbox_handler` (line 184) calls
`outbox_handler` after processing. The outbox POST endpoint (line 534) also
schedules `outbox_handler`. Triggers bypass both paths.

**Impact**: When the vendor validates a report via `POST /trigger/validate-report`,
the BT generates `CreateCaseActivity`, `Add(CaseParticipant)`, and
`AnnounceEmbargo` activities and queues them to the vendor's outbox. But those
activities are never delivered to the finder because `outbox_handler` is never
called. The finder only receives these messages if:

1. A subsequent inbox activity arrives for the vendor (triggering
   `inbox_handler` → `outbox_handler`), or
2. Someone manually POSTs to the vendor's outbox endpoint.

This violates `specs/outbox.md` OX-03-001 ("Activities in an actor's outbox
MUST be delivered to recipient inboxes") and OX-03-002 ("Delivery MUST occur
after the generating handler completes").

**Fix**: Add `BackgroundTasks` dependency to all trigger endpoint functions
and schedule `outbox_handler` after use-case execution. This is tracked as
task D5-6-TRIGDELIV.

### D5-6l: demo protocol compliance audit (significant)

D5-6l raises the most consequential concern: the multi-actor demos may be
demonstrating "puppeteered" workflows rather than genuine protocol-driven
behavior. Key observations from the gap analysis:

**Two-actor demo** (post D5-6-WORKFLOW): The validate-report BT now automates
case creation, participant setup, embargo initialization, and notification
activity generation. However, because trigger→outbox delivery is broken
(D5-6-TRIGDELIV), the finder never actually receives those notifications in a
multi-container run. The demo-runner also manually posts notes via
`post_to_inbox_and_wait()` rather than using trigger endpoints.

**Three-actor demo**: Uses `engage-case` and `propose-embargo` trigger
shortcuts in the demo-runner where the protocol flow should be automatic
(BT-driven after invitation acceptance). The demo-runner is doing intermediate
steps that should be consequences of primary events.

**Multi-vendor demo**: Same pattern as three-actor — multiple trigger shortcuts
for `validate-report`, `engage-case`, and `propose-embargo` where the protocol
expects automated behavior.

**Single-actor demos**: Already protocol-compliant (direct activity posts).
No changes needed.

**Dependency chain**: D5-6-TRIGDELIV → D5-6-DEMOAUDIT. Without trigger→outbox
delivery, the demo refactoring cannot verify end-to-end message flow.

### Where the BT automation is sufficient vs insufficient

**Sufficient** (no demo-runner shortcut needed):

- validate-report → case creation → participant setup → embargo init →
  notification queuing (7-node BT, fully automated)

**Insufficient** (demo-runner must still trigger or inject):

- submit-report: Finder must trigger this (correct — a primary event)
- validate-report: Vendor must trigger this (correct — a primary event)
- Note exchange: No BT automation for ad-hoc notes (acceptable — notes are
  actor-initiated primary events)
- Invitation acceptance: The `AcceptInviteActorToCaseReceivedUseCase` handles
  the received message, but engagement (RM→ACCEPTED) requires a separate
  `engage-case` trigger in the current implementation. The protocol docs
  suggest that accepting an invitation should automatically advance RM state,
  but the current BT does not do this.
- Embargo proposal: After case creation, the vendor BT initializes a default
  embargo, but in three-actor/multi-vendor scenarios the coordinator must
  explicitly propose via trigger. This is correct for the coordinator-mediated
  flow but may need a BT sequence for the case-creation-includes-embargo
  pattern.

### Open question: automatic engagement after invitation acceptance

The protocol docs (`docs/topics/formal_protocol/worked_example.md`) describe
acceptance of an invitation as implying engagement. The current implementation
requires a separate `engage-case` trigger after accepting an invitation. Should
`AcceptInviteActorToCaseReceivedUseCase` automatically advance RM to ACCEPTED
(via the engage-case BT), or is the separate trigger step intentional?

If engagement should be automatic, the use case needs to invoke
`SvcEngageCaseUseCase` internally. If intentional, the demos should document
why the extra trigger is needed.
