## Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate
insights, issues, and learnings during the implementation process.

Append new items below any existing ones, marking them with the date and a
header.

---

## 2026-03-26 Current active priority

PRIORITY-250 (pre-300 cleanup) is now the active focus. Tasks in order:
NAMING-1, QUALITY-1, SECOPS-1, DOCMAINT-1, REORG-1. D5-1 (architecture
review for multi-actor demos) may proceed in parallel with PRIORITY-250.
D5-2 and later demo tasks are explicitly blocked until PRIORITY-250 is
complete (per `plan/PRIORITIES.md`).

The trigger→received→sync information flow (participants trigger state
changes → the resulting messages arrive at CaseActor's inbox as "received"
events → sync replicates the updated case log to all participants) should be
documented as part of REORG-1.

---

## 2026-03-30 Gap analysis observations (refresh #57)

### SECOPS-1 remaining work

SHA pinning is complete (all 6 workflow files). `specs/ci-security.md` was
previously created. Dependabot is configured weekly for `github-actions`,
satisfying VSR-01-003. Remaining: (1) write ADR documenting the policy and
Dependabot-as-primary-maintenance; (2) implement CI-SEC-01-003 automated test.
See updated SECOPS-1 task in IMPLEMENTATION_PLAN.md.

### Stale spec references inventory (for SPEC-AUDIT-3)

The 2026-03-30 gap analysis found these specific outdated references in
`specs/`:

- `verify_semantics` decorator (removed in PREPX-2): referenced in
  `dispatch-routing.md` DR-01-003, `behavior-tree-integration.md` ~line 170,
  and `architecture.md` ~line 106 (as a completed item note).
- `SEMANTIC_HANDLER_MAP` (renamed to `USE_CASE_MAP`): referenced in
  `dispatch-routing.md` DR-02-001/002, `handler-protocol.md`,
  `semantic-extraction.md` SE-05-002.
- `test/api/v2/` test paths (directory removed): referenced in
  `dispatch-routing.md`, `error-handling.md`, `handler-protocol.md`,
  `http-protocol.md`, `idempotency.md`, `inbox-endpoint.md`,
  `message-validation.md`, `observability.md`, `outbox.md`,
  `response-format.md`, `structured-logging.md`.

These stale references should be corrected as part of SPEC-AUDIT-3.

### VSR-ERR-1: VultronConflictError rename now a plan task

VSR-03-002 (rename `VultronConflictError` → `VultronInvalidStateTransitionError`)
is now tracked as plan task VSR-ERR-1. The rename affects:
`vultron/errors.py`, `vultron/core/use_cases/triggers/embargo.py` (4 raises),
`vultron/core/use_cases/triggers/report.py` (1 raise),
`vultron/adapters/driving/fastapi/errors.py` (handler mapping), and
corresponding tests.

### BUG-FLAKY-1: test_remove_embargo root cause

The test at `test/wire/as2/vocab/test_vocab_examples.py::test_remove_embargo`
calls `examples.remove_embargo()` (which internally calls
`embargo_event(90)`) and then also calls `examples.embargo_event(days=90)`
separately. Both calls use `datetime.now()` to produce a time-based `as_id`.
If the two calls straddle a second boundary, the IDs differ and the equality
assertion fails. Tracked as plan task BUG-FLAKY-1. Must be fixed before
PRIORITY-300 demo work.

### notes/activitystreams-semantics.md stale note (for DOCMAINT-1)

`notes/activitystreams-semantics.md` ~line 333 states "CaseActor broadcast is
not yet implemented". This is outdated — CaseActor broadcast was implemented
in PRIORITY-200 (CA-2) via
`vultron/core/use_cases/case.py::_broadcast_case_update`. DOCMAINT-1 should
update this note.

---

---

## 2026-03-30 NAMING-1 complete

All `as_`-prefixed field names have been migrated to trailing-underscore
convention (`id_`, `type_`, `object_`, `context_`). Class names retain
the `as_` prefix. All 1080 tests pass. `specs/code-style.md` updated to
MUST-level policy. PRIORITY-250 is now fully complete — D5-2 and later
PRIORITY-300 demo tasks are unblocked.

---

## 2026-03-31 D5-1-G1 and D5-1-G6 complete

### D5-1-G1 notes

The `GET /info` endpoint lives at `/info` (i.e., `/api/v2/info` when mounted).
It returns `VULTRON_BASE_URL` (from `vultron.adapters.utils.BASE_URL`) and a
list of actor IDs from the shared DataLayer. The `/health/ready` DataLayer
connectivity probe (OB-05-002) was already implemented — only the info
endpoint was missing.

### D5-1-G6 notes

The inbox URL derivation in `DeliveryQueueAdapter` (`{actor_id}/inbox/`) is
already consistent with the FastAPI route (`POST /actors/{uuid}/inbox/`).
Tests in `test/adapters/driven/test_delivery_inbox_url.py` serve as a
regression guard. Reminder: when writing router tests that use `_shared_dl`
in `actors.py`, override both `get_datalayer` and `actors_router._shared_dl`
in `app.dependency_overrides` — `_shared_dl` calls `get_datalayer()` directly
(not via `Depends`), so overriding only `get_datalayer` is insufficient.

D5-1-G3, D5-1-G4, and D5-1-G5 are the remaining prerequisites for D5-2.

---

## 2026-03-31 D5-1-G5 complete

The new two-actor demo lives in `vultron/demo/two_actor_demo.py` and is
exposed through `vultron-demo two-actor` in `vultron/demo/cli.py`.

The implementation uses a two-phase seeding flow: each container first
creates its own local actor, then registers the peer actor using the
deterministic full URI returned from the opposite container. This keeps
the setup idempotent and avoids race/order assumptions across
containers.

The demo intentionally simulates cross-container message delivery by
posting activities directly to the target container's inbox with the
target container's `DataLayerClient`. That matches
`DEMO-MA-00-001` / the multi-actor architecture notes: coordination
still happens over HTTP, but the orchestration script does not rely on
background outbox delivery to advance the scenario deterministically.

`find_case_for_offer()` must resolve the case indirectly via the report
ID referenced by the stored submit-report offer. This matches current
case creation behavior, where `VulnerabilityCase.vulnerability_reports`
stores report references and the validate-report trigger creates the
case from that report rather than from the offer object itself.

D5-2 is now the next executable task.

2026-03-31 D5-2 complete

The two-actor Dockerized demo now resets Finder/Vendor container state to a
known baseline, re-seeds the scenario deterministically, and verifies the
final case state strongly enough to assert the intended D5-2 workflow rather
than just successful HTTP calls.

The main core gap exposed by the stronger scenario was not in demo code: the
validate-report BT path created a case but did not seed the initial Vendor
participant or `actor_participant_index`. Reusing
`CreateInitialVendorParticipant` from `create_validate_report_tree()` fixed the
missing Vendor participant and removed the follow-on `engage-case` warning
about a missing `CaseParticipant` for the Vendor actor.

Validation completed cleanly with focused demo/BT tests plus the canonical
Black/flake8/mypy/pyright/pytest validation command. A live Docker Compose
acceptance attempt was also made with a unique project name, but the shared
local Docker daemon was out of space (`no space left on device` while creating
BuildKit temp dirs / volumes), so the multi-container runtime check could not
be completed in this environment.

---

## 2026-04-01 D5-3 complete

The three-actor demo now lives in `vultron/demo/three_actor_demo.py` and is
exposed through `vultron-demo three-actor`. It extends the D5-2 multi-actor
infrastructure with a dedicated Coordinator container and uses the existing
CaseActor container as the authoritative case host.

The deterministic D5-3 workflow is intentionally centered on already-supported
protocol surfaces: Finder submits the report to the Coordinator, the
Coordinator creates the authoritative case on the CaseActor container via
`CreateCaseActivity`, explicitly links the report with
`AddReportToCaseActivity`, invites Finder and Vendor via case invites, and
establishes the embargo using the existing `propose-embargo` /
`EmAcceptEmbargoActivity` flow. This keeps the demo additive and avoids
inventing a new remote create-case trigger.

Unit tests use the existing single-`TestClient` demo pattern, so all logical
"containers" share one base URL during pytest. The three-actor demo therefore
avoids duplicate self-delivery when the authoritative CaseActor client and the
recipient client are the same underlying test server; real multi-container
runs still take the full record-locally-then-deliver-remotely path.

The scenario also exposed an unrelated core-state issue now tracked in
`plan/BUGS.md`: invited participants do not currently end in `RM.ACCEPTED`
after invite acceptance plus `engage-case`. D5-3 verification therefore checks
the stable behavior the system does provide today (authoritative case hosting,
participant registration, and embargo acceptance) without trying to redefine
that state-machine behavior inside the demo task.

---

## Circular Import Resolution Pattern (BUG-2026040102, 2026-04-01)

When a module in `vultron/core/behaviors/` needs a helper also used by
`vultron/core/use_cases/triggers/`, importing it from `triggers/_helpers`
triggers the `triggers/__init__.py`, which eagerly imports all trigger
use-case submodules.  If any of those submodules import back into the
behaviors layer, a circular import results.

**Fix pattern**: move shared helpers to `vultron/core/use_cases/_helpers.py`
(the neutral, package-top-level helpers module), which is importable from any
layer without loading the `triggers` sub-package.  `triggers/_helpers.py` may
re-export for callers already inside the `triggers` package.

**Corollary**: `VultronCase` (core) now implements `record_event()` so that
`is_case_model()` returns `True` for core-created cases as well as
wire-layer `VulnerabilityCase` instances.  The `CaseModel` Protocol guard
must be satisfiable by both model families.

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
