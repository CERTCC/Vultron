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

- **Load specs first**: `PYTHONPATH= uv run spec-dump --index` (map), then
  `--topic`/`--group`/`--ids`; never raw `specs/*.yaml`. `PYTHONPATH=` required.
- Pipeline: FastAPI inbox → AS2 parser → semantic extraction
  (`vultron/wire/as2/extractor/`) → dispatcher → use-case callable
  (`vultron/core/use_cases/`).
- Use-Case Protocol: `__init__(dl, request)` + `execute() -> HandlerResult`
  (received, ADR-0095) or the verb's `TriggerResult` subtype (trigger, ADR-0110),
  both in `core/models/use_case_result.py`; routing via `use_case_map()` key
  lookup. `DispatchNode` maps the verdict onto `InboxOutcome.status`.
- ASGI entrypoint: `vultron.adapters.driving.fastapi.main:app`.
- Tests: `uv run pytest --tb=short > /tmp/last-test-run.log 2>&1; rc=$?; tail -5 /tmp/last-test-run.log; echo "exit: $rc"; (exit $rc)`
  — run once; read `exit:` first. Never end a gate command with a pipe: a pipeline exits with its last stage's status, so a killed run reads as success. See `.agents/skills/run-tests/SKILL.md`.

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
**ruff** (lint + format), **mypy**, **pyright**, **markdownlint-cli2** (`mdlint.sh`).
No other frameworks/package managers without approval (`ui/` Node/React: ADR-0104).

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
  **Critical**: for a *domain* type, `as_VulnerabilityCase` and
  `VulnerabilityCase` are the same class — ADR-0099 detail 3 aliased all 27
  paired names onto core. The prefix still marks a real wire class for
  unpaired AS2 vocabulary (`as_Link`, …). See ARCH-14-001.
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
  `NonEmptyString` from `vultron/primitives.py` (`NonEmptyString | None` when
  optional; CS-08-002). Do NOT add per-field `@field_validator` stubs for
  empty-string rejection; extend the shared type alias. See CS-08-001, CS-08-002.

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

- **Under `docs/`**: SG-38 governs — one sentence per line, **no mid-sentence hard
  wrap**, and no line-length limit (`markdownlint` MD013 is disabled). Do **not**
  reflow docs prose to a column width: it destroys the per-sentence diff SG-38
  exists to give, which is how a doubled-list-marker defect reached green CI in
  #3458. See `.claude/skills/shared/docs-style-guide.md`.
- **Everywhere else** (`notes/`, `specs/`, `plan/`, READMEs): 88 chars max
  (exceptions: tables, code blocks, long URLs); break long sentences at natural
  points.
- Use `markdownlint-cli2` for linting; see Miscellaneous tips for commands

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
- **Dispatchers**: `vultron/core/dispatcher.py`, `vultron/core/trigger_dispatcher.py`
- **Inbox**: `vultron/adapters/driving/fastapi/routers/actors/` (package; `_routes.py` defines endpoints)
- **Errors**: `vultron/errors.py`
- **Demo**: `vultron/demo/cli.py` (entry point)
- **Case States**: `vultron/core/states/cs.py` (CS/VFD/PXA enums, authoritative)
  and `cs_invariants.py` (CSB-17 invariants) → [notes/case-state-model.md](notes/case-state-model.md)
  for the legacy-oracle relationship (ADR-0060)

Full core-layer map → [`vultron/core/AGENTS.md`](vultron/core/AGENTS.md).
Full wire-layer map → [`vultron/wire/as2/AGENTS.md`](vultron/wire/as2/AGENTS.md).
Full adapter-layer map → [`vultron/adapters/AGENTS.md`](vultron/adapters/AGENTS.md).

### Constructing Outbound Activities

All outbound activities MUST use factory functions in
`vultron.wire.as2.factories`. See
[`vultron/wire/as2/AGENTS.md`](vultron/wire/as2/AGENTS.md) for details.

### GitHub Issue Labels

**GitHub Project #24** `Schedule` (Focus/Now/Next/Later/Someday) is on **Epics only**;
other issues take their nearest Epic's tier and carry a mirrored `Status`. No `group:`
labels. See `notes/parallel-development.md` § "Project #24: Two Paths".

## Change Protocol

For non-trivial changes: state assumptions → load governing specs (`deepen-context`) →
review `notes/` → describe intent → apply minimal diff → update/add tests →
call out risks.

For architectural changes, draft an ADR first. Use the decision-tree in
`notes/specs-vs-adrs.md` (MS-11-001 through MS-11-006) to decide ADR vs. spec
entry vs. both.

### Commit Workflow

**Before committing**, run skills in order:

1. `run-linters` — ruff (lint + format), mypy and pyright must all pass.
   Supersedes `format-code`, so run it alone — no separate `format-code` step.
2. `run-tests` — unit suite once; read the `exit:` line. If `vultron/demo/` or
   `test/demo/` touched, also run the full suite (`-m ""`, same redirect form).
3. `build-docs` if `docs/` modified; `check-docs-sync` runs regardless (PD-03-008)
4. `commit` skill — include Co-authored-by trailer

**PR body**: use `.agents/skills/shared/pr-body-guide.md` template. Put
`- Closes #N` at top, one per line.

**`append-history`**: stage the new entry file (`git add plan/history/`).
The monthly `README.md` under `plan/history/YYMM/` is gitignored — do not stage it.

Pre-commit hooks are fail-only. If a hook fails, run `run-linters` (ruff, mypy,
pyright) or `format-code` (ruff fixes + format), re-stage, then commit.

**Lint memoization**: mypy and pyright run through `run-if-changed.sh`, which
skips a tool when its inputs are unchanged since the last success (a `... skipping`
line is expected, not an error); ruff is fast enough to run bare. See `run-linters`.

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
`AGENTS.md`, then **extend a cell below — this file has a 400-line budget, so trim as you add, never append**.

### Where to look

| Symptom area | Read | Pitfalls covered |
|---|---|---|
| Wire/core boundary | [wire-core-boundary](notes/wire-core-boundary.md) | wire may import only `core/models`+`core/states` (ARCH-22-001 allow-list; ARCH-01-001 is the other direction); union validators raise `ValueError`; core `extra="forbid"`, no alias key beside its twin (ARCH-12-003); IRI branch is `NonEmptyString` → `strip_annotated()` (#3876); unknown inbound keys decided at the parse edge, `@id`/`@type` are near misses (MV-11, #3900) |
| Core needs camelCase | [core-wire-rendering-port](notes/core-wire-rendering-port.md) | `to_camel` inherited by every `CoreObject` (ADR-0099), but core never builds wire shape — delivery via `WireRenderPort` (ARCH-20-001, CLP-07-009/010); empty `by_alias` baseline; missing port is `VultronWiringError`, never a fallback (#3930) |
| Wire vs. core class names | [vocabulary-registry](notes/vocabulary-registry.md) | `as_` prefix (ARCH-14-001); `VOCABULARY` (class name) vs. `WIRE_TYPE_MAP` (derived `type` value) are disjoint (ARCH-23-002, VM-01-004/008); shared `type` → `_wire_type_alias`; `find_in_vocabulary` is wire-only unless `include_core=True` (VM-06-008); needs a `Literal` `type_` to register (VM-03-002) |
| Domain object validation | [domain-validation](notes/domain-validation.md) | assignment/`append` bypass validation (CM-27-001); no `self` assignment in `mode="after"` (ARCH-21-004); silent `None` = fake `SUCCESS` (ARCH-15); `getattr` misses `ValueError`; `__init_subclass__` pitfalls; report every violation (EH-07-001); `participant_transition_violations()` only (BTND-10-002); `force_rm_state` is bootstrap-only (RMB-14-005); trigger fail-closed vs. receive partial-accept is deliberate (Postel) |
| Behavior tree nodes | [bt-pitfalls](notes/bt-pitfalls.md) | write nodes validate own transitions (CSB-16); guarded commits as CASE_MANAGER (BT-17-005); store follows executing actor, but a received RM write is about the sender (RSH-08-001); don't clear keys you don't own; guards name the transition; **refusal arms fail toward admit** — record first, guards raise, key on the request; log via `node_logger(node)` (SL-01-005, [structured-logging](notes/structured-logging.md)) |
| BT integration / concurrency | [bt-integration](notes/bt-integration.md), [bt-pitfalls](notes/bt-pitfalls.md) | module-level `RLock` under `BackgroundTasks`; trigger `execute()` delegates SM transitions (BT-15-001); `internal_error is False` ≠ "no bug" — node `except Exception` and nested `BTBridge` hops hide it |
| Case ledger | [case-ledger-authority](notes/case-ledger-authority.md), [ownership-transfer](notes/ownership-transfer.md) | not a process log (CLP-07); one role-gated commit, already injected by the factory (CLP-09-001); two timestamps — commit stamp vs. claimed `published`, monotonic per snapshot actor but reported, never refused (CLP-15-003/005); blank/missing `published` refused at parse (CLP-15-006); nested times carried as received (ADR-0103); replicas see only ledger entries (CM-23-005, #2505) |
| Who sends what to whom | [case-communication-model](notes/case-communication-model.md), [case-joining](notes/case-joining.md) | roster ≠ entitlement — recipients only via `core/participants/recipients.py` (CM-10-004/005/007, ADR-0114, #4100); joiners answer the full-case Invite (CM-11-005); participants message only the CASE_MANAGER (PCR-08, ADR-0109); gated effects → `REFUSED` (BT-17-001, HP-01-005); the gate checks the receiver, never the sender — sender entitlement declared once per use case, composed by the factory (HP-01-006/007, ADR-0115); embargo proposals relayed (EP-09, ADR-0113); manager never unfilled (CM-24-006) |
| Pattern matching / semantics | [activitystreams-semantics](notes/activitystreams-semantics.md), [activitystreams-state-update](notes/activitystreams-state-update.md), [`vultron/wire/as2/AGENTS.md`](vultron/wire/as2/AGENTS.md) | patterns match the inbound wire format; `target_` permissive unless `strict=True` (SE-08); `Reject(Invite)` case in `inner_target` (CM-11-003); phrase placeholders (SE-07-005); no `origin_` field — examples must match exactly one pattern (#3438) |
| Persistence / stores | [datalayer-design](notes/datalayer-design.md) | `dl.read()` returns core objects (ADR-0034), no wire re-read for semantics (ADR-0035); actor id is a store name (DL-07-004); `_dehydrate_data` keeps inline snapshots; a clock-minted wire default can't round-trip a URI-only core field (#3732); a renamed stored field refuses its old key via `RetiredFieldsRecord`, never an alias (#4128) |
| Embargo / consent | [embargo-lifecycle](notes/embargo-lifecycle.md), [participant-embargo-consent](notes/participant-embargo-consent.md) | go through `EmbargoLifecycle`, never inline `EMAdapter`; consent only via `apply_pec_transition()` (CM-18-005/006), no downgrade on retry; proposals change no consent, lapse only on activating longer terms (ADR-0093); a revision Invite never re-INVITEs a SIGNATORY (EP-09-004); termination clears every proposal (EP-08-004); default embargo once per case, keyed on EM ≠ `NONE` (EP-04-012; [embargo-default-semantics](notes/embargo-default-semantics.md), #3393, #4019) |
| Participant records | [participant-role-management](notes/participant-role-management.md) | RM mutation uses `actor_participant_index` (CM-19-003); RM terminal guard before same-state shortcut |
| Devcontainer / tooling | [devcontainer-tooling](notes/devcontainer-tooling.md) | always `uv run`, `PYTHONPATH=` cleared, `UV_NO_SYNC=1` on sync failure; ruff runs bare (IMPLTS-07-021); `SKIP=actionlint` (hangs); `git push -u origin HEAD`, HTTP/1.1 retry (#3893, #3905); edit `.agents/skills`, not the `.claude` symlink |
| Spec/notes/ADR/history tooling | [`vultron/metadata/AGENTS.md`](vultron/metadata/AGENTS.md), [agentic-workflow](notes/agentic-workflow.md) | learning filename slug ≠ `source` (BW-01-003, #1857); loaders name failing files `path:line:col` via `file_loading.py` (MS-17) — YAML errors aren't `ValueError`; pre-code spec needs `lint_suppress: [phantom_path_ref]` |
| git / branches / PRs | [git-workflow-pitfalls](notes/git-workflow-pitfalls.md) | false-positive rebase "local changes"; conflict-free ≠ working merge; integration branches for related fixes; re-check ADR numbers; verify ACs on `origin/main`, always `Closes #N`, prose ACs skip the pre-claim gate (#1907) |
| GH Actions / CI YAML | [ci-workflow-authoring](notes/ci-workflow-authoring.md) | red job ≠ assertions ran, all-skipped = green; `notify-failure` mandatory (CISEC-05); bare `on:` → `True`; matrix booleans job vs. step; `python3 -c` breaks `actionlint`; YAML apostrophes |
| Spec authoring | [spec-authoring-rules](notes/spec-authoring-rules.md) | strict `kind`/`priority`/`rel_type` enums; `adr:` not `references:`; `kind: protocol` needs marker test or strict `xfail`; CASE_MANAGER not "CaseActor" (ADR-0088); item format = field presence, not `isinstance` (ADR-0101); advisories need a ceiling |
| Specs vs. ADRs, doc drift | [specs-vs-adrs](notes/specs-vs-adrs.md), [documentation-sweeps](notes/documentation-sweeps.md) | ADR "what is removed" is scoped to one use; no counts in long-lived docs (MS-16-001); moving a claim ≠ verifying it, share by `include-markdown` fragment (DF-10-001/002) |
| Tests | [testing-pitfalls](notes/testing-pitfalls.md), [`test/AGENTS.md`](test/AGENTS.md) | killed run reads exit 0 under `tail -5`; vacuous assertions; "falls back to" on malformed input asserts a bug; process-global blackboard/registries (`isolated_core_registries`); `caplog` catches fixture setup; timeout method vs. ceiling (#3603); directory-hook markers need a `trylast` probe (#3604) |
| Demo scenarios | [`vultron/demo/AGENTS.md`](vultron/demo/AGENTS.md), [demo-scenario-authoring](notes/demo-scenario-authoring.md), [demo-scenario-registry](notes/demo-scenario-registry.md) | puppeteer via triggers, never inbox injection or mail-carrying; gate steps on their cause (EDF-06, ADR-0058); protocol activity lives in `helpers/workflow.py` ([demo-ci-diagnostics](notes/demo-ci-diagnostics.md)); declare a scenario once with `@scenario`, all inventories generated, no `@main.command`, unbuilt ones go in `demo-future-ideas.md` (ADR-0098, DEMOCI-11) |
| Inbox / outbox | [inbox-orchestration](notes/inbox-orchestration.md), [inbox-pipeline](notes/inbox-pipeline.md), [outbox-delivery-reliability](notes/outbox-delivery-reliability.md), [`vultron/adapters/AGENTS.md`](vultron/adapters/AGENTS.md) | inbox policy in `core/behaviors/inbox/`, `process_payload` sole entry (IO-02-001/003); catch `UnroutableActivityError` inside `_handle`; retry caps composing to `4 × ∞` (OX-13); inbox has no read surface (IE-02-003/004, #3141); outbox relays the sealed body, never a re-read (OX-07-001, VM-08-003) |
| Call-out points | [call-out-configuration](notes/call-out-configuration.md) | automation potential ≠ call-out shape (ADR-0024); an externally-versioned capability is **one** call-out unit (BTND-05-007) |

### Cross-cutting rules with no other home

- **Module splits** (no god modules, re-export moved names, importer proof before
  deleting), small coding habits, Protocol sync (CS-20), `HashChainLedgerRecord`
  ≠ `CaseLedgerEntry`: [notes/codebase-structure.md](notes/codebase-structure.md).
- **BT/use-case**: no DataLayer writes in `execute()`, even via a helper (CLP-10-020,
  `test_no_dl_mutations_in_execute.py`); received trees run intake → guards →
  commit → effects, ledger commits only via `CommitCaseLedgerEntryNode`
  (CLP-10-006/019, BT-06-006, ADR-0111) — [notes/bt-integration.md](notes/bt-integration.md);
  emit nodes fail fast without a CASE_MANAGER recipient (PCR-08-011), broadcasts
  never mask delivery failure (BT-14-001) — [notes/bt-pitfalls.md](notes/bt-pitfalls.md).
- **Adapters/ports**: stubs raise `NotImplementedError` (OX-10-004, OX-11-004),
  transport-role names stay explicit —
  [notes/architecture-adapters.md](notes/architecture-adapters.md); idempotency chain
  [`vultron/core/AGENTS.md`](vultron/core/AGENTS.md); no `BaseModel` in ports
  [`vultron/core/ports/AGENTS.md`](vultron/core/ports/AGENTS.md); ledger commit before
  outbox write (under review, ADR-0119) [`case/AGENTS.md`](vultron/core/behaviors/case/AGENTS.md).
- **Logging**: bulk level refactors need a consistency grep; self-healing paths never
  log at ERROR — [notes/structured-logging.md](notes/structured-logging.md).
- **Agent workflow**: archive superseded notes sections with `append-history note`
  (PD-03-002/004, [notes/history-management.md](notes/history-management.md));
  partition large migrations by node shape, then domain, within the 200-turn fork
  cap ([notes/agentic-workflow.md](notes/agentic-workflow.md)).
- **MkDocs scope**: `not_in_nav` ≠ `exclude_docs` ≠ lint scope; a zero-target gate
  fails; withholding a page does not unlink it — `docs-links` checks every built
  `site/` file (DF-09-007/009, ADR-0092, DOCBW-03-007):
  [notes/documentation-strategy.md](notes/documentation-strategy.md).

---

## Skill Interaction Rules

Ask the user anything per [`.agents/skills/shared/asking-the-user.md`](.agents/skills/shared/asking-the-user.md), in every session and when skills compose (`learn` → `grill-me`):
**one question at a time**; **problem before decision** (the problem, why it matters, each option spelled out, your recommendation and why); **plain language**, no metaphor jargon or coined terms;
**no bare IDs** ("#3512 (the docs navigation reorganization)," not "#3512"); **restate, don't point** by number; **short**, no walls of text ending in "do you agree?" Use `ask_user` for short, discrete choices, with a recommended answer; use plain text when a longer reply is likely.

---

## Governance note for agents

Agents MAY update `AGENTS.md` to correct/clarify rules, but substantive changes
SHOULD be discussed via Issue or PR. Include rationale in the commit message.

---

## Miscellaneous tips

- Use `markdownlint-cli2` for markdown; `ruff format` skips it. Default config
  ignores only `wip_notes/**`; all other dirs are linted.
- **Notes frontmatter** (NF-06-001, NF-06-002): every `notes/*.md` (except
  `README.md`) needs `title` + `status`. **Maintenance rule:** when you modify a
  note, update its `status`, `related_specs`, and `related_notes` in the same
  change; cross-links SHOULD be two-way. Full write-up + schema:
  [notes/notes-frontmatter.md](notes/notes-frontmatter.md).
- **Docs links must be relative** and MUST NOT go above `docs/`. Run
  `uv run mkdocs build --strict` before committing docs. `docs/developer/` pages
  are draft docs — visible in `mkdocs serve`, excluded from production builds.
- **Demo script lifecycle logging**: see
  [`vultron/adapters/AGENTS.md`](vultron/adapters/AGENTS.md) for `demo_step` /
  `demo_check` pattern.
- **Project history entries**: use `uv run append-history` — never write directly
  to `plan/history/`. See HM-01–HM-05 and `notes/history-management.md`.
  `orient-agent` reads `plan/*.md` and `learnings-index`, never `plan/history/`.

---

## Agent skills

### Issue tracker

Issues live in GitHub Issues. See
[docs/agents/issue-tracker.md](docs/agents/issue-tracker.md) for the full rules.
Non-negotiables:

- **Never use `gh issue create`** — it cannot set issue types or parent/child
  and blocker links. Use
  `.agents/skills/manage-github-issue/manage_github_issue.sh` (or the
  `createIssue` GraphQL mutation).
- **Epics are the `Epic` issue type, not a label** — detect by
  `issueType.name == "Epic"`, not a label query; create with the `create-epic`
  skill.
- **Never pass backtick markdown in a double-quoted `--body`** — use a
  single-quoted heredoc.

### Triage labels

`needs-info` (the only hold), `ready-for-human` (agents skip it). The other
labels in `docs/agents/triage-labels.md` are being retired (#3717).

### Domain docs

Single-context repo: one `CONTEXT.md` + `docs/adr/` at root. See `docs/agents/domain.md`.
