# AGENTS.md — Vultron Project

## Purpose

This file provides quick technical reference for AI coding agents working in
this repository.

**See also**:

- `notes/` — durable design insights (BT integration, ActivityStreams
  semantics). These files are committed to version control and are the
  authoritative source for design decisions.
- `specs/project-documentation.yaml` — documentation structure guidance.

Agents MUST follow these rules when generating, modifying, or reviewing code.

---

## Agent Quickstart

- **Load specs first**: `uv run spec-dump` (or `load-specs` skill) — do **not**
  read raw `specs/*.yaml` files.
- Key pipeline: FastAPI inbox → AS2 parser → semantic extraction
  (`vultron/wire/as2/extractor.py`) → dispatcher → use-case callable
  (`vultron/core/use_cases/`).
- Use-Case Protocol: `__init__(dl, request)` + `execute() -> None`; routing
  is via `USE_CASE_MAP` key lookup, not per-handler decorators.
- Tests: `uv run pytest --tb=short 2>&1 | tail -5` — run **once**, read output.
  See `.agents/skills/run-tests/SKILL.md` for the single-run rule and suite
  variants (unit / integration / all).
- Commands: see `.agents/skills/format-code/SKILL.md`,
  `run-linters/SKILL.md`, `run-tests/SKILL.md`, `build-docs/SKILL.md`.

Quick gotchas:

- `SEMANTICS_ACTIVITY_PATTERNS`: specific patterns before general.
- Always `rehydrate()` before pattern matching.
- Persist with `dl.save(obj)` — `object_to_record()` + `dl.update()` is removed.
- FastAPI endpoints return 202 immediately; use `BackgroundTasks` for work.
- Non-trivial architecture changes → draft an ADR first.

## Scope of Allowed Work

Agents MAY:

- Implement small to medium features that do not change public APIs or
  persistence schemas
- Refactor existing code without changing external behavior
- Add or update tests and test fixtures
- Improve typing, validation, and error handling
- Update documentation, examples, and specification markdown in `docs/` and
  `specs/`
- Propose architectural changes (but not apply them without approval)

Agents MUST NOT:

- Introduce breaking API changes without explicit instruction
- Modify authentication, authorization, or cryptographic logic
- Change persistence schemas or perform data migrations without explicit
  instruction
- Touch production deployment, CI configuration, or secrets unless explicitly
  instructed (see exception below for documentation updates)

Note: Small implementation tweaks do not require an ADR;
architectural or protocol changes SHOULD be documented as ADRs before merging.
See `docs/adr/_adr-template.md`.

---

## Technology Stack (Authoritative)

Runtime: Python **3.12+** (CI: 3.13), **FastAPI** (BackgroundTasks for long
ops), **Pydantic v2**, **pytest**, **mkdocs** (Material). Dev tools: **uv**,
**black**, **flake8**, **mypy**, **pyright**, **markdownlint-cli2** (`mdlint.sh`).
Do NOT introduce alternative frameworks or package managers without approval.

---

> **Architecture details** (layer rules, hexagonal architecture, message pipeline):
> see [notes/architecture-ports-and-adapters.md](notes/architecture-ports-and-adapters.md).

## Coding Rules (Non-Negotiable)

### Naming Conventions

- **ActivityStreams class names**: Use `as_` prefix (e.g., `as_Activity`,
  `as_Actor`) — in the wire layer (`vultron/wire/as2/`) only
- **Wire-layer and core field names**: Use trailing underscore for fields
  whose plain name collides with a Python builtin or reserved word
  (e.g., `id_`, `type_`, `object_`, `context_`) with a Pydantic alias
  for the JSON key (e.g., `id_: str = Field(alias="id")`). See CS-07-002,
  CS-07-003. Do NOT use `as_`-prefixed field names anywhere.
- **Domain class names**: Use CVD-domain vocabulary, not wire-format parallels
  (e.g., `CaseTransferOffer` not `VultronOffer`). See CS-12-001.
- **Vulnerability**: Abbreviated as `vul` (not `vuln`)
- **Handler functions**: Named after semantic action (e.g., `create_report`,
  `accept_invite_actor_to_case`)
- **Handler use cases** (processing received messages): Use `Received` suffix
  (e.g., `CreateReportReceivedUseCase`). See CS-12-002.
- **Trigger use cases** (actor-initiated actions): Use `Svc` prefix
  (e.g., `SvcEngageCaseUseCase`). See CS-12-002.
- **Trigger service functions** in `trigger_services/`: Use a `_trigger`
  **suffix** (not an `svc_` prefix). For example: `engage_case_trigger`
  not `svc_engage_case`. The `Svc` prefix is reserved for use-case class
  names only.
- **Pattern objects**: Descriptive CamelCase (e.g., `CreateReport`,
  `AcceptInviteToEmbargoOnCase`)

### Validation and Type Safety

- Prefer explicit types over inference; avoid `Any` (see CS-11-001)
- Use `pydantic.BaseModel` (v2 style) for all structured data
- Never bypass validation for convenience
- Use Protocol for interface definitions
- Avoid global mutable state
- **Fail-fast domain objects**: Domain events and models MUST validate
  required fields at construction and fail immediately on missing invariants.
  Fields that are required for a specific event subtype MUST NOT be typed
  as `X | None` in that subtype. Subclasses SHOULD narrow optional parent
  fields to required. See `specs/architecture.yaml` ARCH-10-001.
- **Optional string fields MUST follow "if present, then non-empty"**:
  `Optional[str]` fields MUST reject empty strings. Use the shared
  `NonEmptyString` or `OptionalNonEmptyString` type alias from
  `vultron/wire/as2/vocab/base/` when it exists (CS-08-002), or a field
  validator that raises `ValueError` for `""` if the type alias is not yet
  available. This pattern also applies to JSON Schemas derived from Pydantic
  models (`minLength: 1`). See `specs/code-style.yaml` CS-08-001, CS-08-002.
  **Do NOT** add a new per-field `@field_validator` stub for empty-string
  rejection; instead, use or extend the shared type alias.

### Decorator Usage

- Semantic type validation is performed at dispatch time by the `USE_CASE_MAP`
  key lookup in `vultron/core/dispatcher.py`
- Unrecognised semantic types raise `VultronApiHandlerNotFoundError`

### Code Organization

- Prefer small, composable functions
- Raise domain-specific exceptions; do not swallow errors
- Keep formatting and linting aligned with tooling; do not reformat
  unnecessarily

### Markdown Formatting

- **Line length**: Regular text lines MUST NOT exceed 88 characters
- Exceptions: Tables, code blocks, long URLs, or other formatting that requires
  it
- Use `markdownlint-cli2` for linting markdown files; see Miscellaneous tips
  for the correct commands
- Break long sentences at natural points (after commas, conjunctions, etc.)
- Keep list items and paragraphs readable and well-formatted

**Rationale**: Consistent line length improves readability in text editors and
reduces diff noise. 88 characters aligns with Python's Black formatter width.

### Logging Requirements

Log levels: DEBUG (details), INFO (lifecycle/state transitions), WARNING
(recoverable), ERROR (failures), CRITICAL (system). Include `activity_id`
and `actor_id` when available. See `specs/structured-logging.yaml`.

---

> **Specification-Driven Development** has moved to `specs/AGENTS.md`.
> **Testing Expectations** has moved to `test/AGENTS.md`.

## Quick Reference

### Adding a New Message Type

1. Add `MessageSemantics` enum value in `vultron/core/models/events.py`
2. Define an `ActivityPattern` named `<TypeName>Pattern` in
   `vultron/wire/as2/extractor.py`
3. Add pattern to `SEMANTICS_ACTIVITY_PATTERNS` in
   `vultron/wire/as2/extractor.py` (order matters — specific before general)
4. Implement a use-case class in `vultron/core/use_cases/`:
   - Follow `UseCase[Req, Res]` Protocol; accept `(dl, request)` in `__init__`
   - Implement `execute() -> None`
5. Register in `USE_CASE_MAP` in
   `vultron/core/use_cases/use_case_map.py`
6. Add tests:
   - Pattern matching in `test/test_semantic_activity_patterns.py`
   - Routing coverage in `test/test_semantic_handler_map.py`
   - Use-case logic in `test/core/use_cases/`

### Key Files Map

- **Enums**: `vultron/enums.py` — re-exports `MessageSemantics`; defined in
  `vultron/core/models/events.py`
- **Patterns**: `vultron/wire/as2/extractor.py` — `ActivityPattern` defs
  (`*Pattern` names), `SEMANTICS_ACTIVITY_PATTERNS`, `find_matching_semantics()`
- **Use-Case Map**: `vultron/core/use_cases/use_case_map.py` — `USE_CASE_MAP`
  (`MessageSemantics` → use-case callable)
- **Dispatcher**: `vultron/core/dispatcher.py` — `DirectActivityDispatcher`,
  `get_dispatcher()`; port: `vultron/core/ports/dispatcher.py`
- **Inbox**: `vultron/adapters/driving/fastapi/routers/actors.py`
- **Triggers**: `vultron/adapters/driving/fastapi/routers/trigger_*.py`
- **Errors**: `vultron/errors.py`, `vultron/adapters/driving/fastapi/errors.py`
- **Data Layer port**: `vultron/core/ports/datalayer.py` — `DataLayer` Protocol
- **TinyDB adapter**: `vultron/adapters/driven/datalayer_tinydb.py`
- **BT Bridge**: `vultron/core/behaviors/bridge.py`
- **BT nodes/trees**: `vultron/core/behaviors/report/`, `case/`, `helpers.py`
- **Case Event Log**: `vultron/wire/as2/vocab/objects/case_event.py` — use
  `VulnerabilityCase.record_event(object_id, event_type)`
- **Vocab Examples**: `vultron/wire/as2/vocab/examples/` — reference for
  message semantics and test fixtures
- **Demo**: `vultron/demo/cli.py` (entry point), `utils.py` (shared helpers),
  `vultron/demo/*_demo.py` (workflow scripts)
- **Case States**: `vultron/case_states/` — enums are authoritative; update
  docs, not enums, when they conflict

### Constructing Outbound Activities

All outbound Vultron activities MUST be constructed via the factory functions
in `vultron.wire.as2.factories`. Code outside
`vultron/wire/as2/vocab/activities/` and `vultron/wire/as2/factories/` MUST
NOT import internal activity subclasses (e.g., `RmCreateReportActivity`)
directly. Use the corresponding factory function instead (e.g.,
`rm_create_report_activity()`). This boundary is enforced by
`test/architecture/test_activity_factory_imports.py`.

### GitHub Issue Labels

When adding a `group:` label to an issue, the label name MUST NOT include a
priority number (PAD-02-007). Use a short, descriptive kebab-case slug derived
from the priority group title — e.g., `group:architecture-hardening`, never
`group:473-architecture-hardening`. Priority numbers in `plan/PRIORITIES.md`
can be reordered; label names must remain stable. Before assigning a
`group:` label, verify it exists on GitHub and create it with `gh label create`
if not. See `notes/parallel-development.md` §Group Label Conventions.

## Change Protocol

When making non-trivial changes, agents SHOULD:

1. Briefly state assumptions
2. Load specifications with `uv run spec-dump` (see `load-specs` skill) and
   consult requirements relevant to the change
3. Review `notes/` directory for durable design insights
4. Describe the intended change
5. Apply the minimal diff required
6. Update or add tests per Testing Expectations
7. Call out risks or follow-ups

Do not produce speculative or exploratory code unless requested. For proposed
architectural changes, draft an ADR (use `docs/adr/_adr-template.md`) and link
to relevant tests and design notes.

### Commit Workflow

**Before committing**, run the skills in this order:

1. `format-code` — Black + flake8
2. `run-linters` — all four linters (Black, flake8, mypy, pyright); all MUST pass
3. `run-tests` — unit suite once; read output
4. `build-docs` — only when `docs/` files were modified
5. `commit` skill — include Co-authored-by trailer

See each skill's SKILL.md for the exact commands. If the pre-commit hook
reformats files: `git add -A && git commit -m "Same message"`.

---

> **Specification Usage Guidance** has moved to `specs/AGENTS.md`.
>
## Safety & Guardrails

- Treat anything under `/security`, `/auth`, or equivalent paths as sensitive
- Do not generate secrets, credentials, or real tokens
- Flag ambiguous requirements instead of guessing

---

## Project Vocabulary

- Use **`vul`** (not `vuln`) as the abbreviation for vulnerability
- Prefer domain terms already present in the codebase
- Do not invent new terminology without justification

---

## Default Behavior

If instructions are ambiguous:

- Choose correctness over convenience
- Choose explicitness over brevity
- Ask for clarification rather than assuming intent

---

## Common Pitfalls (Lessons Learned)

Key pitfall write-ups are in the `notes/` files.
Short entries are reproduced here; longer ones are referenced below.

### Idempotency Responsibility Chain

Layered: Inbox MAY detect duplicates (IE-10); Message Validation SHOULD
detect duplicate submissions (MV-08); Handlers SHOULD implement idempotent
logic — check for existing records before creating (HP-07-001). Data Layer
provides unique ID constraints. Report handlers (`create_report`,
`submit_report`) already follow this pattern.

---

### Reference index

- **Circular Imports** — see [notes/codebase-structure.md](notes/codebase-structure.md)
- **Pattern Matching with ActivityStreams** — see [notes/activitystreams-semantics.md](notes/activitystreams-semantics.md)
- **Test Data Quality** — moved to `test/AGENTS.md`
- **All Protocol-Significant Behavior MUST Be in the BT** — see [notes/bt-integration.md](notes/bt-integration.md)
- **Protocol Event Cascades (Cascading Automation)** — see [notes/bt-integration.md](notes/bt-integration.md)
- **Post-BT Procedural Cascade Anti-Pattern** — see [notes/bt-integration.md](notes/bt-integration.md)
- **py_trees Blackboard Global State** — see [notes/bt-integration.md](notes/bt-integration.md)
- **BT Blackboard Key Naming** — see [notes/bt-integration.md](notes/bt-integration.md)
- **Health Check Readiness Gap** — see [notes/codebase-structure.md](notes/codebase-structure.md)
- **Docker Health Check Coordination** — see [notes/codebase-structure.md](notes/codebase-structure.md)
- **FastAPI response_model Filtering** — see [notes/codebase-structure.md](notes/codebase-structure.md)
- **`VulnerabilityCase.case_activity` Cannot Store Typed Activities** — see [notes/activitystreams-semantics.md](notes/activitystreams-semantics.md)
- **Accept/Reject `object` Field Must Use an Inline Typed Activity Object** — see [notes/activitystreams-semantics.md](notes/activitystreams-semantics.md)
- **Pydantic Union Serialization Silently Returns `None` for `active_embargo`** — see [notes/activitystreams-semantics.md](notes/activitystreams-semantics.md)
- **`case_status` Field Is a List (Rename Pending)** — see [notes/case-state-model.md](notes/case-state-model.md)
- **CaseEvent Trusted Timestamps: Use `record_event()`, Never Copy Activity Timestamps** — see [notes/case-state-model.md](notes/case-state-model.md)
- **ActivityStreams as Wire Format, Not Domain Model** — see [notes/activitystreams-semantics.md](notes/activitystreams-semantics.md)
- **Preserve Subclass Identity in ActivityStreams Decorators** — see [notes/activitystreams-semantics.md](notes/activitystreams-semantics.md)
- **Black Can Invalidate Inline pyright Suppressions on Wrapped Fields** — see [notes/codebase-structure.md](notes/codebase-structure.md)
- **Pytest `filterwarnings = ["error"]` Does Not Catch All Warnings** — moved to `test/AGENTS.md`
- **Pytest Helper Enums Must Not Use `Test*` Names** — moved to `test/AGENTS.md`
- **Avoid `BaseModel` in Port/Adapter Type Hints** — see [notes/architecture-ports-and-adapters.md](notes/architecture-ports-and-adapters.md)
- **Activity `name` Field Must Not Use `repr()` or `str()`** — see [notes/activitystreams-semantics.md](notes/activitystreams-semantics.md)
- **Actor IDs Must Always Be Full URIs** — see [notes/codebase-structure.md](notes/codebase-structure.md)
- **BT Failure Reason: Use `get_failure_reason()`, Not Generic Error Logs** — see [notes/bt-integration.md](notes/bt-integration.md)
- **Dead-Letter vs. No-Pattern: Two Distinct UNKNOWN Failure Modes** — see [notes/activitystreams-semantics.md](notes/activitystreams-semantics.md)
- **Accept.object_ Must Be the Invite Activity, Not the Case Object** — see [notes/activitystreams-semantics.md](notes/activitystreams-semantics.md)
- **Actor ID Normalization in Trigger Paths: Resolve Path Params Before Outbox** — see [notes/codebase-structure.md](notes/codebase-structure.md)
- **Trigger-Side Embargo Ownership Gate (Owner vs. Participant)** — see [notes/participant-embargo-consent.md](notes/participant-embargo-consent.md)
- **Note Attachment Idempotency: Check `case.notes`, Not DataLayer Existence** — see [notes/bt-integration.md](notes/bt-integration.md)
- **Transitive Activity `object_` Contract at Base Type** — see [notes/activitystreams-semantics.md](notes/activitystreams-semantics.md)
- **Base-Typed Serialization Drops Subtype Fields: Use `serialize_as_any=True`** — see [notes/activitystreams-semantics.md](notes/activitystreams-semantics.md)
- **Invite Response Parsing Requires Recursive Rehydration** — see [notes/activitystreams-semantics.md](notes/activitystreams-semantics.md)
- **Scenario Demos Must Puppeteer via Trigger Endpoints, Not Spoof Inboxes** — see [notes/event-driven-control-flow.md](notes/event-driven-control-flow.md)
- **Role Taxonomies Must Not Leak Into Parameter Names** — When renaming a role concept (e.g., "finder" → "reporter"), search adapter and demo layers as well as core. Demo helpers often mirror public parameter names; leaving them behind creates naming inconsistency. See `notes/bugfix-workflow.md`.
- **Close Bugs With Evidence, Not Assumption** — see [notes/bt-integration.md](notes/bt-integration.md)
- **Use `isinstance` for Pyright Attribute Narrowing, Not `# type: ignore`** — When
  accessing an attribute that exists on a subtype but not its base type (pyright
  `[attr-defined]` error), narrow with a runtime `isinstance` assertion rather than
  suppressing the error with `# type: ignore`. Example: if `as_Question` does not have
  `one_of` but `ChoosePreferredEmbargoActivity` does, add
  `assert isinstance(activity, ChoosePreferredEmbargoActivity)` before accessing
  `activity.one_of`. This keeps the type checker accurate and makes implicit subtype
  assumptions explicit and runtime-verified.
- **Untyped Closures Are Invisible to mypy — Extract to Named Functions** — When
  refactoring or extracting logic from an untyped function body or closure (e.g.,
  inside `extractor.py`), mypy does not check the body of untyped functions.
  Hidden type errors only surface once the code is promoted to a named, typed
  function. Always extract closures to named, fully-typed helper functions; do not
  leave logic inside untyped lambda or nested-function bodies. Specifically: AS2
  fields that carry an object or ID reference (e.g., `context`, `origin`,
  `in_reply_to`) MUST be converted to `str | None` using `_get_id(field)` before
  assigning to a `NonEmptyString | None` snapshot field — passing the raw AS2
  object directly is a type error that mypy will catch only after extraction.

> **Parallelism and Single-Agent Testing** has moved to `test/AGENTS.md`.
>
## Skill Interaction Rules

When a skill requires user input or asks the user a question:

- **Always use the `ask_user` tool.** Never ask questions in plain text
  output — plain text questions are easy to miss and produce no structured
  response.
- Provide a recommended answer or a `choices` array (with the recommended
  option first) on every `ask_user` call.
- The `grill-me` skill is the canonical example: it interviews the user one
  question at a time using `ask_user`. All skills that include an interview
  or clarification phase MUST follow the same pattern.
- When skills compose (e.g., `learn` invokes `grill-me`, `build` invokes
  `study-project-docs`), the `ask_user` rule applies transitively — each
  invoked skill must also use `ask_user` for any user-facing questions.

---

## Governance note for agents

- Agents MAY update `AGENTS.md` to correct or clarify agent rules, but
  substantive changes to this file SHOULD be discussed with a human maintainer
  via Issue or PR. If an agent edits `AGENTS.md`, it must include a short
  rationale in the commit message and open a PR for human review.

---

## Miscellaneous tips

Do not use `black` to format markdown files, it is for python files only.
Use `markdownlint-cli2` for linting markdown. The default config
(`.markdownlint-cli2.yaml`) ignores only `wip_notes/**`.
All other directories (`specs/`, `notes/`, `docs/`, `plan/`) are linted
by the default config.

### Notes frontmatter maintenance (NF-06-001, NF-06-002)

Every `notes/*.md` file (except `notes/README.md`) MUST have a YAML
frontmatter block with at least `title` and `status` fields. Valid statuses:
`active`, `draft`, `superseded` (requires `superseded_by`), `archived`.
When modifying a notes file, review and update its frontmatter. Schema:
`vultron/metadata/notes/schema.py`; enforced by pre-commit hook and
`test/metadata/test_notes_frontmatter.py`.

### Docs links must be relative

Links in `docs/` MUST be relative to the current file and MUST NOT go above
the `docs/` root. Run `uv run mkdocs build --strict` before committing any
`docs/` changes (see `build-docs` skill).

### Demo script lifecycle logging

Use `demo_step` / `demo_check` context managers (`vultron/demo/utils.py`) to
wrap every workflow step and verification block. See `notes/codebase-structure.md`
"Demo Script Lifecycle Logging" for the full pattern.

### Archiving IMPLEMENTATION_PLAN.md

`plan/IMPLEMENTATION_PLAN.md` is the forward-looking roadmap (target < 400
lines). Completed phase details belong in `plan/history/` via the
`append-history` tool. See `specs/project-documentation.yaml` `PD-02-001`
and `specs/history-management.yaml` HM-03.

### Writing project history entries

History entries live under `plan/history/YYMM/<type>/<entry-id>.md`. Use the
`append-history` CLI tool — **never** append directly to files in
`plan/history/`. See `specs/history-management.yaml` (HM-01–HM-05) and
`notes/history-management.md` for the format and usage. During `study-project-docs`,
read only `plan/*.md` — access `plan/history/` only for investigating
completed work.
