## Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate
insights, issues, and learnings during the implementation process.

Add new items below this line

---

### 2026-03-20: IMPLEMENTATION_NOTES.md reset

This file was reset after extracting durable content into `notes/` files.
Items extracted:

- Wire-layer terminology leaking into core event interfaces →
  `notes/domain-model-separation.md`
- Core should reliably get domain objects from DataLayer →
  `notes/domain-model-separation.md`
- Datalayer storage records rethink →
  `notes/domain-model-separation.md`
- Vocabulary registry entanglement →
  `notes/domain-model-separation.md`
- Trigger services relocation plan →
  `notes/codebase-structure.md`
- VCR-019a bulk-rename lessons learned →
  `notes/codebase-structure.md`
- VCR-019d / transitions sweep → captured as TECHDEBT-34 in plan
- VCR-019e / MessageTypes clarification → implemented (complete)
- VCR-022 vs TECHDEBT-16 → confirmed identical, both complete
- Prefer `TypeHint | None` over `Optional[TypeHint]` → style preference,
  apply opportunistically during refactoring (no bulk task needed)
- VCR-005 follow-up (profile endpoint returns links only) → TECHDEBT-29
- Semantic field naming in core events → TECHDEBT-30
- `wire` needs pydantic field aliases, `core` does not → already in AGENTS.md
- `transitions` + Pydantic integration pattern → captured in
  `notes/state-machine-findings.md` (OPP-06 implementation note)

---

### Current open items (2026-03-20)

**P90-1** — Persist initial RM report-phase state in `VultronParticipantStatus`
(currently `set_status()` writes to the in-memory STATUS dict only). This is
ADR-0013 implementation step 1. `CreateReportReceivedUseCase` and
`SubmitReportReceivedUseCase` need to also create a persisted
`VultronParticipantStatus` with `rm_state=RM.RECEIVED` after storing the
report.

**P90-4** — Once P90-1 is done, the transient STATUS dict and its helpers
(`ReportStatus`, `set_status()`, `get_status_layer()`) in
`vultron/core/models/status.py` can be deprecated and removed.

**TECHDEBT-31** — `vultron/api/v2/backend/trigger_services/` is the last
significant chunk of the old `api/v2/` layer. Move its contents into
`vultron/adapters/driving/fastapi/` (see `notes/codebase-structure.md` for
the full plan). Do this before ACT-2 to avoid threading DataLayer isolation
changes through two layers.

**TECHDEBT-32** — Research the core/DataLayer boundary coupling
(object_to_record, record_to_object, vocabulary registry entanglement) before
implementing ACT-2, so that the DataLayer isolation work starts with a clean
understanding of the port contract.

**VCR-014** — `vultron/api/v2/data/actor_io.py` is the last blocker to
removing `vultron/api/v2/data/` entirely. Resolution is defined in ADR-0012
(migrate inbox/outbox into per-actor DataLayer as part of ACT-2).

## Implementation plan review and prioritization

We recently completed a review of the implementation plan, attempting to
group tasks according to complexity and effort.
Grouping by the four-rung rubric (For each task I state label (Complexity /
Effort), short rationale, and key dependencies)

### Quick Wins (Low Complexity / Low Effort)

TECHDEBT-29 — (Low / Low)
Rationale: spec + small test + single endpoint change (ensure inbox/outbox are
URLs, not embedded collections). Small PR + test.
Dependencies: None.

P90-5 — (Low / Low)
Rationale: docs-only requirement addition to spec; no code.
Dependencies: None.

OX-1.4 — (Low / Low)
Rationale: adding a test file scaffold + tests is narrow; straightforward.
Dependencies: OX design decisions to test, but test file can be created now.

OB-05-002 (Deferred health readiness probe) — (Low / Low)
Rationale: add a simple DataLayer read probe (e.g., dl.list() or dl.ping()) and
return 503 if it fails. Small change in routers/health.py.
Dependencies: DataLayer port is already present.

AR-01-003 — (Low / Low)
Rationale: add unique operation_id values to FastAPI route decorators — small
PR.

### Fillers / "The Churn" (Low Complexity / High Effort)

TECHDEBT-30 — (Low Complexity / High Effort)
Rationale: mechanical audit and rename across many use-case signatures, event
models and call sites. Low conceptual complexity but touches many files and
tests.
Dependencies: Need comprehensive grep / tests; update tests and possibly API
docs.

TECHDEBT-33 — (Low / High)
Rationale: split a monolithic large test file into multiple files. Mechanically
repetitive but time-consuming and needs careful test-run verification.
Dependencies: Running full test suite to ensure coverage parity.

P90-4 — (Low / High)
Rationale: removing a global STATUS dict is conceptually simple but requires
touching many call sites and tests. Risky and test-heavy.
Dependencies: P90-1 (must complete first).

VCR-014 — (Low / High) — borderline filler vs strategic depending on chosen
resolution
Rationale: removing/migrating actor_io.py can be mechanical if migration path is
clear (move to DataLayer or queue adapter), but will require many test updates
and careful orchestration.
Dependencies: ACT decisions and possibly ACT-2/ACT-3.

### Tactical Strikes (High Complexity / Low Effort)

These are items that need an architectural idea or small design fix; once the
design is decided, the code change is relatively small.

OX-1.3 — (High Complexity / Low Effort) — candidate tactical strike
Rationale: idempotency design requires careful thought (how to detect
duplicates), but implementing an idempotent-create guard or quick "exists" check
in the delivery path can be small once the pattern is chosen. This is a
high-leverage change (prevents duplicates) but may be a small helper + test once
the approach is selected.
Dependencies: OX design and DataLayer index/unique-key support.

(Possible tactical candidates depending on design choices)
Some guard/validator additions (e.g., strict inbox/outbox shape validation) —
low code but needs careful design.

### Strategic Initiatives (High Complexity / High Effort)

TECHDEBT-31 — (High / High)
Rationale: moving trigger_services/ into FastAPI adapters is a coordinated,
multi-step architectural change (move functions, models, error translators,
inline adapter delegates, delete old dir). Large PR and test updates.
Dependencies: tests, router stability.

TECHDEBT-32 — (High / High)
Rationale: cross-cutting audit of DataLayer/core boundary; requires
repository-wide analysis, doc, and follow-on tasks (TECHDEBT-32b).
Dependencies: careful code review and likely subsequent refactor tasks.

TECHDEBT-34 — (High / High)
Rationale: sweep and migrate many hand-rolled state transitions to transitions
machines across vultron/core/ — deep changes; must keep behavior identical and
add tests.
Dependencies: existing transitions factories, test coverage, caution with
RM/EM/CV flows.

ACT-2 — (High / High)
Rationale: Implementing per-actor DataLayer isolation is a major architectural
change (affects data location, DI for datalayer, get_datalayer semantics).
Dependencies: ADR-0012 (complete), tests, careful migration plan.

ACT-3 — (High / High)
Rationale: Updating all tests and get_datalayer dependency injection is
labour-intensive.
Dependencies: ACT-2.

OX-1.1 & OX-1.2 — (High / High)
Rationale: outbox/local delivery and background delivery integration are core
features touching ports/adapters and runtime background execution; must be
designed for idempotency and non-blocking response.
Dependencies: OX-1.0 port (complete), OX-1.3 (idempotency), background task
system (FastAPI BackgroundTasks).

CA-1, CA-2, CA-3 — (High / High)
Rationale: Implementing CaseActor broadcast, adding action-rules endpoint, and
tests depend on outbox/delivery work and actor isolation.
Dependencies: OX-1.* and ACT-2/3.

D5-1..D5-5 — (High / High)
Rationale: Multi-actor demos are integration-heavy (container orchestration,
multiple actors, CaseActor), requiring ACT & OUTBOX foundations to be in place.
Dependencies: ACT-2/3, OX-1.*, CA-1.

VCR-019d — (High / High)
Rationale: adoption of transitions module across RM/EM/CS is non-trivial; it is
a strategic consistency project.

### Other Deferred / Medium items (not yet prioritized in plan)

OB-05-002 — health readiness (listed under Deferred) — Quick Win (already
placed).

AR-04/05/06 — job tracking/pagination/bulk ops — (High / High) — production
readiness work
Domain model separation (CM-08) — ADR + follow-up — (High / High)

### Summary counts (rough)

- Quick Wins (Low/Low): 4–5 tasks (TECHDEBT-29, P90-5, OX-1.4, OB-05-002,
  AR-01-003)
- Fillers (Low/High): 3–4 tasks (TECHDEBT-30, TECHDEBT-33, P90-4, VCR-014)
- Tactical Strikes (High/Low): 1–2 candidate tasks (OX-1.3 and similar small
  idempotency/design fixes)
- Strategic Initiatives (High/High): ~12+ tasks (TECHDEBT-31, TECHDEBT-32,
  TECHDEBT-34, ACT-2/3, OX-1.1/1.2, CA-1–3, D5-1..D5-5, VCR-019d)

### Short recommended next steps (practical roadmap)

Do the Quick Wins first (small PRs): TECHDEBT-29, OB-05-002, P90-5, OX-1.4,
AR-01-003. These unblock tests/docs and give immediate CI wins.

While CI is healthy, schedule one filler batch sprint for mechanical churn:

- Batch TECHDEBT-30 and TECHDEBT-33 together (they are both broad, mechanical
  updates that require running the full test-suite).
- Start P90-1 design in parallel (see next).

Start tactical design for OX idempotency (OX-1.3): define the idempotency key
and DataLayer support. This is a small-scope design that will enable OX-1.1/1.2
implementation.

Kick off one strategic initiative at a time:

- TECHDEBT-31 (relocate trigger_services) is a discrete, bounded strategic
  task — do this first as it reduces adapter/core layering friction.
- Parallel research: TECHDEBT-32 (audit) — create the analysis doc as an
  output-only task; that doc will reduce risk for large refactors (ACT-2,
  VCR-014).

Schedule major feature work (ACT-2/ACT-3 and OUTBOX OX-1.1/1.2) only after
idempotency (OX-1.3) and the DataLayer boundary research (TECHDEBT-32) are
complete.

For demos (D5-*), reserve them until PRIORITY-100/200 items are stable; use them
as integration tests once core features are in.

## `_make_payload()` duplicated across tests

Multiple tests contain a `def _make_payload(activity, **extra_fields):` 
method due to a large refactoring that split a test file into multiple files.
Because this appears to be a common test helper, it should be centralized to 
DRY up the test codebase.

## `vultron/api/v2` is deprecated

At this point we should make explicit: we should not be adding anything 
new to `vultron/api` at all as it's subsumed into the 
`vultron/adapters/driving/fastapi/` layer. This also means that `test/api` 
should also be deprecated and any existing tests migrated to the new structure.

## Avoid local imports in test modules

Far too many tests have local imports inside test functions. This is an 
anti-pattern that makes the code harder to read and can cause issues with 
refactoring and test discovery. All imports should be at the top of the file 
to avoid bloating the test functions and to make it clear what dependencies 
the test module has. This should be enforced as a style guideline and 
cleaned up across the codebase.

## Important notes on TECHDEBT-30 (semantic field naming in core events)

`vultron/wire/as2/extractor.py` contains key information about the mapping 
between AS2 fields in terms of the semantics it's looking for in 
`ActivityPattern` objects. Use these patterns as a reference for mapping the 
AS2 fields from wire into core objects.

Core objects should be ignorant of AS2 and not rely on AS2-specific field names.
Also be cognizant of DRY principles and follow these in any new code you 
create. Do not duplicate for the sake of duplication, clean up and 
centralize any common logic wherever possible.

The intuition that extractor can create common objects that get translated 
before passing into core use cases is a good one. However you may be 
treating VultronEvent too rigidly. Since VultronEvent is a core object it 
was ea mistake for it to have any AS2 terminology dependency to begin with. 
So you might consider going deeper with your solution. Do the hard thing now 
to get the right design. We are in prototype mode so all refactoring now is 
comparatively cheap to the longer term cost of having to maintain bad 
abstractions. We're not obligated to preserve backwards compatibility with 
the current VultronEvent or extractor design, we're the only users of these 
components at present so it is more important that we get them right for the 
future than preserve the status quo.

The core VultronEvent class may be too generic for use cases to be able to 
reliably infer semantics of fields like `object` and `target`. One direction 
to consider is that the extractor might be refactored to not just map to a 
message semantics enum, but instead could perform the mapping directly from 
an AS2 message into a domain-specific event class. Consider the use of a 
"Activity.to_domain()" pattern to provide a consistent implementation point 
for this mapping logic, or possibly a more explicit "EventFactory" that 
takes and activity, figures out the semantics like the extractor does now, 
and then returns a domain-specific event object with well-defined fields. 
The domain-specific event then maps to a specific use case input model, 
which is then invoked with the new event as its input.
