## Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate
insights, issues, and learnings during the implementation process.

Add new items below this line

---

### 2026-03-16 — Refresh #39 gap analysis

**Previous session findings (refresh #34–38) captured**: All items from
the prior TECHDEBT review passes (items 1–16), UseCase interface work, and
P75-4/TECHDEBT-15 completion notes have been captured in
`plan/IMPLEMENTATION_PLAN.md` and `plan/IMPLEMENTATION_HISTORY.md`.

**Confirmed open tasks (code-verified)**:

All of TECHDEBT-17 through TECHDEBT-26 confirmed still open as of refresh
#39 via direct code search:

- TECHDEBT-17: Dead bare functions in `embargo.py` at lines 335–599 — present.
- TECHDEBT-18: Duplicate import block + `_resolve_offer_and_report` in
  `triggers/report.py` starting at line 329 — present.
- TECHDEBT-19: `from vultron.api.v2.data.rehydration import rehydrate` and
  `from vultron.api.v2.data.status import ...` in `triggers/report.py`
  lines 28–34 — present (same file as TECHDEBT-18; fix together).
- TECHDEBT-20: Duplicate import block in `triggers/embargo.py` at lines
  279–301 — present.
- TECHDEBT-21: All 38 handler use case classes confirmed without `Received`
  suffix (e.g., `CreateReportUseCase`, `UpdateCaseUseCase`,
  `AcceptInviteToEmbargoOnCaseUseCase`).
- TECHDEBT-22: No use case class inherits from `UseCase[Req, Res]` Protocol.
- TECHDEBT-23: All 8 trigger request models still directly subclass
  `BaseModel`; no `TriggerRequest` base class exists.
- TECHDEBT-24: `case.py` has lazy import of `VulnerabilityCase` from wire
  layer at line 62. `triggers/_helpers.py` imports `VulnerabilityCase` and
  `ParticipantStatus` directly from `vultron.wire.as2.vocab.objects.*`
  at lines 29–30. `core/use_cases/_types.py` already defines `CaseModel`
  and `ParticipantModel` Protocol types that should replace these.
- TECHDEBT-25: `_as_id` pattern (`x.as_id if hasattr(x, "as_id") else x`)
  confirmed in `case.py:267`, `actor.py:258`, `case_participant.py:68` and
  `:124`. No `_helpers.py` with `_as_id()` exists yet.
- TECHDEBT-26: `OptionalNonEmptyString` alias still present in
  `vultron/core/models/events/base.py:21` and used in `:91`, `:94`, `:95`,
  `:97`.

**TECHDEBT-27 and TECHDEBT-28 newly promoted from deferred**:

P75-4 is complete, which removes the deferral conditions for both:
- TECHDEBT-27 (error handling standardization): Several stub use cases
  wrap `logger.info()` in dead `try/except Exception` guards. Three use
  cases (`EngageCaseUseCase`, `DeferCaseUseCase`, `CreateCaseUseCase`) do
  BT status checks via string comparison (`result.status.name != "SUCCESS"`).
  The string comparison issue is low-risk but should be fixed in the same pass.
- TECHDEBT-28 (idempotent-create helper): Six use cases repeat the same
  idempotency guard boilerplate. Batch with TECHDEBT-25 since both add
  helpers to `_helpers.py`.

**OX-1.0 gap confirmed**: `vultron/core/ports/emitter.py` does not exist.
The `ActivityEmitter` Protocol is a prerequisite for OUTBOX-1 delivery and
for properly handling `CloseCaseUseCase`'s outbound activity construction.

**P75-5 still open**: `vultron/api/v1/` exists with app, routers — decision
still needed (keep as vocabulary showcase / merge into v2 / remove).

**Batching recommendations confirmed** (see Priority-80 section in plan):

- TECHDEBT-17 + 18 + 20: all pure dead-code deletions, one commit.
- TECHDEBT-19 + 24: both remove wrong-layer imports from core; the
  `CaseModel`/`ParticipantModel` Protocol types in `_types.py` are already
  suitable replacements for TECHDEBT-24.
- TECHDEBT-21 + 22: mechanical rename then Protocol base declaration; one PR.
- TECHDEBT-25 + 28: both add helpers to `_helpers.py`; one commit.

## Avoid backwards-compatible shims in prototype

As we build out the prototype, we must avoid adding backwards-compatible shims
to support old versions of the code. We need to be able to iterate quickly 
and make changes to code without worrying about maintaining backwards 
compatibility. Nobody outside of this project is dependent on the code as it 
currently exists, and shims create technical debt that we have to clean up 
later anyway. When we are refactoring something, a shim is appropriate to 
confirm changes are working as expected during a test run, but they should 
be removed immediately after the test run confirms the change works as 
expected. Going back through the code and replacing calls to the old code 
with calls to the new code is critical at these moments to avoid 
accumulating technical debt for abandoned interfaces. This is not to say 
that we should break existing code: it's saying that we should go all the 
way with refactors to eradicate the old code and not leave it around with 
shims that just add to the maintenance burden. If you're going to refactor, 
finish the job while you're already in the middle of the code and have the 
context fresh to understand what needs to be changed. Don't leave it for 
later.

## TECHDEBT-24 note

See `notes/architecture-ports-and-adapters.md` regarding richness of core 
objects for vs wire objects. Use that to reason about the correct solution 
to TECHDEBT-24.


---

### 2026-03-16 — TECHDEBT-24 case.py constraint

`CreateCaseUseCase.execute` in `core/use_cases/case.py` retains a lazy import
of `VulnerabilityCase`. The reason: `VulnerabilityCase` uses
`default_factory=init_case_status` to seed `case_statuses = [CaseStatus()]`.
A bare `VultronCase` has `case_statuses = []`; after TinyDB round-trip
(`record_to_object` reconstitutes via `VulnerabilityCase.model_validate`),
`case_statuses` remains empty, and `VulnerabilityCase.current_status`
(which calls `max(self.case_statuses, ...)` without an empty-list guard)
raises `max() iterable argument is empty`.

Options to fully resolve (TECHDEBT-24 remaining item):
- (a) Add an `init_case_status`-equivalent `default_factory` to
  `VultronCase.case_statuses` using a `VultronCaseStatus` initializer.
- (b) Have the `PersistCase` BT node convert `VultronCase` → `VulnerabilityCase`
  before persisting.
- (c) Add an empty-list guard to `VulnerabilityCase.current_status` (smallest
  change, but treats the symptom not the root cause).

## `vultron/api/v2/backend/handlers/__init__.py` is pointless?

The handlers `__init__.py` currently contains a bunch of functions that are 
basically just compatibility shims from a previous refactor. It seems like 
these could be removed and their callers could just call the use cases 
directly. For example:

```python
def create_report(dispatchable, dl=None):
    return _uc_report.CreateReportReceivedUseCase(dl).execute(
        _unwrap(dispatchable)
    )
```

Also consider whether the `dispatchable` unwrapping logic is something that
is still needed or if it is a relic of the pre-refactor architecture. If 
it's not needed, then that would be another reason to remove these shims and 
revise the code to interact directly with the use case ports.

