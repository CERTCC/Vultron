# AGENTS.md — Vultron Project

## Purpose

This file provides quick technical reference for AI coding agents working in
this repository. Agents MUST follow these rules when generating, modifying, or
reviewing code.

**See also**: `notes/` — durable design insights, committed to version control
and authoritative for design decisions (start at
[notes/README.md](notes/README.md)); `specs/project-documentation.yaml` —
documentation structure guidance.

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
- Tests: `uv run pytest --tb=short 2>&1 | tee /tmp/last-test-run.log | tail -5` — run once. See
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

## Project Vocabulary and Default Behavior

Use **`vul`** (not `vuln`) for vulnerability. Prefer domain terms already present
in the codebase; do not invent terminology without justification.

If instructions are ambiguous: choose correctness over convenience, explicitness
over brevity, and ask for clarification rather than assuming intent.

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

This is an **index**, not the write-ups. Find your symptom area below, read the
linked file before touching that area. New pitfalls MUST be routed per
[notes/agents-md-structure.md](notes/agents-md-structure.md): write-up in the nearest `notes/` or per-directory
`AGENTS.md`, then **extend a cell below — this file is at its 400-line budget, so trim as you add, never append**.

### Where to look

| Symptom area | Read | Pitfalls covered |
|---|---|---|
| Wire/core boundary | [wire-core-boundary](notes/wire-core-boundary.md) | no new `vultron.core.models` imports in `vultron/wire/` (ARCH-22-001/002); union-exposed validators must raise `ValueError` subclasses; `extra="forbid"` needs self-round-trip; deleting a wire-spelling shim without a reject-guard is silent data loss (SDO-03-005); ARCH-01-001 ≠ ARCH-22-001 |
| Core needs camelCase | [core-wire-rendering-port](notes/core-wire-rendering-port.md) | never `alias_generator`/`by_alias=True` in core — go through `WireRenderPort` (ARCH-20-001, CLP-07-009/010) |
| Wire vs. core class names | [vocabulary-registry](notes/vocabulary-registry.md) | `as_` prefix rule (ARCH-14-001); `VOCABULARY` and `WIRE_TYPE_MAP` keys are disjoint (ARCH-23-002) |
| Domain object validation | [domain-validation](notes/domain-validation.md) | assignment and `append` bypass validation (CM-27-001, PRM-03-003); no `self` assignment in `mode="after"` validators (ARCH-21-004); silent `None` == fake `SUCCESS` (ARCH-15); `getattr` misses `ValueError`; `model_fields` is empty in `__init_subclass__`; rejecting atomically does **not** license reporting only the first violation (EH-07-001, ADR-0084); trigger path fails closed while receive path partial-accepts — Postel's maxim, do not "reconcile" them |
| Behavior tree nodes | [bt-pitfalls](notes/bt-pitfalls.md) | write nodes validate their own transitions (CSB-16, EMB-18-001); guarded commits run as CASE_MANAGER (BT-17-005/006); a BT's store follows its executing actor (BT-05-005/006); never clear a blackboard key you don't own; guard names name the transition, not the symptom |
| BT integration / concurrency | [bt-integration](notes/bt-integration.md) | blackboard needs a module-level `RLock` under `BackgroundTasks`; trigger-side `execute()` delegates SM transitions (BT-15-001) |
| Case ledger | [case-ledger-authority](notes/case-ledger-authority.md), [ownership-transfer](notes/ownership-transfer.md) | ledger is not a process log (CLP-07); commits are role-gated (CLP-09); `create_receive_activity_tree` already injects the guarded commit — a second one in `effect_nodes` forks the chain (CLP-09-001) |
| Who sends what to whom | [case-communication-model](notes/case-communication-model.md) | `case_addressees()` is the wrong recipient (PCR-08-001/002); no identity spoofing or foreign CaseActor IDs on the received side; Invite/Accept routes through the Case Actor (PCR-08-007/008); delegated emit sets `actor=case_actor_id`, `attributed_to=requesting_actor_id` and gates on the **role** (CM-24) |
| Pattern matching / semantics | [activitystreams-semantics](notes/activitystreams-semantics.md), [activitystreams-state-update](notes/activitystreams-state-update.md) | registry patterns must match the inbound wire format; `target_` is permissive unless `strict=True` (SE-08); `Reject(Invite(…))` carries the case in `inner_target` (CM-11-003); `SemanticEntry` phrases use only `{actor}`/`{object}`/`{target}` (SE-07-005) |
| Persistence / stores | [datalayer-design](notes/datalayer-design.md) | `dl.read()` returns core objects (ADR-0034); core must not re-read wire activities for semantics (ADR-0035); an actor id **is** a store name (DL-07-004); `_dehydrate_data` deliberately keeps inline Activity sub-fields as snapshots |
| Embargo / consent | [embargo-lifecycle](notes/embargo-lifecycle.md), [participant-embargo-consent](notes/participant-embargo-consent.md) | delegate to `EmbargoLifecycle`, never inline `EMAdapter`; consent only via `apply_pec_transition()` (CM-18-005/006); `embargo_adherence` is a `@computed_field` (ADR-0056); don't downgrade consent on retries; test `REVISE → REVISE` separately |
| Participant records | [participant-role-management](notes/participant-role-management.md) | `actor_participant_index` is the fast path, and RM mutation MUST use it (CM-19-003); RM terminal guard runs before the same-state shortcut |
| Devcontainer / tooling | [devcontainer-tooling](notes/devcontainer-tooling.md) | always `uv run`; clear `PYTHONPATH` first; `UV_NO_SYNC=1` on sync failures; wrong `gh` path in the credential helper; `.agents/` and `.claude/` skills are hard links — edit only `.agents/` |
| git / branches / PRs | [git-workflow-pitfalls](notes/git-workflow-pitfalls.md) | rebase "local changes" can be a false positive; conflict-free ≠ working merge; related fix PRs need an integration branch (`create-pr` can't target one); `claim-issue.sh` needs a synced branch; re-check ADR numbers before merge; verify every AC against `origin/main` and always add `Closes #N`; scan peer files before closing |
| GH Actions / CI YAML | [ci-workflow-authoring](notes/ci-workflow-authoring.md) | a red job may never have run its assertions (and an all-skipped run is green); `notify-failure` is mandatory on `main`/`schedule` (CISEC-05); PyYAML reads bare `on:` as `True`; matrix booleans differ job- vs. step-level; `python3 -c` blocks break `actionlint`; single-quoted YAML needs doubled apostrophes |
| Spec authoring | [spec-authoring-rules](notes/spec-authoring-rules.md) | strict enums for `kind`/`priority`/`rel_type`; `references:` is dropped (use `adr:`); a new `kind: protocol` entry needs a marker test or strict `xfail`; grep bare filenames when retiring a name; "CaseActor MUST …" is usually a role/object category error |
| Specs vs. ADRs, doc drift | [specs-vs-adrs](notes/specs-vs-adrs.md) | ADR "what is removed" lists are scoped to one use; never restate counts in long-lived docs (MS-16-001) |
| Tests | [testing-pitfalls](notes/testing-pitfalls.md), [`test/AGENTS.md`](test/AGENTS.md) | a killed run reports exit 0 under `tail -5`; vacuous assertions (third participant, hash presence, `MagicMock(spec=)`); "falls back to" on malformed input asserts a bug; process-global `py_trees` blackboard and class registry; `caplog` catches fixture setup; two emitter resolution paths; delete `devlogs/` first |
| Demo scenarios | [`vultron/demo/AGENTS.md`](vultron/demo/AGENTS.md), [demo-scenario-authoring](notes/demo-scenario-authoring.md) | puppeteer via triggers, never spoof via inbox injection; never carry one actor's mail to another's inbox; gate steps on their cause, not script position (EDF-06, ADR-0058); protocol activity is emitted from `helpers/workflow.py`, not the scenario files |
| Inbox / outbox | [inbox-orchestration](notes/inbox-orchestration.md), [inbox-pipeline](notes/inbox-pipeline.md), [outbox-delivery-reliability](notes/outbox-delivery-reliability.md) | inbox policy belongs in `vultron/core/behaviors/inbox/` (IO-02-003); catch `UnroutableActivityError` inside `_handle`; retry caps that compose to `4 × ∞` are a resource hazard (OX-13) |
| Call-out points | [call-out-configuration](notes/call-out-configuration.md) | automation potential ≠ call-out shape (ADR-0024); an externally-versioned capability is **one** call-out unit (BTND-05-007) |

### Cross-cutting rules with no other home

- **Splits must not produce new god modules** — submodules ≤500 lines, split
  recursively when they re-accumulate (CS-18-001–004). A leaf within ~20 lines of
  the cap must be split *before* you add docstrings (BTND-07-004/006). Flat
  `nodes.py` in a BT area is non-compliant (BTND-07-001/003).
- **Splits must re-export** — use-case subpackages re-export classes *and* request
  models; module splits re-import moved names for `monkeypatch` (`# noqa: F401`,
  #972); FastAPI router packages re-export `dependency_overrides` keys (#970).
  Deleting a module instead needs importer proof: no live importers in `vultron/`
  or `test/`.
- **`dl.save/create/update/delete()` in `execute()` bypasses the BT audit trail** —
  ratchet: `test/architecture/test_no_dl_mutations_in_execute.py` (#1071).
- **Receive-side ordering is guards → commit → effects** (CLP-10-006), and
  received-side `execute()` never calls `commit_log_entry_trigger()` directly
  (BT-06-006, SYNC-02-002).
- **Stub adapter files must raise `NotImplementedError`** — docstring-only stubs
  hide integration gaps (OX-10-004, OX-11-004).
- **Protocol-declared fields must stay in sync with concrete classes**, and
  `TypeGuard` discriminators may `hasattr`-check only Protocol-declared attributes
  (CS-20-001/002).
- **Emit nodes in case-scoped trigger BTs fail fast on a missing CaseActor**
  (PCR-08-011); **peer broadcast nodes must not mask delivery failure with
  SUCCESS** (BT-14-001).
- **Small habits**: mypy infers a type from the first branch assignment (use
  distinct names per `except`/`if`-else branch); pre-build dedup sets before
  fallback loops (`seen = set(d.values())`, O(n×m) → O(n+m)); walrus for
  single-assignment guards (`if (f := self._require_factory()) is not None`).
- **Bulk logging-level refactors need a consistency grep pass**, and designed
  self-healing recovery paths log WARNING/INFO, never ERROR
  ([notes/structured-logging.md](notes/structured-logging.md)).
- **Superseded notes sections are archived via `append-history note`** (PD-03-002,
  PD-03-004); **large migrations partition by node shape, then domain**
  ([notes/agentic-workflow.md](notes/agentic-workflow.md)); **MkDocs `not_in_nav`
  and `exclude_docs` are not the same**
  ([notes/documentation-strategy.md](notes/documentation-strategy.md)).
- **Transport-role naming must stay explicit** — core ports docs, adapter notes,
  ADR refs and codebase reference pages change together. Likewise
  `HashChainLedgerRecord` (in-memory) vs. `CaseLedgerEntry` (wire-serializable):
  distinct types, imported by full module path (ARCH-12-007).
- **Idempotency responsibility chain** —
  [`vultron/core/AGENTS.md`](vultron/core/AGENTS.md); **avoid `BaseModel` in
  ports** — [`vultron/core/ports/AGENTS.md`](vultron/core/ports/AGENTS.md);
  **ledger commit precedes outbox write** and **local-only correlation markers use
  `disposition="rejected"`** —
  [`vultron/core/behaviors/case/AGENTS.md`](vultron/core/behaviors/case/AGENTS.md).

---

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
  scalar string. Schema: `vultron/metadata/notes/schema.py`. **Maintenance rule
  (NF-06-001, documented here per NF-06-002):** when you modify a note, review
  and update its `status`, `related_specs`, and `related_notes` in the same
  change — a new spec citation or cross-note link in the body means a new
  frontmatter entry, and cross-links SHOULD be two-way.
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
