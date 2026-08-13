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

- **Load specs first**: `PYTHONPATH= uv run spec-dump` — never read raw
  `specs/*.yaml`. The `PYTHONPATH=` prefix is required; see pitfall below.
- Pipeline: FastAPI inbox → AS2 parser → semantic extraction
  (`vultron/wire/as2/extractor.py`) → dispatcher → use-case callable
  (`vultron/core/use_cases/`).
- Use-Case Protocol: `__init__(dl, request)` + `execute() -> None`; routing via
  `USE_CASE_MAP` key lookup.
- ASGI entrypoint: `vultron.adapters.driving.fastapi.main:app`.
- Tests: `uv run pytest --tb=short 2>&1 | tail -5` — run once. See
  `.agents/skills/run-tests/SKILL.md`.

Quick gotchas: specific patterns before general; always `rehydrate()` before
pattern matching; persist with `dl.save(obj)`; return 202 immediately
(`BackgroundTasks`); architecture changes → ADR first.

## Scope of Allowed Work

Agents MAY: implement small–medium features, refactor without behavior change,
add/update tests, improve typing/validation/error handling, update docs/specs,
propose architectural changes (not apply without approval).

Agents MUST NOT: introduce breaking API changes, modify auth/crypto logic,
change persistence schemas without explicit instruction, touch CI/deployment/secrets.

Small tweaks don't require an ADR; architectural/protocol changes SHOULD have one
before merging. See `docs/adr/_adr-template.md`.

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
- Use Protocol for interface definitions; avoid global mutable state
- **Fail-fast domain objects**: required fields MUST validate at construction;
  subtype-required fields MUST NOT be `X | None` in that subtype. See ARCH-10-001.
- **Validate at the edge, promote to the core (ADR-0032)**: wire/adapter objects
  may have `Optional` fields; validate before passing to core so core receives
  non-optional types — no `if x is None` guards needed inside core.
- **Collection defaults**: collection fields default to empty (`[]`, `{}`, `set()`),
  not `None`, unless absence is semantically distinct from empty.
- **Core helpers raise, never return `None`**: helpers raise on failure; `update()`
  is the sole `try/except` in BT nodes. See `notes/bt-pitfalls.md` § BT-HELPER-01.
- **Optional string fields MUST follow "if present, then non-empty"**: use shared
  `NonEmptyString`/`OptionalNonEmptyString` from `vultron/wire/as2/vocab/base/`
  (CS-08-002). Do NOT add per-field `@field_validator` stubs for empty-string
  rejection; extend the shared type alias. See CS-08-001, CS-08-002.

### Decorator Usage

See [`vultron/core/AGENTS.md`](vultron/core/AGENTS.md) — use-case protocol
and dispatcher routing.

### Code Organization

- Prefer small, composable functions
- Raise domain-specific exceptions; do not swallow errors
- Keep formatting and linting aligned with tooling; do not reformat
  unnecessarily
- **Prefer extracting shared logic over duplicating it.** Three similar lines
  of code is a signal to extract; copy-pasting a function body is not
  acceptable. DRY is a project standard (CS-22-001). For demo scenarios the
  rule is stricter (MUST) — see `vultron/demo/AGENTS.md` §
  "Extract Before Reuse" and `specs/multi-actor-demo.yaml` DEMOMA-17-001.

### Markdown Formatting

- **Line length**: 88 chars max (exceptions: tables, code blocks, long URLs)
- Use `markdownlint-cli2` for linting; see Miscellaneous tips for commands
- Break long sentences at natural points

### Logging Requirements

DEBUG (details), INFO (lifecycle/state transitions), WARNING (recoverable),
ERROR (failures), CRITICAL (system). Include `activity_id` and `actor_id`
when available. See `specs/structured-logging.yaml`.

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
- **Case States**: `vultron/core/states/cs.py` — CS/VFD/PXA enums are
  authoritative; `vultron/core/states/cs_invariants.py` holds the CS validity,
  transition and history invariants (CSB-17). `vultron/core/case_states/` is the
  legacy string-pattern reference model, retained as an independent oracle and
  still imported by `states/cs.py` and `use_cases/query/action_rules.py`. Reach
  for `cs_invariants.py` for new protocol-path work; the legacy module's only
  remaining new-code use is as the oracle in the CSB-17 equivalence tests
  (ADR-0060)

Full core-layer map → [`vultron/core/AGENTS.md`](vultron/core/AGENTS.md).
Full wire-layer map → [`vultron/wire/as2/AGENTS.md`](vultron/wire/as2/AGENTS.md).
Full adapter-layer map → [`vultron/adapters/AGENTS.md`](vultron/adapters/AGENTS.md).

### Constructing Outbound Activities

All outbound activities MUST use factory functions in
`vultron.wire.as2.factories`. See
[`vultron/wire/as2/AGENTS.md`](vultron/wire/as2/AGENTS.md) for details.

### GitHub Issue Labels

Priority tracking via **GitHub Project #24** `Schedule` field: `Now`, `Next`,
`Later`, `Someday`. New issues default to `Someday`. Do not use `group:` labels.
See `notes/parallel-development.md`.

## Change Protocol

For non-trivial changes: state assumptions → load specs (`PYTHONPATH= uv run spec-dump`) →
review `notes/` → describe intent → apply minimal diff → update/add tests →
call out risks.

For architectural changes, draft an ADR first. Use the decision-tree in
`notes/specs-vs-adrs.md` (MS-11-001 through MS-11-006) to decide ADR vs. spec
entry vs. both.

### Commit Workflow

**Before committing**, run skills in order:

1. `format-code` — Black + flake8
2. `run-linters` — all four linters must pass
3. `run-tests` — unit suite once; read output. If `vultron/demo/` or `test/demo/`
   touched, also run full suite: `uv run pytest -m "" --tb=short 2>&1 | tail -5`
4. `build-docs` — only if `docs/` modified
5. `commit` skill — include Co-authored-by trailer

**PR body**: use `.agents/skills/shared/pr-body-guide.md` template. Put
`- Closes #N` at top, one per line.

**`append-history`**: stage the new entry file (`git add plan/history/`).
The monthly `README.md` under `plan/history/YYMM/` is gitignored — do not stage it.

Pre-commit hooks are fail-only. If a hook fails, run `format-code` (black/markdown)
or `run-linters` (flake8), re-stage, then commit.

**After a PR merges** in a named worktree slot:
`bash "$HOME/.copilot/skills/manage-worktree/scripts/manage_worktree.sh" reset <slot-name>`

---

## Parallel Development (Worktree Slots)

Multiple agents use named git worktree **slots**. See
[`notes/parallel-development.md`](notes/parallel-development.md) and
`~/.copilot/skills/manage-worktree/SKILL.md`.

---

> **Specification Usage Guidance** has moved to `specs/AGENTS.md`.
>
## Safety & Guardrails

- Treat anything under `/security`, `/auth`, or equivalent paths as sensitive
- Do not generate secrets, credentials, or real tokens
- Flag ambiguous requirements instead of guessing
- **NEVER run `git worktree prune` (or `git gc`)** — `.git` is shared across
  host and dev-container mounts. `prune` silently destroys live worktrees whose
  paths aren't resolvable from the current environment. If `git worktree list`
  shows `prunable` entries, leave them and verify with a human first.
  See [`notes/parallel-development.md`](notes/parallel-development.md).

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

Full doctrine: `.claude/skills/shared/completeness-doctrine.md` (loaded by
`orient-agent`). Summary:

- Done = all changed behaviors tested, edge cases handled, types/docs current,
  linters clean.
- **FAIL** → fix before PR. **IMPROVE** → fix this session.
  **DEFER** → create follow-up issue + user ack. No WARN-and-defer.

---

## Common Pitfalls (Lessons Learned)

See [notes/agents-md-structure.md](notes/agents-md-structure.md) for routing policy on new pitfalls.

- **Production Adapters MUST NOT Import from `vultron/demo/` for Config** —
  actor policy config belongs in `AppConfig.actor` (CFG-07-005 through CFG-07-007).
  See [notes/configuration.md](notes/configuration.md).
- **Idempotency Responsibility Chain** — see [`vultron/core/AGENTS.md`](vultron/core/AGENTS.md)
- **Bulk Logging-Level Refactors Need a Consistency Grep Pass** — grep-check
  all matching functions before commit.
- **Case-Actor Broadcast Guard Tests Need a Third Participant** — include at
  least one non-sender peer or the assertion is vacuous.
- **Case Participant Lookup**: `actor_participant_index` is the authoritative fast
  path. Two lookup patterns exist — pick by context:
  - **RM state mutation** (`update_participant_rm_state`): MUST use
    `actor_participant_index → dl.read()` exclusively (CM-19-003). Never read
    inline objects from `case_participants`; they may be stale snapshots (#2233).
  - **BT-level resolution** (`FindParticipantByActorIdNode`): check
    `actor_participant_index` first; fall back to `case_participants` scan for
    bootstrap compatibility. Fail only on index↔scan contradictions, not cache
    misses.
- **Orphan Module Cleanup Requires Importer Proof** — verify no live importers
  in `vultron/` and `test/` before deleting.
- **Worktree Sync Checks Need Ancestry Verification** — use `ensure-synced`
  flow, not raw `git rebase origin/main`.
- **`as_VulnerabilityCase` (wire) vs `VulnerabilityCase` (core)** — all classes
  in `vultron/wire/as2/vocab/objects/` use `as_` prefix. Bare name = core type.
  See ARCH-14-001.
- **Never Reach for `alias_generator` or `by_alias=True` in Core to Get camelCase**
  — core needs wire-shaped JSON only for `CaseLedgerEntry.payloadSnapshot`, and it
  MUST get it from the `WireRenderPort` driven port, not from the domain model.
  A core-side alias cannot express structural core/wire differences (nested
  `consent: PecDimension` vs flat `emConsentState`), so it always accretes
  per-field hand-patches that drift from `from_core()`. See ARCH-20-001,
  CLP-07-009, CLP-07-010 and
  [notes/core-wire-rendering-port.md](notes/core-wire-rendering-port.md).
- **Deleting a Wire-Spelling Shim Without a Reject-Guard Is a Silent Data-Loss
  Bug** — Pydantic v2 defaults to `extra="ignore"`, so removing a validator that
  accepted a legacy key makes that key *silently dropped* and the field default
  to its start value (a lost RM ladder, not an error). Always pair the deletion
  with a `model_validator(mode="before")` built on `reject_wire_spelled_keys`
  (`vultron/core/models/_wire_spelling.py`). See SDO-03-005, ARCH-15-002.
- **Flat `nodes.py` in BT Areas Is Non-Compliant** — use `nodes/` subpackage;
  `__init__.py` MUST re-export all public names. See BTND-07-001, BTND-07-003.
- **Splits Must Not Produce New God Modules** — submodules ≤500 lines; split
  recursively when they re-accumulate. See CS-18-001 through CS-18-004.
- **BT Emit Nodes: Inherit Base Classes, Never Reimplement Guard Boilerplate**
  — use `_EmitCaseActorReportActivityBase` (report domain) or
  `_SendEmbargoActivityBase` (embargo domain); override only `_call_factory()`
  and the three hook methods. See BTND-07-005.
- **Peer Broadcast Nodes Must Not Mask Delivery Failure with SUCCESS** —
  see [notes/peer-broadcast-failure-semantics.md](notes/peer-broadcast-failure-semantics.md) BT-14-001.
- **Negative-Guard Condition Nodes Are a Readability Anti-Pattern** — use
  positive-precondition Sequences. See BTND-08-001, BTND-08-002 and
  [notes/bt-design-patterns.md](notes/bt-design-patterns.md).
- **`case_addressees()` Is the Wrong Recipient for Participant Outbound
  Messages** — use Case Actor only (PCR-08-001, PCR-08-002).
  See [notes/case-communication-model.md](notes/case-communication-model.md).
- **Received-Side Use Cases MUST NOT Spoof Another Actor's Identity** —
  see [notes/case-communication-model.md](notes/case-communication-model.md)
  § "Antipattern: Identity Spoofing in Received-Side Use Cases".
- **Received-Side Guarded Commit MUST NOT Resolve a Foreign CaseActor ID** —
  see [notes/case-communication-model.md](notes/case-communication-model.md)
  § "Antipattern: Received-Side Guarded Commit with Foreign CaseActor ID".
- **Invite/Accept Handshake Must Route Through the Case Actor** — PCR-08-007,
  PCR-08-008. See [notes/case-communication-model.md](notes/case-communication-model.md).
- **Inline `EMAdapter` Instantiation Is an Anti-Pattern** — delegate to
  `EmbargoLifecycle` (#538); cascade PEC alongside EM transitions.
  See [notes/embargo-lifecycle.md](notes/embargo-lifecycle.md).
- **Trigger-Side execute() Must Delegate SM Transitions to BTBridge** — all RM/EM
  transitions are protocol-significant (BT-15-001) and MUST live in BT leaf nodes.
  See [notes/bt-integration.md](notes/bt-integration.md) § "Trigger/Received Parity".
- **Direct DataLayer Mutations in execute() Are Not Caught by the Import-Based
  Ratchet** — `dl.save/create/update/delete()` in `execute()` bypass the BT audit
  trail. See ratchet in `test/architecture/test_no_dl_mutations_in_execute.py` (#1071).
- **Receive-Side BTs Must Record the Triggering Activity Before Applying Protocol
  Effects** — ordering: (1) guards, (2) commit, (3) effects. See CLP-10-006.
- **Received-Side execute() Must Not Call commit_log_entry_trigger() Directly** —
  BT-06-006; use `CommitCaseLedgerEntryNode` via `BTBridge`. See SYNC-02-002.
- **BTBridge Global Blackboard Is Not Thread-Safe Under FastAPI BackgroundTasks** —
  use module-level `threading.RLock` (not `Lock`).
  See [notes/bt-integration.md](notes/bt-integration.md) § "Concurrency Model".
- **ResolveCaseManagerNode Requires CASE_MANAGER Participant in Test Fixtures** —
  set `case_participants` and `actor_participant_index` directly in constructor;
  pass `TriggerActivityAdapter(dl)` to every use case in chained integration tests.
- **Routing Prerequisites Must Be Resolved Before State Mutation** — resolve Case
  Manager ID in a read-only guard node BEFORE state-mutation node. See BT-19-001,
  BT-19-002. [notes/bt-pitfalls.md](notes/bt-pitfalls.md) § "Routing-Gated
  State Mutation".
- **Superseded `notes/*.md` Files Must Move to `archived_notes/`** — use `git mv`;
  update both READMEs. See PD-03-004, PD-03-005.
- **Stub Adapter Files Must Raise `NotImplementedError`** — docstring-only stubs
  hide integration gaps. See OX-10-004, OX-11-004.
- **Trigger Use Cases Need Per-Use-Case Tests** — incidental coverage via
  `test_trignotify.py` is insufficient. See
  [notes/triggers-test-coverage.md](notes/triggers-test-coverage.md).
- **Hash-Chain Ledger Record vs. Domain Model** — `HashChainLedgerRecord` (in-memory
  SYNC-1) vs. `CaseLedgerEntry` (wire-serializable). Import by full module path.
  See ARCH-12-007.
- **Case Ledger Is Not a Process Log** — only CaseActor-accepted protocol-significant
  assertions; `payloadSnapshot` MUST NOT be empty. See ADR-0019, CLP-07,
  [notes/case-ledger-authority.md](notes/case-ledger-authority.md).
- **Canonical Ledger Commits Must Be Role-Gated** — `CommitCaseLedgerEntryNode`
  MUST be wrapped in a role-gated composite. See CLP-09,
  [notes/case-ledger-authority.md](notes/case-ledger-authority.md).
- **Use-Case Subpackage Splits Must Re-Export Both Classes and Request Models** —
  `__init__.py` must re-export both; mirror split in test layout.
- **Transport-Role Naming Must Stay Explicit** — update core ports docs, adapter
  notes, ADR refs, and codebase reference pages together.
- **mypy Infers Type From First Branch Assignment** — use distinct variable names
  per `except`/`if`-else branch.
- **Counter-Revision EM Path Must Be Tested Separately** — `EM.REVISE → EM.REVISE`
  must be separate test; `_cascade_pec_revise` only fires on `ACTIVE → REVISE`.
- **RM Terminal Guard Must Run Before Same-State Shortcut** — evaluate
  `RM.CLOSED` terminal rules before `current == new` no-op check.
- **Do Not Downgrade Existing Consent on Idempotent Retries** — preserve non-null
  consent on embargo accept/reject retry paths.
- **PEC Consent Must Go Through `apply_pec_transition()`, Never Direct Field
  Assignment** — `participant.embargo_consent_state = PEC.SIGNATORY` bypasses both
  the PEC machine and `_sync_latest_status_metadata()`, leaving the latest
  `ParticipantStatus` stale so the ledger snapshot emits the contradictory pair
  `{"embargoAdherence": true, "emConsentState": "NO_EMBARGO"}`. Use
  `participant.apply_pec_transition(trigger)` as the single authoritative
  consent-write path — it is fail-closed and raises
  `VultronInvalidStateTransitionError` on an illegal trigger. Guard idempotent
  sites with `if participant.embargo_consent_state != PEC.<TARGET>:` before
  calling. See CM-18-005, CM-18-006, ADR-0048,
  [notes/participant-embargo-consent.md](notes/participant-embargo-consent.md).
- **DataLayer Scope Tests: Use `call_args.args`, Not `call_args[0]`** — named
  attribute raises `AttributeError` clearly; index returns empty tuple silently.
- **Inbox Policy Logic Must Live in the Core BT Module** — all inbox processing
  policy belongs in `vultron/core/behaviors/inbox/`. See IO-02-003, IO-03-003,
  [notes/inbox-orchestration.md](notes/inbox-orchestration.md).
- **`ProposeCaseToActorNode` Sends `Create(CaseProposal)`; `CreateCaseActorNode`
  Does Not** — wire after actor creation. See CP-04-002,
  [notes/case-proposal.md](notes/case-proposal.md).
- **Protocol-Declared Fields Must Stay in Sync with Concrete Classes** — remove
  Protocol members when removed from concrete class. See CS-20-001.
- **`TypeGuard` Discriminators Must Use Protocol-Declared Fields Only** —
  `hasattr` only on Protocol-declared attributes. See CS-20-002.
- **`getattr(obj, name, default)` Does Not Catch `ValueError` from Property
  Getters** — use `try/except (AttributeError, ValueError)`.
  See [notes/domain-validation.md](notes/domain-validation.md).
- **Core→Wire Conversion: Use `wire_cls.from_core()`** — never
  `model_dump()` + `model_validate()`. See
  [notes/activity-factories.md](notes/activity-factories.md).
- **`dl.read()` Returns Core Objects** — MUST NOT return `as_`-prefixed wire
  types for `CORE_VOCABULARY`-registered types. See ADR-0034, DL-05-001–DL-05-004,
  [notes/datalayer-design.md](notes/datalayer-design.md).
- **Core MUST NOT Re-Read a Wire Activity for Semantic Content** — capture domain
  fact as core state at extraction time. See ADR-0035, DL-06-001–DL-06-005,
  [notes/datalayer-design.md](notes/datalayer-design.md).
- **Always Use `uv run <tool>` in Devcontainer** — bare entrypoints use baked
  image, not mounted working tree. See #1460.
- **`PYTHONPATH=/app` Contaminates Imports** — the devcontainer sets
  `PYTHONPATH=/app`, which causes `uv run spec-dump` (and any other entry
  point) to resolve `vultron` imports from the stale baked image at `/app`
  instead of the editable install. Always prefix with `PYTHONPATH=` to clear
  it: `PYTHONPATH= uv run spec-dump`. Same applies to any `uv run <entrypoint>`
  that touches `vultron.*` modules.
- **Walrus Operator for Single-Assignment Guard Blocks** —
  `if (f := self._require_factory()) is not None: return f`.
- **Silent `None` Returns and Fake `SUCCESS` Are the Same Bug** — raise
  `VultronValidationError` (helpers) or return `Status.FAILURE` (BT nodes).
  See [notes/domain-validation.md](notes/domain-validation.md) ARCH-15-001–15-004.
- **`outbox_list()` Requires `clone_for_actor` in Tests** —
  see [notes/datalayer-design.md](notes/datalayer-design.md).
- **Happy-Path DL Seed Must Include `origin` Activities for `dl.read()` Calls** —
  assert `len(outbox) >= N` (expected count, not just ≥1).
  See [notes/datalayer-design.md](notes/datalayer-design.md).
- **`UnroutableActivityError` Must Be Caught Inside `_handle`, Not Above It** —
  see [notes/inbox-pipeline.md](notes/inbox-pipeline.md).
- **Blackboard List Write-Back: Only Needed for New Lists** —
  see [notes/bt-pitfalls.md](notes/bt-pitfalls.md).
- **Always Check `BTBridge.execute_with_setup` Return Value** —
  `if bridge.execute_with_setup(...) == Status.FAILURE: raise VultronBTError(...)`.
  See [notes/bt-pitfalls.md](notes/bt-pitfalls.md).
- **Ledger Commit Must Precede Outbox Write** —
  see [notes/bt-pitfalls.md](notes/bt-pitfalls.md).
- **`disposition="rejected"` for Local-Only Correlation Markers** —
  see [notes/bt-pitfalls.md](notes/bt-pitfalls.md).
- **Semantic Registry Pattern Must Match Inbound Wire Format** —
  see [notes/activitystreams-state-update.md](notes/activitystreams-state-update.md).
- **`OFFER_CASE_MANAGER_ROLE` and `OFFER_CASE_OWNERSHIP_TRANSFER` Share
  `Offer(VulnerabilityCase)` — Registry Order and Required `target` Field Are
  the Current Guards** — `OFFER_CASE_MANAGER_ROLE` MUST appear before
  `OFFER_CASE_OWNERSHIP_TRANSFER` in `SEMANTIC_REGISTRY` (enforced by
  `_validate_registry_order()`). `_OfferCaseManagerRoleActivity.target` MUST
  remain required. Do NOT add a third `Offer(VulnerabilityCase)` pattern without
  a distinct object type. See SE-08-001, SE-08-002, ADR-0039,
  [notes/activitystreams-state-update.md](notes/activitystreams-state-update.md)
  § "Target-Field Discriminators".
- **`offer_case_participant_activity`: `event.object_id` Has `#participant` Suffix**
  — extract `actor_id` from `event.attributed_to`.
  See [notes/activitystreams-state-update.md](notes/activitystreams-state-update.md).
- **Pre-Build Dedup Sets Before Fallback Loops** — `seen = set(d.values())`
  before the loop; O(n×m) → O(n+m).
- **Consolidated Helper Needs One Test Per Distinct Lookup Path** —
  see [notes/bt-pitfalls.md](notes/bt-pitfalls.md) § "Dual-Path
  Consolidation Test Gap".
- **Domain Sweep Audit: Catalog → Code, Then Factory Injection, Then
  `register_key`** — see
  [notes/bt-fuzzer-nodes-report-management.md](notes/bt-fuzzer-nodes-report-management.md).
- **MkDocs `not_in_nav` and `exclude_docs` Are Not the Same** — files excluded
  from nav MUST ALSO be in `not_in_nav`; overlay list replaces base list.
- **Pre-commit Hooks Interfere with `git rebase` in Worktrees** — use
  `manage_worktree.sh ensure-synced`. Manual fix: `git reset --soft origin/main`
  then `git -c core.hooksPath=/dev/null commit`. See `test/AGENTS.md`.
- **Automation Potential and Call-Out Point Shape Are Orthogonal** — assign shape
  using ADR-0024 seam-structure decision tree only. See BT-18-005, BT-18-006.
- **`NoNew*` flags imply an upstream Sentinel seam** — trace flag to its writer
  and record a Sentinel stub. See
  [notes/bt-fuzzer-nodes-report-management.md](notes/bt-fuzzer-nodes-report-management.md).
- **BT Integration Tests Must Use Deterministic Factories When the Default Is
  Probabilistic** — see `test/AGENTS.md` § "BT Factory Determinism" and
  [notes/bt-pitfalls.md](notes/bt-pitfalls.md).
- **Emit Nodes in Case-Scoped Trigger BTs Must Fail Fast on Missing CaseActor** —
  FAILURE/exception when no routable CaseActor. See PCR-08-011.
- **Module Split: Re-Import Moved Names for `monkeypatch` Compatibility** —
  re-import into original module namespace with `# noqa: F401`. Issue #972.
- **FastAPI `dependency_overrides` Key Must Be Re-Exported When Converting a
  Router Module to a Package** — scan tests for `module.dependency_function`
  patterns. Issue #970.
- **Guarded-Commit Tests Must Use the CASE_MANAGER Actor as `receiving_actor_id`**
  — `CheckIsCaseManagerNode` checks the participant entry, not the service ID.
  See BT-17-005.
- **Staged-Type `model_validate` Only Works on Core-Constructed Objects** — don't
  use on `dl.read()` results; check pre-conditions directly on returned object.
- **`freshen-branch.sh` Leaves Temp Branch on Conflict When Abort Silently Fails** —
  If `git cherry-pick --abort` fails (partially-written cherry-pick state),
  the `|| true` swallows the error but the following `git checkout "$TASK_BRANCH"`
  fails with "you need to resolve your current index first" and the script exits,
  leaving the repo on a `temp-freshen-*` branch with conflict markers.
  Recovery: `git branch --show-current` (confirm `temp-freshen-*`), resolve
  conflict markers, `git add <file>`, `git cherry-pick --continue --no-edit`,
  then `git branch -f "$TASK_BRANCH" HEAD && git checkout "$TASK_BRANCH"`.
  Use `manage_worktree.sh ensure-synced` in preference to the raw script.
- **A Red CI Job Is Not Evidence That Its Assertions Ran** — a job that dies in
  an earlier step (artifact download, dependency setup, container build) never
  reaches pytest, so its red status says nothing about what the tests assert.
  Open the log and identify the failing *step* before concluding a test is
  wrong, unsatisfiable, or "can never pass". A permanently-red
  `<scenario> Invariant Harness` job was misread this way in CONCERN-2243: it
  failed at `actions/download-artifact` on every run, so the assertion blamed
  for the failure had never once executed. Note the inverse trap too — an
  all-skipped pytest run exits 0 and reports **green** while checking nothing.
  See [notes/demo-ci-invariants.md](notes/demo-ci-invariants.md) § "Reading a
  Red Invariant Harness Job".
- **Trace Shared Helper Layers Before Declaring an Event Unemitted** — in the
  demo suite, protocol activity is emitted from shared helpers in
  `vultron/demo/helpers/workflow.py` (e.g. `receiver_engages_case()`,
  `run_direct_path_rm_triage()`), not from the scenario files. Grepping a
  scenario file — or even all of `vultron/demo/scenario/` — finds nothing and
  invites the false conclusion that no code emits the event. Search the helper
  and semantic-registry layers, and confirm against
  `graphify explain "<function>"` call edges, before asserting absence.
  CONCERN-2243 filed a Concern on this basis for an event emitted by all nine
  scenarios. *Source: CONCERN-2243*
- **`git rebase` "local changes would be overwritten" With a Clean Working Tree**
  — this error can be a false positive when the rebased branch diverges far from
  main and both sides touched the same files. Fix: cherry-pick onto a fresh branch
  from `origin/main` (`git checkout -b temp origin/main && git cherry-pick <hash>`)
  instead of rebasing. The error message is misleading — it is NOT evidence of
  uncommitted work. See also: single large-commit branches with 70+ files trigger a
  sequencer duplicate-pick bug; the cherry-pick workaround resolves both variants.
  If `freshen-branch.sh` took this path and then hit a conflict, it can leave the
  temp branch behind — delete it by hand (ISSUE-1784).
  *Sources: ISSUE-1518, ISSUE-1504, ISSUE-1784*
- **Verify Issue ACs Against Current Code Before Starting** — an issue may already
  be fully implemented by a prior PR that did not include a `Closes #N` footer.
  Check current `main` against all ACs before writing any code; if satisfied, close
  the issue with a reference comment instead. *Sources: ISSUE-1510, ISSUE-1484*
- **Docs/Learn PRs That Fix a Bug Must Include `Closes #N`** — when a docs PR
  fixes a bug as a side effect, the closing footer is the only thing that
  closes the issue automatically. Without it the issue stays OPEN after merge.
  *Source: ISSUE-1787*
- **Guard Name Must Reflect the State-Machine Transition Precondition, Not Just
  Symptom Absence** — look up the transition in `vultron/core/states/` before
  naming and implementing a guard node; "not yet X" names under-constrain the
  guard and allow invalid state jumps. See
  [notes/bt-pitfalls.md](notes/bt-pitfalls.md) § "Guard Name Must Match…".
  *Source: ISSUE-1825*
- **Leaf Modules Near the 500-Line Cap Block Documentation Edits** — check
  `wc -l` before adding docstrings or audit comments to a leaf module. If it is
  within ~20 lines of 500, extract a semantic concern into a sibling submodule
  (BTND-07-006) *first*, then write the documentation. See BTND-07-004,
  BTND-07-006. *Source: ISSUE-1777*
- **`CheckIsCaseOwnerNode` Lives in `vfd_role_guards.py`, Not `conditions.py`** —
  placed there because `conditions.py` was at the 500-line cap when the node was
  added (ISSUE-1841). `__init__.py` re-exports it alongside the other role guards.
  If `conditions.py` grows further, consider extracting proposal-related nodes
  into `proposal_conditions.py`. *Source: ISSUE-1841*
- **ADR "What Is Removed" Lists Are Scoped to One Use, Not Global Existence** —
  grep the spec corpus for MUSTs describing the *operation* the node implements
  before deleting it. An ADR may list a component as removed from one specific
  initialization flow while spec entries still require it in another. *Source:
  ISSUE-1777; see also [notes/bt-pitfalls.md](notes/bt-pitfalls.md)*
- **Large Migration Tasks: Partition by Node Shape (Type), Then Domain for Size**
  — for tasks that migrate many nodes (e.g., Ports adoption), classify nodes by
  their structural shape first (trivial reparent / read-only extra inputs /
  complex output ports), then split by domain only to balance PR size. "Each PR
  should be a lot of the same thing." See ISSUE-1809 for the typed-Ports chain
  decomposition as the reference example.
- **When a `Closes #N` Footer Is Missing from a Merged PR, the Issue Stays Open**
  — check open issues before starting a session; an issue may be fully implemented
  but not closed. Use `git log -S "<fix string>" -- <file>` against `origin/main`
  to confirm. *Source: ISSUE-1787*
- **`Reject(Invite(actor, case))` Carries the Case in `inner_target`, Not Top-Level `target`**
  — `extract_event` does NOT populate `request.target` for the Reject; the case
  reference is on the nested Invite's `target` field, exposed as `request.inner_target_id`.
  Always read `request.inner_target_id or request.target_id` (or use a typed `case_id`
  property on the event class) when resolving `case_id` for
  `RejectInviteActorToCaseReceivedUseCase`. The same nesting applies to
  `Accept(Invite(actor, case))` — `AcceptInviteActorToCaseReceivedEvent.case_id` already
  follows this pattern. See CM-11-003. *Source: ISSUE-1747*
- **Retiring a File or Label Requires Auditing All Specs for Bare-Filename References** —
  `MS-15` (`_check_phantom_paths`) only flags backtick-quoted tokens containing a directory
  separator (e.g. `` `plan/PRIORITIES.md` ``). Bare filenames such as `PRIORITIES.md` or
  bare label names such as `group:unscheduled` written without backticks or without a `/`
  pass the lint check silently. When retiring any file, label, or convention, grep
  `specs/` for the bare name as well as the quoted/path form, and update every spec entry
  that references it — including `statement:`, `rationale:`, and cross-reference fields.
  *Source: ISSUE-2011*
- **`embargo_adherence` Is a `@computed_field`, Not a Settable Field** —
  `ParticipantStatus.embargo_adherence` is derived from `consent.state`
  (`True` iff `PEC.SIGNATORY`). Do NOT set it directly or declare it as a
  stored field. To change the value, apply a PEC trigger via
  `CaseParticipant.apply_pec_transition()`. See CM-18-008, ADR-0056.
  *Source: CONCERN-2091*
- **Delegated-Emit Trigger Use Cases MUST Set `actor=case_actor_id`,
  `attributed_to=requesting_actor_id`** — trigger use cases that emit an
  Activity on behalf of the CaseActor (invite, ownership transfer, and any
  future delegated flows) MUST set `self._actor_id = case_actor_id` and
  `self._attributed_to = requesting_actor_id` in `_prepare()`, then queue
  the Activity in the CaseActor's outbox (CM-24-001 through CM-24-004).
  Setting `actor` to the requesting actor directly causes receivers to reject
  the message (ISSUE-2142).  Use the shared `_prepare_delegated_context()`
  helper (or equivalent) — never reconstruct the pattern inline (CM-24-005).
  See [notes/case-communication-model.md](notes/case-communication-model.md)
  § "Delegated-Message Pattern". *Source: CONCERN-2170*
- **Multiple Related Fix PRs Targeting a Shared CI Suite Must Use an Integration
  Branch, Not Race to `main`** — when 3+ related bug fix PRs are open
  simultaneously and all affect the same CI suite (e.g. Demo Integration), open
  a single `fix/<area>` integration branch off `main` and target all child PRs
  there. Run the full CI suite against the integration branch after each child PR
  merges into it. Merge the integration branch to `main` only when the full suite
  is green. Racing parallel PRs to `main` means each PR can only confirm its own
  scenario passes — none can confirm it hasn't perturbed other currently-passing
  scenarios. *Source: CONCERN-2137*
- **New Push-to-`main` or Scheduled Workflows MUST Wire the `notify-failure`
  Composite Action** — any workflow that triggers on `push: branches: [main]` or
  on `schedule:` MUST include `.github/actions/notify-failure` as a final step
  (CISEC-05-001). Without it, failures on `main` or unattended scheduled runs go
  undetected until someone manually audits the Actions tab. Two separate steps are
  required: one on failure (file/update a `ci:main-failure` issue, CISEC-05-001)
  and one on success (close the issue for recovery visibility, CISEC-05-002).
  *Source: CONCERN-2132*
- **Demo Steps Must Be Gated on Their Cause, Not Their Position in the Script** —
  a scenario step that depends on an asynchronous effect MUST gate on the
  committed state of the actor that *produces* that effect, read from that actor's
  own container. An HTTP 202 return, elapsed time, and step order are not
  evidence; neither is an observable that resolves synchronously during the
  triggering request (ISSUE-2134). Discover a forwarded object by discriminator
  scan, never by the sender's original ID (ISSUE-2178). Use `demo_gate` (stops
  dependent steps) for preconditions and `demo_check` (advisory) for assertions,
  and never patch either out with `nullcontext` in tests. See EDF-06, DEMOMA-22,
  DEMOCI-01-007, ADR-0058,
  [notes/event-driven-control-flow.md](notes/event-driven-control-flow.md)
  § "Temporal Sequence vs. Causal Sequence", and
  [`vultron/demo/AGENTS.md`](vultron/demo/AGENTS.md). *Source: CONCERN-2181*
- **`SemanticEntry` Phrases MUST Use Only `{actor}`, `{object}`, `{target}`** —
  the runtime render pipeline (`CaseTimelineEvent.summary`, `event_phrase()`)
  never fills `{context}`, `{origin}`, or `{inner_object}`. A phrase referencing
  one of those slots passes the `defaultdict`-based SE-07-004 test (which fills
  every slot with `"X"`) but produces a dangling `"—"` in production. The
  allowlist test (SE-07-005 in `test/test_semantic_registry.py`) enforces this
  structurally. *Source: CONCERN-1898*

---

See each subsystem AGENTS.md for additional pitfalls:

- **BT design decisions**: [notes/bt-integration.md](notes/bt-integration.md)
  (when to use BTs, actor isolation, concurrency model, composability)
- **BT canonical reference**: [notes/bt-canonical-reference.md](notes/bt-canonical-reference.md)
  (subtree map, BT-IDM anti-patterns, how to locate new behaviors)
- **BT pitfalls**: [notes/bt-pitfalls.md](notes/bt-pitfalls.md)
  (blackboard, idempotency, role guards, memory=False, routing-gated mutation)
- **ActivityStreams/wire**: [notes/activitystreams-semantics.md](notes/activitystreams-semantics.md)
- **ActivityStreams state/DR bugs**: [notes/activitystreams-state-update.md](notes/activitystreams-state-update.md)
- **Core layer**: [`vultron/core/AGENTS.md`](vultron/core/AGENTS.md)
- **Adapters**: [`vultron/adapters/AGENTS.md`](vultron/adapters/AGENTS.md)
- **Codebase structure**: [notes/codebase-structure.md](notes/codebase-structure.md)
- **FastAPI/test patterns**: [notes/codebase-structure-fastapi-patterns.md](notes/codebase-structure-fastapi-patterns.md)
- **DataLayer**: [notes/datalayer-design.md](notes/datalayer-design.md)

## Skill Interaction Rules

- Always use the `ask_user` tool for user questions — never plain text.
- Provide a recommended answer on every `ask_user` call.
- Rule applies transitively when skills compose (`learn` → `grill-me`, etc.).

---

## Governance note for agents

Agents MAY update `AGENTS.md` to correct/clarify rules, but substantive
changes SHOULD be discussed via Issue or PR. Include rationale in the commit
message.

---

## Miscellaneous tips

- Use `markdownlint-cli2` for markdown; `black` is Python-only. Default config
  ignores only `wip_notes/**`; all other dirs are linted.
- **Notes frontmatter** (NF-06-001, NF-06-002): every `notes/*.md` (except
  `README.md`) needs `title` and `status` frontmatter. `superseded_by` is a
  scalar string. Schema: `vultron/metadata/notes/schema.py`.
- **Docs links must be relative**: links in `docs/` MUST be relative and MUST NOT
  go above `docs/`. Run `uv run mkdocs build --strict` before committing docs.
  `docs/developer/` pages are draft docs — visible in `mkdocs serve` but excluded from production builds.
- **Demo script lifecycle logging**: see
  [`vultron/adapters/AGENTS.md`](vultron/adapters/AGENTS.md) for `demo_step` /
  `demo_check` pattern.
- **Project history entries**: use `uv run append-history` — never write
  directly to `plan/history/`. See HM-01–HM-05 and
  `notes/history-management.md`. During `orient-agent`, read only `plan/*.md`.

---

## Agent skills

### Issue tracker

Issues live in GitHub Issues. See `docs/agents/issue-tracker.md`.

**Never use `gh issue create`** — it cannot set issue types, parent/child
relationships, or blocker/blocked-by links. Use
`.agents/skills/manage-github-issue/manage_github_issue.sh` or the
`createIssue` GraphQL mutation directly. Type IDs and relationship mutations:
`.agents/skills/manage-github-issue/REFERENCE.md`.

**Never pass backtick-containing markdown in a double-quoted `--body`.**
Use a single-quoted heredoc:

```bash
gh issue comment <N> --repo CERTCC/Vultron --body "$(cat <<'EOF'
Use `code` freely here.
EOF
)"
```

Same rule applies to `gh issue edit --body`, `gh pr create --body`, etc.

### Triage labels

`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`.
See `docs/agents/triage-labels.md`.

### Domain docs

Single-context repo: one `CONTEXT.md` + `docs/adr/` at root. See `docs/agents/domain.md`.
