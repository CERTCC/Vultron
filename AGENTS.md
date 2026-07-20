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
  see [`vultron/wire/as2/AGENTS.md`](vultron/wire/as2/AGENTS.md).
  **Critical**: ALL classes in `vultron/wire/as2/vocab/objects/` use the
  `as_` prefix (`as_VulnerabilityCase`, `as_CaseParticipant`, etc.). The
  bare name `VulnerabilityCase` (no prefix) always refers to the **core**
  domain model. See ARCH-14-001.
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
- **Validate at the edge, promote to the core (ADR-0032)**: Wire-layer and
  adapter objects may have `Optional` fields. Before passing data to core
  logic, validate that required fields are present and raise a descriptive
  exception if not. What core functions receive should be a type that makes
  required fields non-optional — no `if x is None` guards needed inside core.
- **Collection defaults**: collection-typed fields and parameters default to
  the empty collection (`[]`, `{}`, `set()`), not `None`. Use
  `field(default_factory=list)` etc. `None` is only correct when absence is
  semantically distinct from empty (e.g. AS2 fields where `None` omits the
  key from the wire payload, or deliberate sentinels like
  `BTExecutionResult.errors`).
- **Core helpers raise, never return `None`**: core domain helpers and BT node
  helpers raise a descriptive exception on failure. In BT nodes, `update()` is
  the sole `try/except` handler; helper methods are clean typed functions that
  either succeed or raise. See `notes/bt-integration.md` § "BT-HELPER-01".
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
- **Inbox**: `vultron/adapters/driving/fastapi/routers/actors/` (package; `_routes.py` defines endpoints)
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

**When opening a PR**, use the structured body template in
`.agents/skills/shared/pr-body-guide.md`. Implementation PRs require
**Summary + Changes + Verification** (with actual test counts); docs-only
PRs use **Summary + Changes**. Always put closing references
(`- Closes #N`) at the top, one per line.

**Always stage the new entry file when `append-history` was called.** The tool
creates a new entry file under `plan/history/YYMM/<type>/` — stage it with
`git add plan/history/`. The monthly `plan/history/YYMM/README.md` is
**gitignored**; do **not** stage it. Omitting the entry file is the most
common cause of history files being left out of PRs.

See each skill's SKILL.md for the exact commands. Pre-commit hooks are
fail-only (no auto-fix); if a hook fails, run the relevant skill
(`format-code` for black/markdown, `run-linters` for flake8) to fix and
re-stage before committing.

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
- **NEVER run `git worktree prune` (or `git gc` / any pruning command) in this
  repo.** The `.git` common directory is **shared across multiple environments**
  (host macOS checkouts *and* dev-container checkouts) via mounts. `prune` deletes
  the admin metadata (`gitdir`/`commondir`/`HEAD`/`index`) for every worktree
  whose checkout path is not resolvable *from the current environment* — which
  silently destroys live worktrees belonging to other containers/the host, not
  just stale ones. A worktree registered under a path the current environment
  can't see always looks "prunable" but usually is not. If `git worktree list`
  shows `prunable` entries, **leave them**; verify with the human before removing
  any worktree. Recovery after an erroneous prune is possible (refs/objects
  survive) but requires hand-rebuilding each admin dir — see
  [`notes/parallel-development.md`](notes/parallel-development.md).

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

## Quality Standard

Every workflow skill reads `.claude/skills/shared/completeness-doctrine.md`
via `orient-agent`. The full doctrine is there; this is the summary:

- **"Done" requires**: all changed behaviors tested, edge cases handled,
  types/docs current, linters clean.
- **Depth within scope is non-negotiable**: happy-path-only is not done; a
  behavior with no test is not done.
- **Scope expansion**: ask if user is present; make best-judgment call if not,
  record rationale as a learning file.
- **Finding severity**: **FAIL** (broken) → fix before PR opens. **IMPROVE**
  (correct but incomplete) → fix in this session. **DEFER** (out of scope) →
  create follow-up issue + get user acknowledgment. No WARN-and-defer.

---

## Common Pitfalls (Lessons Learned)

Key pitfall write-ups are in the `notes/` files.
Short entries are reproduced here; longer ones are referenced below.

- **Production Adapters MUST NOT Import from `vultron/demo/` for Config** —
  `vultron/demo/` is scaffolding; its modules MUST NOT be imported by
  production adapter code.  Actor policy configuration (`auto_create_case`,
  `default_case_roles`) belongs in `AppConfig.actor` (read via
  `get_config().actor` from `vultron/config/`), not in `SeedConfig`.
  See [notes/configuration.md](notes/configuration.md) § "Current Architecture"
  and specs CFG-07-005 through CFG-07-007.
- **Idempotency Responsibility Chain** — see
  [`vultron/core/AGENTS.md`](vultron/core/AGENTS.md)
- **Bulk Logging-Level Refactors Need a Consistency Grep Pass** — After
  changing log levels across many BT tree-creation functions, run a grep-based
  consistency check before commit so no matching functions are left at the old
  level.
- **Case-Actor Broadcast Guard Tests Need a Third Participant** — Positive
  tests for Case Manager broadcast fan-out must include at least one non-sender
  peer, or the broadcast-addressing assertion becomes vacuous.
- **Case Participant Lookup Must Fail Fast on Surface Divergence** —
  `case_participants` is the source of truth and `actor_participant_index` is
  only a derived lookup cache. Lookup helpers MUST NOT silently choose the
  populated surface; if the surfaces disagree, surface the mismatch and fix
  the write path or fixture. However, do NOT treat a missing cache entry as
  fatal when canonical participant data exists — fail only on contradictions
  (cache returns a wrong/stale participant), not on cache misses. The
  recommended resolution order: check `actor_participant_index` for a direct
  hit first, then scan `case_participants` as the authoritative fallback.
- **Orphan Module Cleanup Requires Importer Proof** — Before deleting
  scaffolding or suspected-dead modules, verify there are no live importers in
  both `vultron/` and `test/`; then prefer deletion over leaving dead code.
- **Worktree Sync Checks Need Ancestry Verification** — `git rebase origin/main`
  alone can mislead when branch ancestry is wrong. Use the manage-worktree
  `ensure-synced` flow (or explicitly verify behind-count/merge-base) before
  creating a task branch.

---

### Reference index

- **Circular Imports** — see [notes/codebase-structure.md](notes/codebase-structure.md)
- **Pattern Matching with ActivityStreams** — see [notes/activitystreams-semantics.md](notes/activitystreams-semantics.md)
- **`SEMANTIC_REGISTRY` Order Errors Fail Silently — `_validate_registry_order()` Required** — A misplaced pattern causes the wrong use case to run with no error. The import-time guard `_validate_registry_order()` raises `RegistryOrderError` immediately. Until it lands, always run `test/test_semantic_activity_patterns.py` after editing the registry. See [vultron/wire/as2/AGENTS.md](vultron/wire/as2/AGENTS.md)
- **Test Data Quality** — moved to `test/AGENTS.md`
- **All Protocol-Significant Behavior MUST Be in the BT** — see [notes/bt-integration.md](notes/bt-integration.md)
- **Protocol Event Cascades (Cascading Automation)** — see [notes/bt-integration.md](notes/bt-integration.md)
- **Post-BT Procedural Cascade Anti-Pattern** — see [notes/bt-integration.md](notes/bt-integration.md)
- **Peer Broadcast Nodes Must Not Mask Delivery Failure with SUCCESS** — For
  protocol-visible fan-out, BT nodes/subtrees MUST return `FAILURE` when
  activity construction or outbox enqueue fails. A guaranteed SUCCESS fallback
  causes silent state divergence across peers. See
  [notes/peer-broadcast-failure-semantics.md](notes/peer-broadcast-failure-semantics.md)
  and `specs/behavior-tree-integration.yaml` BT-14-001.
- **BT Node MUST NOT Call a Use Case** — A BT node's `update()` MUST NOT
  instantiate or call a use-case class. Use cases create BTs; BT nodes are
  leaves of those trees. Calling a use case from inside a node creates an
  auditable-breaking BT→UseCase→BT chain. Compose the sub-behavior as a
  child subtree instead. See [notes/bt-integration.md](notes/bt-integration.md)
  § "DO NOT: BT node calling a use case".
- **BT Node MUST NOT Import From Use Case Modules** — Dependency direction is
  `use_cases/ → behaviors/`, never the reverse. If a helper is needed in
  both layers, extract it to a shared utility. See
  [notes/bt-integration.md](notes/bt-integration.md)
  § "DO NOT: BT node importing from use case modules".
- **Avoid God BT Nodes: `update()` MUST Stay Small** — An `update()` method
  exceeding ~20–30 lines is a god node. Decompose into a named subtree of
  simple leaf nodes; the tree structure becomes the workflow documentation.
  See [notes/bt-integration.md](notes/bt-integration.md)
  § "DO NOT: God BT nodes with long `update()` methods".
- **BT Emit Nodes: Inherit Base Classes, Never Reimplement Guard Boilerplate**
  — Before writing `if self.datalayer is None`, `if self.actor_id is None`, or
  `if self.trigger_activity_factory is None` in a new BT node's `update()`,
  check whether a base class already handles these guards. `DataLayerAction`
  provides `self.datalayer`, `self.actor_id`, and `self.trigger_activity_factory`
  resolution. Emit nodes that route report-phase activities through the CaseActor
  SHOULD inherit from `_EmitCaseActorReportActivityBase` and override only
  `_call_factory()`. Reimplementing this boilerplate per-class is the root cause
  of god-node `update()` methods: each copy accumulates independently and must be
  fixed separately. See `specs/behavior-tree-node-design.yaml` BTND-07-005.
- **Flat `nodes.py` in BT Areas Is Non-Compliant** — BT-bearing process
  areas under `vultron/core/behaviors/` MUST use a `nodes/` subpackage for
  leaf nodes and MUST keep tree composition in root `*_tree.py` modules.
  A flat `nodes.py` in a BT area is non-compliant regardless of size.
  Group leaf submodules by semantic concern (e.g., `conditions.py`,
  `case_setup.py`, `participant.py`, `embargo.py`, `communication.py`,
  `lifecycle.py`). The `__init__.py` MUST re-export all public names to
  preserve caller import paths. See
  `specs/behavior-tree-node-design.yaml` BTND-07-001 and BTND-07-003.
- **Splits Must Not Produce New God Modules** — When splitting a large
  module into a subpackage, each resulting submodule must itself stay under
  500 lines (BTND-07-004, CS-18-002). The split pattern is **recursive**: a submodule
  that re-accumulates size across multiple concerns must be further
  decomposed. For example, splitting `case/nodes.py` into a `nodes/`
  package produced `nodes/participant.py` at 816 lines — that file is itself
  a candidate for further splitting. Monitor new submodule line counts after
  every split PR and open a follow-up issue when any submodule exceeds 500
  lines and mixes responsibilities. See `specs/code-style.yaml` CS-18-001
  through CS-18-004.
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
- **Avoid `BaseModel` in Port/Adapter Type Hints** — see [vultron/core/ports/AGENTS.md](vultron/core/ports/AGENTS.md)
- **Activity `name` Field Must Not Use `repr()` or `str()`** — see [notes/activitystreams-semantics.md](notes/activitystreams-semantics.md)
- **Actor IDs Must Always Be Full URIs** — see [notes/codebase-structure.md](notes/codebase-structure.md)
- **Co-located Actor IDs Must Be HTTP-Routable; Wire Up `ASGIEmitter` at Startup** — see [notes/architecture-adapters.md](notes/architecture-adapters.md)
- **ASGIEmitter Path Construction: Use Scheme+Netloc Only as `httpx` Base URL** — see [vultron/adapters/driven/AGENTS.md](vultron/adapters/driven/AGENTS.md)
- **`create_app()` MUST NOT Mutate Module-Level Singletons** — see [vultron/adapters/driven/AGENTS.md](vultron/adapters/driven/AGENTS.md)
- **Bootstrap Activities Must Embed Nested Objects Inline, Not as URI Strings** — see [notes/activitystreams-semantics.md](notes/activitystreams-semantics.md)
- **Factory Parameters MUST Be Core Objects, Not Pre-Built Wire Stubs** — When a factory
  function takes a parameter that represents a domain entity (e.g. `target: VulnerabilityCase`
  for an invite), the caller MUST pass the core object and let the factory project it to a
  wire type. Adapters and BT nodes MUST NOT pre-build a partial wire stub
  (e.g. `VulnerabilityCaseStub`) to hand to the factory — that moves projection logic out
  of the factory and into a layer that should be a thin pass-through. The typical failure
  mode: the adapter only has a URI string for a related entity (e.g. `case.active_embargo:
  str | None`) and can't include nested fields (e.g. `end_time`) without an extra DataLayer
  read that it never makes. The factory, holding the full domain object, can project
  everything correctly. See `specs/activity-factories.yaml` AF-01-005 and
  [notes/activity-factories.md](notes/activity-factories.md)
  § "Anti-pattern: Projection Logic in the Adapter".
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
  `participant → CaseActor → CaseLedgerEntry → broadcast → participants` model
  (PCR-08-001, PCR-08-002). `case_addressees()` is correct only on the Case Actor's
  **outbound fan-out** side (broadcasting to all participants). See
  [notes/case-communication-model.md](notes/case-communication-model.md).
- **Received-Side Use Cases MUST NOT Spoof Another Actor's Identity** — A received-side
  use case runs in one actor's DataLayer context. It MUST NOT build an ActivityStreams
  activity with `actor` set to a different actor's ID, and MUST NOT execute a Behavior
  Tree with `actor_id` set to any actor other than the one whose DataLayer is active.
  Example violation: `AcceptInviteActorToCaseReceivedUseCase` (running on the Case Actor)
  calling `PrioritizeBT(actor_id=invitee_id)` — the BT emits `RmEngageCaseActivity` as if
  from the invitee and transitions their RM state from the wrong DataLayer context. The
  correct fix is an inline RM state update on the receiving actor's DataLayer; the
  `Accept(Invite)` message IS the invitee's engage decision (PCR-08-009, PCR-08-010).
  See [notes/case-communication-model.md](notes/case-communication-model.md)
  § "Antipattern: Identity Spoofing in Received-Side Use Cases".
- **Received-Side Guarded Commit MUST NOT Resolve a Foreign CaseActor ID** — Resolving
  `case_actor_id` from the DataLayer and passing it as `actor_id` to
  `BTBridge.execute_with_setup` from a non-CaseActor inbox context is an identity-spoofing
  violation (CLP-10-003). The canonical pattern (see `status.py::_commit_log_cascade_bt`)
  requires a strict pre-flight guard: `if receiving_actor_id != case_actor_id: return`.
  The guarded commit BT must only run when the receiving actor IS the CaseActor — at which
  point `actor_id=receiving_actor_id` is correct and no identity spoofing occurs. For the
  CaseActor to receive the activity in the first place, the trigger tree MUST emit an
  outbound activity addressed to `case_manager_id` (CLP-10-001). See ADR-0021 and
  [notes/case-communication-model.md](notes/case-communication-model.md)
  § "Antipattern: Received-Side Guarded Commit with Foreign CaseActor ID".
- **Invite/Accept Handshake Must Route Through the Case Actor** — `RmInviteToCaseActivity`
  MUST be sent with `actor=case_actor_id` (not the case owner) from the Case Actor's
  outbox. The invitee's `Accept` MUST be addressed to the Case Actor, not the case owner.
  The "owner triggers, Case Actor executes" pattern applies: `SvcInviteActorToCaseUseCase`
  resolves the Case Actor ID, builds the Invite with `actor=case_actor_id` (optionally
  `attributedTo=case_owner_id`), and places it in the Case Actor's outbox (PCR-08-007,
  PCR-08-008). See [notes/case-communication-model.md](notes/case-communication-model.md)
  § "Invite/Accept Handshake Routing".
- **Close Bugs With Evidence, Not Assumption** — see [notes/bt-integration.md](notes/bt-integration.md)
- **BTBridge Thread-Safety (RLock)** — see [notes/bt-integration.md](notes/bt-integration.md) § "Concurrency Model"
- **BT Result Channel for Domain Errors** — see [notes/bt-integration.md](notes/bt-integration.md) § "BT Result Channel for Domain Errors"
- **Lenient vs. Strict Participant Lookup Node Variants** — see [notes/bt-integration.md](notes/bt-integration.md) § "Lenient vs. Strict Participant Lookup Node Variants"
- **Decomposed BT Leaf Missing-Key Must Return FAILURE** — see [notes/bt-integration.md](notes/bt-integration.md) § "Decomposed BT Leaf Must Return FAILURE for Missing Blackboard Keys"
- **Embargo Subtree Idempotency** — see [notes/bt-integration.md](notes/bt-integration.md) § "Embargo Subtree Idempotency with Blackboard Flag"
- **Vocabulary Override Must Preserve Base Registration** — see [notes/vocabulary-registry.md](notes/vocabulary-registry.md) § "Vocabulary Override Preservation"
- **Surrogate-Key Routing Collision** — see [notes/codebase-structure.md](notes/codebase-structure.md) § "Surrogate-Key Routing Collision Handling"
- **Use `isinstance` for Pyright Attribute Narrowing, Not `# type: ignore`** — see [`vultron/core/AGENTS.md`](vultron/core/AGENTS.md)
- **Untyped Closures Are Invisible to mypy — Extract to Named Functions** — see [`vultron/core/AGENTS.md`](vultron/core/AGENTS.md)
- **CI Runs All Tests; Default Local Run Omits Integration** — see `test/AGENTS.md` § Integration Tests
- **Canonical Ledger Commits Must Be Role-Gated and Coverage-Checked, Not
  Conventionally Trusted** — A canonical-write node
  (`CommitCaseLedgerEntryNode`) reachable from more than one call site or
  more than one actor context MUST be wrapped in a role-gated
  Selector/Sequence/Success composite (see
  `notes/bt-integration.md` § "Guarded Commit: Role-Gated Canonical
  Writes"), and every protocol-significant use case MUST be covered by a
  test asserting it reaches a commit — do not rely on manual audit to find
  missing or unguarded commits after the fact. See
  `specs/case-ledger-processing.yaml` CLP-09 and
  `notes/case-ledger-authority.md` § "Commit Authorization and Coverage".
- **Superseded `notes/*.md` Files Must Move to `archived_notes/`, Not Stay in `notes/`** — A file
  with `status: superseded` in its frontmatter MUST be moved to `archived_notes/` using `git mv`.
  Leaving it in `notes/` causes agents to load outdated guidance as active context and pollutes
  `notes/README.md` navigation. When moving, update `archived_notes/README.md` and remove any
  reference to the file from `notes/README.md`. Future-stub items referenced in the superseded file
  MUST have tracked GitHub Issues before archiving. See `specs/project-documentation.yaml`
  PD-03-004 and PD-03-005.

> **Parallelism and Single-Agent Testing** has moved to `test/AGENTS.md`.
>
- **Stub Adapter Files Must Raise `NotImplementedError`, Not Silently No-Op** — Adapter
  files that are intentional future-work placeholders (e.g.,
  `adapters/driven/prod_http_delivery.py`, `adapters/driving/shared_inbox.py`) MUST contain
  a class or function that raises `NotImplementedError` when called, so any code that
  accidentally references the stub gets an immediate, explicit signal instead of a
  silent no-op. A docstring-only stub is indistinguishable from a real empty module
  and can hide integration gaps in production-like deployments. See
  `specs/outbox.yaml` OX-10-004, OX-11-004.
- **Trigger Use Cases Need Per-Use-Case Tests; Don't Bundle Case + Embargo
  Trigger Changes in One PR** — Every use case in
  `vultron/core/use_cases/triggers/` SHOULD have a dedicated unit test that
  exercises its `execute()` path (state transition + outbox + documented
  failure modes). Incidental coverage via `test_trignotify.py` or scenario
  demos is insufficient — when `triggers/case.py` accumulated 26 commits in
  90 days (#652), half its use cases had no dedicated test and regressions
  in case logic shipped behind embargo fixes. Also avoid bundling
  case-trigger and embargo-trigger changes in the same PR unless the change
  is intrinsically cross-cutting; bundled diffs let reviewers miss
  regressions in the half they aren't focused on. See
  [notes/triggers-test-coverage.md](notes/triggers-test-coverage.md).
- **Hash-Chain Ledger Record vs. Domain Model** — Two distinct classes exist for case
  ledger entries. `vultron.core.models.case_ledger.HashChainLedgerRecord` (`BaseModel`) is
  the in-memory hash-chain record used by `CaseLedger` for local SYNC-1 processing
  — it is **not** persisted or shared over the wire. `vultron.core.models.case_ledger_entry.CaseLedgerEntry`
  (`CoreObject`) is the wire-serialisable domain model used in
  `Announce(CaseLedgerEntry)` replication activities — it has an auto-computed
  `id_` and registers in `CORE_VOCABULARY`. Always import by full module path and
  verify which class you need. See `specs/architecture.yaml` ARCH-12-007 and
  issue #806.
- **Case Ledger Is Not a Process Log** — The canonical case ledger
  (`CaseLedgerEntry` chain authored by the CaseActor and replicated via
  `Announce(CaseLedgerEntry)`) is **exclusively** for CaseActor-accepted
  protocol-significant assertions. Each entry's `payloadSnapshot` MUST be the
  verbatim asserted AS2 activity (or a deterministic normalization of it) and
  MUST NOT be empty for non-rejection entries. Runtime diagnostics, demo
  checkpoints (e.g., `demo_verification`), troubleshooting markers, and any
  per-actor observability belong in Python `logging` output governed by
  `specs/structured-logging.yaml` — **never** in the canonical case ledger. Do
  NOT use `record_event()` or any canonical commit path as a generic "log
  this thing" sink. See ADR-0019, `specs/case-ledger-processing.yaml` CLP-07,
  and `notes/case-ledger-authority.md` § "Canonical Entry Criteria".
- **Negative-Guard Condition Nodes Are a Readability Anti-Pattern** — Do NOT
  create condition nodes named `IsNotFoo` that return SUCCESS to *skip* an
  effect and FAILURE to *trigger* it.  The backwards semantics force readers to
  mentally invert the condition.  Use positive-precondition Sequences instead:
  `Selector(Sequence(IsFooLedgerEntryNode, ApplyFooNode), Success("FooSkipped"))`.
  See `specs/behavior-tree-node-design.yaml` BTND-08-001, BTND-08-002 and
  `notes/bt-design-patterns.md` § "Idiom Family Selection Guide".
- **Adding a New Pitfall: Check the Routing Policy First** — see
  [notes/agents-md-structure.md](notes/agents-md-structure.md)
- **`as_VulnerabilityCase` (wire) vs `VulnerabilityCase` (core) — Always Check
  Your Prefix** — The core domain model is `VulnerabilityCase` in
  `vultron.core.models.case`. The wire AS2 projection is `as_VulnerabilityCase`
  in `vultron.wire.as2.vocab.objects.vulnerability_case`. This `as_` prefix
  convention applies to **all** classes in `vultron/wire/as2/vocab/objects/`:
  `as_CaseParticipant`, `as_CaseStatus`, `as_VulnerabilityReport`, etc. If you
  see a bare `VulnerabilityCase` import from the wire layer, that is a naming
  violation (ARCH-14-001) — the migration to `as_` prefixes is tracked in GitHub.
  In BT nodes, use cases, and core code: always import the bare-name core type.
  In wire/extractor/factory code: always import the `as_`-prefixed wire type.
  The two objects have identical field names; they differ only in field types
  (core uses `str` IDs, wire uses `ActivityStreamRef[T]` unions). See
  `specs/architecture.yaml` ARCH-14-001.
- **Trigger-Side execute() Must Delegate SM Transitions to BTBridge** — A
  trigger-side `execute()` method that calls `EmbargoLifecycle`, `EMAdapter`,
  or creates `ParticipantStatus` records with a specific `rm_state`/`em_state`
  directly (outside a BT execution context) is a BT-06-006 violation.
  State machine transitions — RM transitions (e.g., `RM.INVALID`, `RM.CLOSED`),
  EM lifecycle transitions (e.g., `propose_embargo`, `terminate_embargo`) — are
  protocol-significant behavior (BT-15-001) and MUST live in BT leaf nodes
  accessed via `bridge.execute_with_setup()`. Only infrastructure glue
  (instantiate BT → set up blackboard → call bridge → check status → extract
  output) is permitted directly in `execute()`. The historical asymmetry between
  `received/` (BTBridge-delegating) and `triggers/` (inline) arose from the
  now-retired "simple CRUD" guidance. See
  [notes/bt-integration.md](notes/bt-integration.md)
  § "Trigger/Received Parity" and `specs/behavior-tree-integration.yaml`
  BT-15-001, BT-15-002.
- **Direct DataLayer Mutations in execute() Are Not Caught by the
  Import-Based Ratchet** — `test/architecture/test_single_bt_execution_received_side.py`
  detects direct imports of `create_guarded_commit_case_ledger_entry_tree`
  and (after #1074) multi-`execute_with_setup` call patterns, but it does
  **not** detect `self._dl.save()`, `self._dl.create()`, `self._dl.update()`,
  or `self._dl.delete()` called directly inside `execute()`. These direct
  mutations bypass the BT audit trail, skip the hash-chained ledger-commit
  path, and constitute protocol-significant behavior outside the tree — the
  exact anti-pattern BT-06-001 and BT-15-001 prohibit. A second AST-based
  ratchet (`test/architecture/test_no_dl_mutations_in_execute.py`) tracks the
  known violations (issue #1071). Until a file is removed from
  `KNOWN_VIOLATIONS`, do **not** add new `dl.*()` calls in its `execute()`.
  Any new `execute()` method MUST delegate all DataLayer mutations to a BT
  leaf node via `execute_with_setup()`.
- **Receive-Side BTs Must Record the Triggering Activity Before Applying
  Protocol Effects** — In any receive-side BT tree that contains a
  `GuardedCommitCaseLedgerEntryBT` subtree (via
  `create_guarded_commit_case_ledger_entry_tree`), the commit subtree MUST
  appear BEFORE any protocol-effect node (state transitions, outbox enqueues,
  participant record mutations). Pure precondition-guard nodes (read-only
  checks that return FAILURE without writing state) MAY precede the commit.
  The correct ordering is: (1) precondition guards, (2) commit, (3) all
  protocol effects. Placing effects before the commit inverts causal ordering:
  the case ledger shows effects without the cause that produced them, breaking
  forensic auditability and ledger replication. The commit records that the
  triggering activity was received — this is independent of whether subsequent
  effects succeed. Audit issue #1068 found this inverted ordering consistently
  across receive-side BTs; fix tracked in implementation issues blocked by
  #1052. See `specs/case-ledger-processing.yaml` CLP-10-006.
- **Received-Side execute() Must Not Call commit_log_entry_trigger() Directly** —
  A received-side `execute()` method that calls `commit_log_entry_trigger()`
  (or any wrapper around it) directly is a BT-06-006 violation.
  `Announce(CaseLedgerEntry)` fan-out is protocol-visible (SYNC-02-002) and
  MUST be delegated to `CommitCaseLedgerEntryNode` inside a BT tree executed
  via `BTBridge.execute_with_setup()`. The three historical violators were
  `received/embargo.py`, `received/note.py`, and `received/status.py`. Do
  **not** introduce a parallel BT node (e.g., a node that calls
  `commit_log_entry_trigger()` directly in `update()`) as a workaround — all
  hash-chained ledger commits MUST flow through `CommitCaseLedgerEntryNode`,
  which itself composes `create_commit_log_entry_tree()` via
  `BTBridge.execute_with_setup()`. See `specs/behavior-tree-integration.yaml`
  BT-06-006, BT-15-001, and `specs/sync-ledger-replication.yaml` SYNC-02-002.
- **BTBridge Global Blackboard Is Not Thread-Safe Under FastAPI
  BackgroundTasks** — FastAPI runs synchronous `BackgroundTask` callables
  via `anyio.to_thread.run_sync`, placing them on a thread pool. Two BT
  executions can therefore run on different threads simultaneously, both
  writing to `py_trees.blackboard.Blackboard.storage` (process-global).
  The race: Thread A writes `actor_id=A` and `datalayer=DL_A`; Thread B
  overwrites them; Thread A then reads the wrong `actor_id`, queueing its
  outbound activity under the wrong actor's outbox — the activity is
  silently lost. Fix: wrap the entire setup→execute→cleanup critical section
  in `BTBridge.execute_with_setup` with a module-level `threading.RLock`.
  Use `RLock` (not `Lock`) because lifecycle BT nodes call
  `execute_with_setup` recursively — a plain `Lock` deadlocks there. See
  [notes/bt-integration.md](notes/bt-integration.md) § "Concurrency Model".
- **ResolveCaseManagerNode Requires CASE_MANAGER Participant in Test
  Fixtures** — Replacing `case_addressees()` with canonical
  `_resolve_case_manager_id()` / `ResolveCaseManagerNode` causes tests to
  fail non-obviously when `CASE_MANAGER` is absent: the engage path's RM
  transition fires (→ ACCEPTED), the send then fails, the defer path fires
  (→ DEFERRED), and the test sees `RM=DEFERRED` instead of `RM=ACCEPTED`.
  All test fixtures for BT paths that involve `ResolveCaseManagerNode` MUST
  include a `VultronParticipant` with `CVDRole.CASE_MANAGER` registered in
  `actor_participant_index`. Set `case_participants` and
  `actor_participant_index` directly in the `VulnerabilityCase` constructor
  (not via `add_participant()`, which has a pyright type mismatch). In
  chained integration tests, pass `TriggerActivityAdapter(dl)` to **every**
  use case in the chain — if any receives it as `None`, `CreateCaseActorNode`
  never runs and the CASE_MANAGER participant is never registered.
- **Wire Vocabulary Override Must Preserve Base-Module Registration** —
  Overriding all actor keys in `VOCABULARY` from a Vultron-specific actor
  module can leave `vultron.wire.as2.vocab.base.objects.actors` with zero
  registered concrete types, tripping the registry-completeness invariant.
  Keep at least one base-actors-module registration (e.g., `Actor →
  as_Actor`) and override only concrete keys that need Vultron subclasses
  (`Person`, `Organization`, etc.). See
  [notes/vocabulary-registry.md](notes/vocabulary-registry.md) §
  "Vocabulary Override Preservation".
- **Surrogate-Key Resolution Must Treat Ambiguous Matches as Errors** —
  When `dl.resolve_surrogate_key(key)` finds more than one canonical ID
  matching a short-key tail segment, it MUST raise an error — not silently
  return the first result. Also: case-key resolution MUST continue to the
  short-key fallback even when `dl.read(key)` returns a non-case object;
  non-case IDs must not shadow valid case keys and produce false 404/
  validation failures. See
  [notes/codebase-structure.md](notes/codebase-structure.md) §
  "Surrogate-Key Routing Collision Handling".
- **Use-Case Subpackage Splits Must Re-Export Both Classes and Request
  Models** — When replacing a flat use-case module with a subpackage, add
  explicit `__init__.py` re-exports for both use-case classes AND any
  request models that callers previously imported transitively from the old
  module. Mirror the source split in the test layout with a matching
  subdirectory (`test/core/use_cases/<domain>/`) to keep file organization
  aligned and reduce future merge-conflict hotspots. The nodes/ subpackage
  guidance in this file (§ "Large nodes.py Files Are a Code Smell") applies
  to BT node modules; this rule extends the same principle to use-case
  modules.
- **Transport-Role Naming Must Stay Explicit in Adapter Paths and Classes**
  — Outbound adapter names that describe behavior (`delivery_queue`) instead
  of role (`demo_http_delivery`) create broad documentation and import drift.
  When renaming protocol-significant adapter modules, update all parallel
  references together: core ports docs, adapter notes, ADR references, and
  codebase reference pages. See also the existing pitfall "Role Taxonomies
  Must Not Leak Into Parameter Names".
- **mypy Infers Type From First Branch Assignment — Use Distinct Variable
  Names Per Branch** — Avoid reusing a local variable across two `except`
  (or `if`/`else`) branches that assign different concrete types. For
  example, assigning `error: VultronValidationError` in one branch then
  `error = VultronInvalidStateTransitionError(...)` in the next causes mypy
  to infer the type from the first assignment and flag the second as
  incompatible. Use distinct variable names per branch (e.g.,
  `validation_err`, `transition_err`).
- **Counter-Revision EM Path Must Be Tested Separately** —
  `EM.REVISE → EM.REVISE` (counter-revision) must be tested separately
  from `ACTIVE → REVISE` because `_cascade_pec_revise` only fires on the
  `ACTIVE → REVISE` transition; a counter-revision must leave PEC states
  unchanged. Tests that only cover `ACTIVE → REVISE` do not verify this
  invariant.
- **RM Terminal Guard Must Run Before Same-State Shortcut** —
  `ValidateRMTransitionNode` (and equivalent validators) must evaluate
  terminal `RM.CLOSED` rules before `current == new` no-op checks. Otherwise
  repeated `CLOSED -> CLOSED` retries can flow into append/broadcast paths and
  produce duplicate canonical ledger entries.
- **Do Not Downgrade Existing Consent on Idempotent Retries** —
  when reusing a report-phase `ParticipantStatus` during embargo
  accept/reject retries, preserve any non-null existing consent value; never
  overwrite it with default `NO_EMBARGO` during "upsert" paths.
- **Case-Ledger Demo Endpoint Returns Combined View in Single-DL Tests** —
  `demo_get_case_ledger` currently ignores `actor_id` in single-DataLayer
  test setups and returns a combined case log. Use replica JSONL artifacts for
  per-actor assertions and name helpers accordingly (`_fetch_case_log`).
- **DataLayer Scope Tests: Use `call_args.args`, Not `call_args[0]`** —
  When asserting mock positional arguments in DataLayer scope tests (e.g.,
  for `get_canonical_actor_dl()`), use `mock.call_args.args` (Python 3.8+)
  rather than `mock.call_args[0]`. The named attribute raises `AttributeError`
  clearly if the call shifts to kwargs; the index subscript returns an empty
  tuple silently, masking the assertion failure. Test
  `get_canonical_actor_dl()` directly with explicit keyword args
  (`actor_id=...`, `dl=...`) rather than through FastAPI DI — it is a plain
  Python function and does not require the full app stack.
- **Inbox Policy Logic Must Live in the Core BT Module, Not the FastAPI
  Router** — When adding or modifying inbox processing behavior (parse,
  rehydrate, defer-check, dispatch), the change belongs in
  `vultron/core/behaviors/inbox/` — not in the FastAPI router, not in a new
  adapter-layer pipeline helper. `process_payload` is the sole caller-facing
  entry point; all policy is internal to the BT. Creating a new
  adapter-layer helper or adding logic to the router repeats the V-08
  violation (ADR-0009) and makes the pipeline untestable from non-HTTP entry
  points. See `specs/inbox-orchestration.yaml` IO-02-003 and IO-03-003, and
  `notes/inbox-orchestration.md`.
- **`ProposeCaseToActorNode` Sends `Create(CaseProposal)`; `CreateCaseActorNode`
  Does Not** — These two BT nodes have distinct responsibilities and MUST NOT be
  conflated. `CreateCaseActorNode` registers the case-actor service as an actor
  resource in the local DataLayer; it creates the actor identity, not the case.
  `ProposeCaseToActorNode` sends `Create(as_CaseProposal)` to the already-registered
  case-actor service to initiate the case initialization protocol. Updating
  `CreateCaseActorNode` to send a CaseProposal is a violation of single
  responsibility and causes the proposal to be sent before the actor is ready.
  `ProposeCaseToActorNode` MUST be wired into the case-creation BT tree AFTER
  `CreateCaseActorNode` succeeds. See `specs/case-proposal.yaml` CP-04-002 and
  `notes/case-proposal.md`.
- **Protocol-Declared Fields Must Stay in Sync with Concrete Classes** — When
  a field or method is removed from a concrete class that structurally conforms
  to a `Protocol`, the matching member MUST also be removed from the Protocol.
  Static type checkers verify the concrete→Protocol direction only; a stale
  Protocol member is invisible to mypy/pyright but silently breaks callers that
  accept a `Protocol`-typed parameter and access the removed attribute. Issue #792:
  `CaseModel.events` was left in `protocols.py` after `VulnerabilityCase.events`
  was removed; no lint error occurred, but future callers would have failed at
  runtime. See `specs/code-style.yaml` CS-20-001.
- **`TypeGuard` Discriminators Must Use Protocol-Declared Fields Only** —
  `TypeGuard` functions such as `is_case_model()` MUST use only `hasattr`
  checks on attributes explicitly declared in the target `Protocol`. Using a
  method or field that is NOT in the Protocol as a discriminator causes the guard
  to silently return `False` for valid objects when that method is later removed.
  Issue #888: `is_case_model()` tested `hasattr(obj, "record_event")` — a method
  never on `CaseModel` — and when `record_event()` was removed from
  `VulnerabilityCase`, 440 test failures cascaded before the root cause was
  traced. See `specs/code-style.yaml` CS-20-002.
- **`getattr(obj, name, default)` Does Not Catch `ValueError` from Property
  Getters** — Python's three-argument `getattr` suppresses only `AttributeError`.
  If a property raises `ValueError` — as `VulnerabilityCase.current_status` does
  when `case_statuses` is empty — the default is never returned and the error
  propagates. Use `try/except (AttributeError, ValueError)` instead whenever
  accessing a property that may raise on a partially-initialised object.
  See [notes/domain-validation.md](notes/domain-validation.md)
  § "Pitfall: `getattr(obj, name, default)` Does Not Catch `ValueError`".
- **Core→Wire Conversion: Use `wire_cls.from_core()`, Never `model_dump` +
  `model_validate`** — `wire_cls.model_validate(core_obj.model_dump(...))` breaks
  silently when a wire class has field types that differ from the core class (e.g.
  `as_VulnerabilityCase.case_activity` is `list[as_Activity]`, not `list[str]`).
  `wire_cls.from_core(core_obj)` is the canonical core→wire conversion path; it
  handles all field-type differences via `_field_map` and custom conversion logic.
  See [notes/activity-factories.md](notes/activity-factories.md)
  § "Anti-Pattern: `model_dump` + `model_validate` Instead of `from_core()`".
- **Staged-Type `model_validate` Only Works on Core-Constructed Objects** —
  `EmbargoedCase.model_validate(obj)` and `Case.model_validate(obj)` fail with
  `ValidationError` when `obj` was returned by `dl.read()` or `dl.list_objects()`.
  `dl.read()` returns core domain objects via the vocabulary registry, but their
  nested fields (e.g. `case_statuses`) may still be wire-typed (`as_CaseStatus`),
  which Pydantic rejects at the staged-type boundary. Only attempt
  `model_validate`-based staged-type promotion on objects that were constructed
  through core model paths (e.g. `VulnerabilityCase(...)` constructor). For
  DataLayer results, check pre-conditions (field presence, state predicates)
  directly on the returned object without re-validating through a staged type.
- **Always Use `uv run <tool>` in Devcontainer Workflows** — Bare console-script
  entrypoints (e.g. `spec-dump`, `append-history`) in a devcontainer resolve from
  `/app/.venv/bin/`, which imports `vultron` from the baked image snapshot at
  `/app/vultron/`, not from the mounted working tree. `uv run spec-dump` is
  correct; bare `spec-dump` is not. This applies to all tools installed as
  `[project.scripts]` entry points until `#1460` (devcontainer `/app` mount
  design) is resolved.
- **Walrus Operator for Single-Assignment Guard Blocks** — When a helper returns
  `Status | None` and the only use is an early-return guard, use the walrus
  operator to collapse the two-line pattern:
  `if (f := self._require_factory()) is not None: return f`. This is established
  idiom in `vultron/core/behaviors/`; apply it when reducing `update()` size.
- **`dl.read()` Returns Core Objects — Core MUST NOT Receive or Duck-Type Wire
  Objects** — The DataLayer read path (`dl.read()`, `dl.list_objects()`) MUST
  return **core** domain objects (`vultron/core/models/`), never **wire**
  vocabulary types (`vultron/wire/as2/vocab/objects/`, `as_`-prefixed), for any
  persisted `type_` with a registered `CORE_VOCABULARY` counterpart. Do NOT add
  new structural duck-typing Protocols or `TypeGuard` helpers (the
  `CaseModel` / `is_case_model()` family in `vultron/core/models/protocols.py`)
  to let core operate on DataLayer results without importing concrete core
  types — that pattern evades ARCH-01-001 by hiding a runtime `core → wire`
  dependency from mypy/pyright, and it only works by structural coincidence of
  field names. Core code MUST depend on concrete core classes and real
  `isinstance` narrowing. The one recognised exception is persisted AS2
  Activities (`vultron/wire/as2/vocab/activities/`), which have no core
  counterpart; core reading those back from the DataLayer is a tracked
  boundary violation, not a sanctioned pattern. See ADR-0034,
  `specs/datalayer.yaml` DL-05-001 through DL-05-004, and
  [notes/datalayer-design.md](notes/datalayer-design.md) § "Read Path MUST
  Return Core Objects".
- **Core MUST NOT Re-Read a Wire Activity for Semantic Content — Split
  Semantic vs. Envelope Needs** — `dl.read(activity_id)` in `vultron/core/` to
  recover a domain fact from a stored AS2 Activity (e.g. reading a stored
  `Offer` for its embedded report, or an `Invite` for its case/embargo id) is a
  boundary violation (ARCH-09-001, ARCH-03-001): the activity is being used as
  the system of record for a fact that should live in core. The domain fact MUST
  be captured as **core state** at the point the extractor first interprets the
  inbound activity, and core reads it from there; message-to-message correlation
  (Accept→Invite) MUST resolve through a **core-entity relationship**, never a
  wire re-read. This is NOT a license to clone each AS2 Activity into a 1:1 core
  class — model only the domain fact, in domain vocabulary. Reading a stored
  activity back is sanctioned ONLY to reconstitute the **verbatim original**
  envelope for an outbound reply's inline `object_` (activity ids are
  non-regenerable `urn:uuid:` values and the Actor Knowledge Model requires the
  full inline original), and ONLY via a wire/adapter-owned seam that treats the
  payload as opaque — never core interpreting it. See ADR-0035,
  `specs/datalayer.yaml` DL-06-001 through DL-06-005, and
  [notes/datalayer-design.md](notes/datalayer-design.md) § "Activity Read-Back:
  Semantic Content vs. Envelope Reconstitution".
- **Emit Nodes in Case-Scoped Trigger BTs Must Fail Fast on Missing CaseActor**
  — After switching case-scoped trigger routing from `case_addressees()` to
  CaseActor-only routing, emit nodes must fail fast (FAILURE or immediate
  exception) when no routable CaseActor recipient can be resolved. Silently
  returning without setting `to` causes `VultronOutboxToFieldMissingError` to
  fire deep in the outbox handler, masking the true sender-side routing defect.
  See `specs/participant-case-replica.yaml` PCR-08-011.
- **Module Split: Re-Import Moved Names for `monkeypatch` Compatibility** —
  When splitting a module that is accessed as `import module as m` in tests
  using `monkeypatch.setattr(m, "name", ...)`, moved names MUST be re-imported
  into the original module's namespace (not just defined in the new submodule).
  Without the re-import, the original module has no `name` attribute and
  `monkeypatch.setattr` raises `AttributeError`. Add `# noqa: F401` on re-export
  lines to suppress unused-import lint warnings. Issue #972.
- **FastAPI `dependency_overrides` Key Must Be Re-Exported When Converting a
  Router Module to a Package** — When a test does
  `app.dependency_overrides[actors_router.get_shared_dl]`, it accesses
  `get_shared_dl` as an attribute of the `actors_router` module. Converting
  `actors.py` to an `actors/` package breaks this reference unless
  `get_shared_dl` is explicitly re-exported in `actors/__init__.py`. Before
  finalizing any subpackage `__init__.py`, scan tests for
  `module.dependency_function` attribute-access patterns. Issue #970.
- **Guarded-Commit Tests Must Use the CASE_MANAGER Actor as `receiving_actor_id`**
  — Tests for received-side use cases that exercise a guarded-commit BT path
  MUST set `receiving_actor_id` to the actor holding `CVDRole.CASE_MANAGER` in
  `actor_participant_index`, not to the `VultronCaseActor` service entity ID.
  `CheckIsCaseManagerNode` compares `actor_id` against the CASE_MANAGER
  *participant* entry, not the service resource. Passing the service entity ID
  causes the role check to fail silently: the guarded commit never fires, RM
  falls through to DEFERRED, and the test may pass for the wrong reason. Any
  test that exercises BT operations in a received-side use case MUST pass a
  `receiving_actor_id`. See `specs/behavior-tree-integration.yaml` BT-17-005.
- **Routing Prerequisites Must Be Resolved Before State Mutation in Lifecycle BT
  Sequences** — A BT Sequence that performs a protocol state-machine transition
  (EM, RM, or CS) and then routes an outbound activity MUST resolve all routing
  prerequisites (e.g., Case Manager actor ID) in a read-only guard node placed
  BEFORE the state-mutation node. Committing a transition to the DataLayer before
  verifying routing is available creates a divergence window: local state reflects
  the new state (e.g., `EM=EXITED`) while peers still hold the prior state
  (e.g., `EM=ACTIVE`) because the broadcast was never sent. The Sequence MUST fail
  at the guard with zero DataLayer state change when routing prerequisites are
  absent. Duplicated monolithic nodes that inline both mutation and dispatch in a
  single `update()` MUST be replaced by a shared BT factory function used across
  all call sites (trigger path and automatic-cascade path) to prevent per-path
  drift back to the unsafe ordering. See `specs/behavior-tree-integration.yaml`
  BT-19-001, BT-19-002 and [notes/bt-integration.md](notes/bt-integration.md)
  § "Routing-Gated State Mutation".
- **Pre-commit Hooks Are Fail-Only — Run Skills Before Committing** — The
  `black` and `markdownlint-cli2` hooks use `--check` (no auto-fix). If a
  hook fails at commit time, run `format-code` to auto-fix, re-stage, then
  commit. Hooks that auto-modify files break `git rebase` by leaving a dirty
  working tree mid-cherry-pick.
- **Automation Potential and Call-Out Point Shape Are Orthogonal** — When
  classifying a fuzzer node, the `automation potential` and `call-out point
  shape` fields are **independent**. A node with High automation potential may
  still require a Retriever, Sentinel, Evaluator, or Composer seam — "can be
  automated" does not mean "no external seam exists." Assign shape using
  **only** the ADR-0024 seam-structure decision tree: Who/what provides the
  input? What does the node output? Does it monitor a condition, retrieve
  facts, evaluate a situation, or compose content? The answers determine the
  shape regardless of whether the implementation will be automated or
  human-driven. `ProtocolInternal` is reserved exclusively for terminal
  placeholders and structural composites that have **no** external input,
  output, or monitoring seam. See `specs/behavior-tree-integration.yaml`
  BT-18-005 and BT-18-006 and `docs/adr/0024-coordination-agent-taxonomy.md`.
  BT-18-006 resolves the Sentinel vs. Retriever ambiguity for synchronous
  binary external queries: a node the BT invokes on-demand that queries an
  external system and returns only SUCCESS/FAILURE is a Retriever, not a
  Sentinel.

- **BT Integration Tests Must Use Deterministic Factories When the Default Is
  Probabilistic** — When a tree builder's default `CallOutBackendFactory` wraps
  a `WeightedBehavior` or `AlmostAlwaysSucceed` fuzzer node, integration tests
  that assert `Status.SUCCESS` on the full tree become flaky. Pass an explicit
  deterministic factory (e.g., a module-level `_always_succeed_factory` helper)
  to every success-path integration test. Structure tests and `FAILURE`-path
  tests are unaffected. See `test/AGENTS.md` § "BT Factory Determinism" and
  [notes/bt-integration.md](notes/bt-integration.md)
  § "Integration Tests Must Use Deterministic Factories When BT Default Is
  Probabilistic".

- **`NoNew*` flags imply an upstream Sentinel seam.** When a BT condition
  node of the form `NoNew<X>Info` (or any node whose description says "check
  whether new information has arrived") reads a change-detection flag, that
  flag must have been written by someone. If the flag is written by the
  **protocol's own BT execution** (e.g., a prior BT tick or an Actuator in
  the same tree), the consuming node is `ProtocolInternal`. But if the flag
  is written by an **external event monitor** — an agent that watches an
  outside data source and fires into the blackboard when something changes —
  then there is an upstream **Sentinel** agent whose call-out point must be
  documented separately in the catalog. The consuming `NoNew*` node itself
  is `ProtocolInternal` (it reads a local flag), but failing to document the
  upstream Sentinel leaves the real external seam invisible. Always trace
  the flag back to its writer and record a Sentinel stub entry for it. See
  `notes/bt-fuzzer-nodes-report-management.md` for `NewValidationInfoSentinel`,
  `NewPrioritizationInfoSentinel`, and `NewDeploymentInfoSentinel` as worked
  examples. (Established in issue #1199.)
- **Silent `None` Returns and Fake `SUCCESS` Are the Same Bug** —
  Returning `None` from a helper when a required ID is absent, or
  returning `Status.SUCCESS` from a BT node when a required blackboard
  key is missing, both silently drop protocol behavior (ledger entries,
  broadcasts, routing decisions). The correct pattern: check at the
  conversion point and raise `VultronValidationError` (helpers) or
  return `Status.FAILURE` (BT nodes) immediately.
  See [notes/domain-validation.md](notes/domain-validation.md) and
  `specs/architecture.yaml` ARCH-15-001 through ARCH-15-004.
- **`outbox_list()` Requires `clone_for_actor` in Tests** — `SqliteDataLayer.outbox_list()` reads
  from `dl._actor_id`, which is `""` on a freshly constructed DataLayer.
  BT nodes write to the named actor's queue via `record_outbox_item(actor_id, ...)`.
  The two paths share a key only when the DataLayer was obtained via `clone_for_actor(actor_id)`.
  Use `dl.outbox_list_for_actor(local_actor_id)` or `dl.clone_for_actor(actor_id).outbox_list()` in tests.
  See [notes/datalayer-design.md](notes/datalayer-design.md) § "`outbox_list()` Requires `clone_for_actor` in Tests".
- **Happy-Path DL Seed Must Include `origin` Activities for `dl.read()` Calls** — Use cases that call
  `dl.read(activity_id)` to resolve a related entity (e.g., `recommender_id`) silently fall back to
  `""` / `None` when the activity is absent from the fixture. Assert `len(outbox) >= N` where N is
  the *expected* count, not just `>= 1` — a partial emission can pass a weak assertion while hiding
  a broken notification branch. See [notes/datalayer-design.md](notes/datalayer-design.md)
  § "Happy-Path DL Seeds Must Include Origin Activities for `dl.read()` Calls".
- **`UnroutableActivityError` Must Be Caught Inside `_handle`, Not Above It** — A gate/guard called
  before the `try/except` in `DispatcherBase._handle` escapes to `_process_inbox_item`, which re-queues
  the item — creating an infinite retry loop. Wrap gate calls in their own `try/except UnroutableActivityError`
  inside `_handle` and return (drop the event). General rule: when converting a silent `return None`
  into a `raise`, trace the full call stack to every re-queue/retry handler above the raise site.
  See [notes/inbox-pipeline.md](notes/inbox-pipeline.md) § "`UnroutableActivityError` Must Be Caught Inside `_handle`".
- **Blackboard List Write-Back: Only Needed for New Lists** — Mutating a list object retrieved from
  the blackboard is in-place; the write-back (`blackboard.set(key, value)`) is a no-op unless `key`
  was absent (KeyError branch) and you just created the list. Do not add write-backs to mutation
  paths that already hold a reference — they create noise without effect.
  See [notes/bt-integration.md](notes/bt-integration.md) § "Blackboard List Mutation: Write-Back Is Redundant".
- **Always Check `BTBridge.execute_with_setup` Return Value** — `execute_with_setup` never raises;
  it returns the `Status` enum. A FAILURE return left unchecked looks like SUCCESS. Always do:
  `if bridge.execute_with_setup(...) == Status.FAILURE: raise VultronBTError(...)`.
  See [notes/bt-integration.md](notes/bt-integration.md) § "Always Check `BTBridge.execute_with_setup` Return Value".
- **Ledger Commit Must Precede Outbox Write** — When a use case or BT node both commits a ledger
  entry and writes to the outbox, the commit MUST happen first. Writing to the outbox before
  the ledger commit produces a state where outbound activities have been sent but the causal record
  is absent from the ledger. See [notes/bt-integration.md](notes/bt-integration.md)
  § "Ledger Commit Must Precede Outbox Write".
- **`disposition="rejected"` for Local-Only Correlation Markers** — A ledger entry that records a
  *local* correlation or rejection event (not a canonical CaseActor-accepted assertion) MUST use
  `disposition="rejected"`. Using the default `"accepted"` disposition for non-canonical markers
  pollutes the authoritative ledger. See [notes/bt-integration.md](notes/bt-integration.md)
  § "Use `disposition="rejected"` for Local-Only Ledger Correlation Markers".
- **Semantic Registry Pattern Must Match Inbound Wire Format** — The semantic registry key for
  an activity type MUST match the inbound wire format (e.g., `SuggestActorToCasePattern`), NOT
  the outbound factory output (e.g., `OfferActorToCasePattern`). Registering the outbound pattern
  means the registry never fires for inbound messages of that type. See
  [notes/activitystreams-semantics.md](notes/activitystreams-semantics.md)
  § "Semantic Registry Patterns Must Match Inbound Wire Format".
- **`offer_case_participant_activity`: `event.object_id` Has `#participant` Suffix** —
  `event.object_id` is the CaseParticipant URI (with `#participant` suffix), not the actor URI.
  Extract `actor_id` from `event.attributed_to`, not `event.object_id`. See
  [notes/activitystreams-semantics.md](notes/activitystreams-semantics.md)
  § "`offer_case_participant_activity`: `event.object_id` Has `#participant` Suffix".
- **Pre-Build Dedup Sets Before Fallback Loops** — When skipping already-checked IDs inside a loop
  using membership in `dict.values()`, pre-build `seen = set(d.values())` once before the loop.
  Each `in d.values()` is O(n); the `set` makes it O(1) per check, reducing O(n×m) to O(n+m).
- **Consolidated Helper Needs One Test Per Distinct Lookup Path** — When unifying two helpers into
  one function with N distinct lookup paths (e.g., primary index + fallback scan), each path must
  have at least one test where it is the sole source of truth (all other paths left empty). Tests
  that always populate the fallback path leave the primary path untested. See
  [notes/bt-integration.md](notes/bt-integration.md) § "Dual-Path Consolidation Test Gap".
- **Domain Sweep Audit: Catalog → Code, Then Factory Injection, Then `register_key`** — For
  FUZZ-08h-style completeness audits: (1) AST-parse demo/fuzzer classes for a flat inventory,
  (2) cross-ref catalog `New-arch cross-ref:` lines for gaps, (3) grep `CallOutBackendFactory`
  in all tree builders, (4) grep `register_key` for naming conflicts. Closed issues referenced by
  `*(to be implemented — see FUZZ-08x)*` entries must be checked: if the issue is closed but
  the class is absent, it's a gap. See [notes/bt-fuzzer-nodes-report-management.md](notes/bt-fuzzer-nodes-report-management.md)
  § "Sentinel Stubs Must Be Synced When the Upstream Issue Closes".
- **MkDocs `not_in_nav` and `exclude_docs` Are Not the Same** — `exclude_docs` prevents files from
  appearing in the published build but does NOT satisfy the `validation.nav.omitted_files` guard.
  Files intentionally excluded from the nav MUST ALSO be listed in `not_in_nav`. Also: when using
  `INHERIT: mkdocs.yml`, the `not_in_nav` list in the overlay **replaces** (not extends) the base
  list. The strict local build script `mkdocs-build-strict.sh` is the right gate; CI's
  `docs-build-check.yml` runs non-strict and does not surface `omitted_files: warn` failures.
- **Pre-commit Hooks Interfere with `git rebase` in Worktrees** — `git rebase origin/main` in a
  worktree fails with "local changes would be overwritten" even on a clean tree when pre-commit
  hooks (black, flake8) modify files during the checkout step. Preferred workaround:
  `manage_worktree.sh ensure-synced`. Manual workaround when already on the wrong branch:
  (1) `git reset --soft origin/main` to move the branch parent while keeping staged changes,
  (2) `git -c core.hooksPath=/dev/null commit` to re-create the commit without running hooks,
  (3) `git branch -f <branch> HEAD` if needed to update the branch pointer.
  Alternative when rebasing is unavoidable: `git -c core.hooksPath=/dev/null rebase origin/main`,
  then run `pre-commit run --all-files` manually afterwards.
  Do NOT run `git rebase` raw in a worktree without confirming pre-commit hooks are check-only.

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
  `orient-agent`), the `ask_user` rule applies transitively — each
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
When `status: superseded`, `superseded_by` is a single non-empty string
(scalar), not a YAML list. If multiple successors exist, keep one canonical
`superseded_by` target and list siblings in `related_notes` or body text.
When modifying a notes file, review and update its frontmatter. Schema:
`vultron/metadata/notes/schema.py`; enforced by pre-commit hook and
`test/metadata/test_notes_frontmatter.py`.

### Docs links must be relative

Links in `docs/` MUST be relative to the current file and MUST NOT go above
the `docs/` root. Run `uv run mkdocs build --strict` before committing any
`docs/` changes (see `build-docs` skill).
The `.github/scripts/mkdocs-build-strict.sh` wrapper suppresses known griffe
false positives, but unknown-key warnings (for example `context` or `pytest`)
remain hard failures.

Maintainer docs under `docs/developer/` are intentionally excluded from the
published site (`mkdocs.yml`). To view or validate them locally, use
`mkdocs.dev.yml` (for example: `uv run mkdocs serve --config-file
mkdocs.dev.yml`).

### Demo script lifecycle logging

See [`vultron/adapters/AGENTS.md`](vultron/adapters/AGENTS.md) for the
`demo_step` / `demo_check` pattern.

### Writing project history entries

History entries live under `plan/history/YYMM/<type>/<entry-id>.md`. Use the
`append-history` CLI tool — **never** append directly to files in
`plan/history/`. See `specs/history-management.yaml` (HM-01–HM-05) and
`notes/history-management.md` for the format and usage. During `orient-agent`,
read only `plan/*.md` — access `plan/history/` only for investigating
completed work.

---

## Agent skills

### Issue tracker

Issues live in GitHub Issues; external PRs are not a triage surface. See `docs/agents/issue-tracker.md`.

**Never use `gh issue create`** — it cannot set issue types, parent/child
relationships, or blocker/blocked-by links. Always use the
`manage-github-issue` helper script (`.agents/skills/manage-github-issue/manage_github_issue.sh`)
or the `createIssue` GraphQL mutation directly (with `issueTypeId`,
`parentIssueId` inline). Issue type IDs and relationship mutation names are in
`.agents/skills/manage-github-issue/REFERENCE.md`.

**Never pass backtick-containing markdown in a double-quoted `--body` string.**
Backticks inside `"..."` are shell-interpreted and appear as `\`` in GitHub.
Always use a single-quoted heredoc so the shell passes the body verbatim:

```bash
gh issue comment <N> --repo CERTCC/Vultron --body "$(cat <<'EOF'
Use `code` freely here — no escaping needed.
EOF
)"

gh pr create --body "$(cat <<'EOF'
- Closes #N
## Summary
Run `/plan-issue` to fix `needs-decomposition` Epics.
EOF
)"
```

The same rule applies to `gh issue edit --body`, `gh issue comment`, and any
other CLI command that accepts a markdown body argument.

### Triage labels

Default label vocabulary (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context repo: one `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.
