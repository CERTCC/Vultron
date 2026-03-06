# Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate
insights, issues, and learnings during the implementation process.

Add new items below this line

---

## 2026-03-06 (gap analysis refresh #12)

### PyCharm-specific `--- Logging error ---` noise (residual, known limitation)

The `--- Logging error ---` tracebacks visible when running the test suite
under PyCharm's test runner (`_jb_pytest_runner.py`) are due to PyCharm
closing log handler streams after each test, then Python's logging framework
trying to write to those closed streams. This is a PyCharm environment issue,
not a project-code defect. Running `uv run pytest` from the command line
produces clean output (592 passed). No further code changes are warranted
unless a root cause in our handler logging is identified. BUGFIX-1 is
complete.

### Triggerable behaviors spec now formal (TB-*)

`specs/triggerable-behaviors.md` was created (commits since 2026-03-03).
It formally specifies TB-01 through TB-07. The P30 tasks have been updated
to reference these spec IDs and cover previously-missing requirements:
- **TB-03**: request body MUST include `offer_id` or `case_id` per scope;
  unknown fields MUST be ignored; `reject-report` MUST require a `note`.
- **TB-04**: response body SHOULD include `{"activity": {...}}`.
- **TB-06**: DataLayer MUST be injected via `Depends()`, not accessed as a
  singleton — critical for per-actor isolation (CM-01-001).
- **TB-07**: every trigger MUST add the resulting activity to the actor
  outbox (OX-02-001).

The spec also clarifies that `invalidate-report` and `reject-report` are
distinct behaviors from `validate-report` (three-way split on report
validation outcome). P30-2 now covers all three.

### API layer names are conceptual layers, not versions

`notes/codebase-structure.md` (2026-03-05) documents that `api/v1/` and
`api/v2/` are actually distinct layers (examples vs ActivityPub+backend),
not sequential versions. A future refactor to rename them to semantic layer
names (`api.activitypub`, `api.backend`, `api.examples`) is documented there.
This is low priority for the prototype; no plan task is created yet.

### CM-10 embargo acceptance tracking — implementation strategy

CM-10-001 and CM-10-003 can be implemented by adding `accepted_embargo_ids:
list[str] = field(default_factory=list)` to `CaseParticipant`. The two
handlers most affected are `accept_invite_to_embargo_on_case` (explicit
acceptance) and `accept_invite_actor_to_case` (implicit acceptance of
current embargo). SC-3.2 should also apply the server-side timestamp from
`datetime.now(UTC)` rather than any participant-supplied timestamp, in
accordance with CM-02-009.

