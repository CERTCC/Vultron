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
- FastAPI deployment entrypoint: use
  `vultron.adapters.driving.fastapi.main:app` for uvicorn/ASGI startup.
  The mounted `app_v2` object in
  `vultron.adapters.driving.fastapi.app` is for local test/dev patterns
  (for example, isolated app-factory tests).
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

> **Architecture details** (layer rules, hexagonal architecture, message
> pipeline): see [notes/architecture-hexagonal.md](notes/architecture-hexagonal.md).

## Coding Rules (Non-Negotiable)

### Naming Conventions

- **Domain class names**: Use CVD-domain vocabulary, not wire-format parallels
  (e.g., `CaseTransferOffer` not `VultronOffer`). See CS-12-001.
- **Vulnerability**: Abbreviated as `vul` (not `vuln`)
- Wire-layer naming (as\_ prefix, trailing underscore, pattern objects) →
  see [`vultron/wire/as2/AGENTS.md`](vultron/wire/as2/AGENTS.md)
- Use-case / handler naming (Received suffix, Svc prefix, \_trigger suffix)
  → see [`vultron/core/AGENTS.md`](vultron/core/AGENTS.md)

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

See [`vultron/core/AGENTS.md`](vultron/core/AGENTS.md) — use-case protocol
and dispatcher routing.

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

See [`vultron/core/AGENTS.md`](vultron/core/AGENTS.md) for the full
six-step checklist (enum → pattern → use-case → map → tests).

### Key Files Map

- **Enums / MessageSemantics**: `vultron/core/models/events/base.py`
- **Dispatcher**: `vultron/core/dispatcher.py`
- **Inbox**: `vultron/adapters/driving/fastapi/routers/actors.py`
- **Errors**: `vultron/errors.py`
- **Demo**: `vultron/demo/cli.py` (entry point)
- **Case States**: `vultron/case_states/` — enums are authoritative

Full core-layer map → [`vultron/core/AGENTS.md`](vultron/core/AGENTS.md).
Full wire-layer map → [`vultron/wire/as2/AGENTS.md`](vultron/wire/as2/AGENTS.md).
Full adapter-layer map → [`vultron/adapters/AGENTS.md`](vultron/adapters/AGENTS.md).

### Constructing Outbound Activities

All outbound activities MUST use factory functions in
`vultron.wire.as2.factories`. See
[`vultron/wire/as2/AGENTS.md`](vultron/wire/as2/AGENTS.md) for details.

### GitHub Issue Labels

Priority tracking is managed via **GitHub Project #24 ("Vultron Planning")**
using a `Schedule` field with values: `Now`, `Next`, `Later`, `Someday`.
New issues are added to the project with `Schedule=Someday` by default.
Reprioritize by updating the `Schedule` field via the API or by dragging cards
on the board. `group:` labels are no longer used — do not create or assign them.
See `notes/parallel-development.md` for the project board model and API reference.

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
to relevant tests and design notes. Use the decision-tree heuristic in
`notes/specs-vs-adrs.md` (MS-11-001 through MS-11-006) to decide whether a
change warrants a new ADR, a new spec entry, or both.

### Commit Workflow

**Before committing**, run the skills in this order:

1. `format-code` — Black + flake8
2. `run-linters` — all four linters (Black, flake8, mypy, pyright); all MUST pass
3. `run-tests` — unit suite once; read output.
   **If any `vultron/demo/` or `test/demo/` files were modified**, also run
   the full suite (CI always does): `uv run pytest -m "" --tb=short 2>&1 | tail -5`
4. `build-docs` — only when `docs/` files were modified
5. `commit` skill — include Co-authored-by trailer

**Always stage the new entry file when `append-history` was called.** The tool
creates a new entry file under `plan/history/YYMM/<type>/` — stage it with
`git add plan/history/`. The monthly `plan/history/YYMM/README.md` is
**gitignored**; do **not** stage it. Omitting the entry file is the most
common cause of history files being left out of PRs.

See each skill's SKILL.md for the exact commands. If the pre-commit hook
reformats files: `git add -A && git commit -m "Same message"`.

**After a PR merges**, if working in a named worktree slot, reset the slot
so it is ready for the next task:

```bash
bash "$HOME/.copilot/skills/manage-worktree/scripts/manage_worktree.sh" reset <slot-name>
```

---

## Parallel Development (Worktree Slots)

Multiple agents can work concurrently using named git worktree **slots**.
See [`notes/parallel-development.md`](notes/parallel-development.md) for
the GitHub Issue-based coordination model and
`~/.copilot/skills/manage-worktree/SKILL.md` for slot setup and commands.

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

- **Idempotency Responsibility Chain** — see
  [`vultron/core/AGENTS.md`](vultron/core/AGENTS.md)

---

### Reference index

- **Circular Imports** — see [notes/codebase-structure.md](notes/codebase-structure.md)
- **Pattern Matching with ActivityStreams** — see [notes/activitystreams-semantics.md](notes/activitystreams-semantics.md)
- **`SEMANTIC_REGISTRY` Order Errors Fail Silently — `_validate_registry_order()` Required** — A misplaced pattern causes the wrong use case to run with no error. The import-time guard `_validate_registry_order()` raises `RegistryOrderError` immediately. Until it lands, always run `test/test_semantic_activity_patterns.py` after editing the registry. See [notes/semantic-registry.md](notes/semantic-registry.md)
- **Test Data Quality** — moved to `test/AGENTS.md`
- **All Protocol-Significant Behavior MUST Be in the BT** — see [notes/bt-integration.md](notes/bt-integration.md)
- **Protocol Event Cascades (Cascading Automation)** — see [notes/bt-integration.md](notes/bt-integration.md)
- **Post-BT Procedural Cascade Anti-Pattern** — see [notes/bt-integration.md](notes/bt-integration.md)
- **py_trees Blackboard Global State** — see [notes/bt-integration.md](notes/bt-integration.md)
- **py_trees `blackboard.get()` Raises KeyError for Unwritten READ Keys** — see [notes/bt-integration.md](notes/bt-integration.md)
- **Duplicate Method Definitions Silently Shadow Correct BT Logic** — see [notes/bt-integration.md](notes/bt-integration.md)
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
- **Avoid `BaseModel` in Port/Adapter Type Hints** — see [notes/architecture-ports.md](notes/architecture-ports.md)
- **Activity `name` Field Must Not Use `repr()` or `str()`** — see [notes/activitystreams-semantics.md](notes/activitystreams-semantics.md)
- **Actor IDs Must Always Be Full URIs** — see [notes/codebase-structure.md](notes/codebase-structure.md)
- **Co-located Actor IDs Must Be HTTP-Routable; Wire Up `ASGIEmitter` at Startup** — see [notes/architecture-adapters.md](notes/architecture-adapters.md)
- **ASGIEmitter Path Construction: Use Scheme+Netloc Only as `httpx` Base URL** — see [notes/asgi-emitter.md](notes/asgi-emitter.md)
- **`create_app()` MUST NOT Mutate Module-Level Singletons** — see [notes/asgi-emitter.md](notes/asgi-emitter.md)
- **Bootstrap Activities Must Embed Nested Objects Inline, Not as URI Strings** — see [notes/activitystreams-semantics.md](notes/activitystreams-semantics.md)
- **BT Failure Reason: Use `get_failure_reason()`, Not Generic Error Logs** — see [notes/bt-integration.md](notes/bt-integration.md)
- **Dead-Letter vs. No-Pattern: Two Distinct UNKNOWN Failure Modes** — see [notes/activitystreams-semantics.md](notes/activitystreams-semantics.md)
- **Accept.object_ Must Be the Invite Activity, Not the Case Object** — see [notes/activitystreams-semantics.md](notes/activitystreams-semantics.md)
- **Actor ID Normalization in Trigger Paths: Resolve Path Params Before Outbox** — see [notes/codebase-structure.md](notes/codebase-structure.md)
- **Trigger-Side Embargo Ownership Gate (Owner vs. Participant)** — see [notes/participant-embargo-consent.md](notes/participant-embargo-consent.md)
- **Inline `EMAdapter` Instantiation Is an Anti-Pattern** — Trigger and received
  use cases MUST NOT instantiate `create_em_machine()` + `EMAdapter` inline in
  `execute()` methods. Once `EmbargoLifecycle` (#538) lands, delegate all EM +
  PEC transitions to it. Until then, add a `# TODO(#538)` comment so the
  duplication is discoverable. Always cascade PEC alongside EM transitions
  (`_cascade_pec_revise` on `ACTIVE → REVISE`; `_cascade_pec_reset` on
  termination). See [notes/embargo-lifecycle.md](notes/embargo-lifecycle.md).
- **Note Attachment Idempotency: Check `case.notes`, Not DataLayer Existence** — see [notes/bt-integration.md](notes/bt-integration.md)
- **Transitive Activity `object_` Contract at Base Type** — see [notes/activitystreams-semantics.md](notes/activitystreams-semantics.md)
- **Base-Typed Serialization Drops Subtype Fields: Use `serialize_as_any=True`** — see [notes/activitystreams-semantics.md](notes/activitystreams-semantics.md)
- **Invite Response Parsing Requires Recursive Rehydration** — see [notes/activitystreams-semantics.md](notes/activitystreams-semantics.md)
- **Scenario Demos Must Puppeteer via Trigger Endpoints, Not Spoof Inboxes** — see [notes/event-driven-control-flow.md](notes/event-driven-control-flow.md)
- **Role Taxonomies Must Not Leak Into Parameter Names** — When renaming a role concept (e.g., "finder" → "reporter"), search adapter and demo layers as well as core. Demo helpers often mirror public parameter names; leaving them behind creates naming inconsistency. See `notes/bugfix-workflow.md`.
- **`case_addressees()` Is the Wrong Recipient for Participant Outbound Messages** — After
  case creation, participant-originated activities MUST be addressed only to the Case Actor
  (`CVDRole.CASE_MANAGER` participant's `attributed_to`), not to `case_addressees()`.
  Using `case_addressees()` on the sender side bypasses the CaseActor and violates the
  `participant → CaseActor → CaseLogEntry → broadcast → participants` model
  (PCR-08-001, PCR-08-002). `case_addressees()` is correct only on the Case Actor's
  **outbound fan-out** side (broadcasting to all participants). See
  [notes/case-communication-model.md](notes/case-communication-model.md).
- **Close Bugs With Evidence, Not Assumption** — see [notes/bt-integration.md](notes/bt-integration.md)
- **Use `isinstance` for Pyright Attribute Narrowing, Not `# type: ignore`** — see [`vultron/core/AGENTS.md`](vultron/core/AGENTS.md)
- **Untyped Closures Are Invisible to mypy — Extract to Named Functions** — see [`vultron/core/AGENTS.md`](vultron/core/AGENTS.md)
- **CI Runs All Tests; Default Local Run Omits Integration** — see `test/AGENTS.md` § Integration Tests

> **Parallelism and Single-Agent Testing** has moved to `test/AGENTS.md`.
>
- **Adding a New Pitfall: Check the Routing Policy First** — see
  [notes/agents-md-structure.md](notes/agents-md-structure.md)

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

See [`vultron/adapters/AGENTS.md`](vultron/adapters/AGENTS.md) for the
`demo_step` / `demo_check` pattern.

### Writing project history entries

History entries live under `plan/history/YYMM/<type>/<entry-id>.md`. Use the
`append-history` CLI tool — **never** append directly to files in
`plan/history/`. See `specs/history-management.yaml` (HM-01–HM-05) and
`notes/history-management.md` for the format and usage. During `study-project-docs`,
read only `plan/*.md` — access `plan/history/` only for investigating
completed work.
