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
  `--topic`/`--group`/`--ids`; never raw `specs/*.yaml`. Old images need `PYTHONPATH=`.
- Pipeline: FastAPI inbox → AS2 parser → semantic extraction
  (`vultron/wire/as2/extractor/`) → dispatcher → use-case callable
  (`vultron/core/use_cases/`).
- Use-Case Protocol: `__init__(dl, request)` + `execute() -> HandlerResult`
  (received, ADR-0095) or the verb's `TriggerResult` subtype (trigger, ADR-0110),
  both in `core/models/use_case_result.py`; routing via `use_case_map()` key
  lookup. `DispatchNode` maps the verdict onto `InboxOutcome.status`.
- ASGI entrypoint: `vultron.adapters.driving.fastapi.main:app`.
<!-- markdownlint-disable-next-line MD013 -->
- Tests: one gate, always targeted — `logs="/tmp/vultron-$(basename "$(git rev-parse --show-toplevel)")"; git fetch -q origin main || { echo "fetch failed — stop and report"; exit 1; }; gate=$(PYTHONPATH= uv run targeted-tests --base origin/main --pytest); rc=$?; [ "$rc" -eq 0 ] && { eval "$gate" > "$logs-gate.log" 2>&1; rc=$?; tail -20 "$logs-gate.log"; }; echo "exit: $rc"; (exit $rc)`
  — run once; read `exit:` first; never end a gate command with a pipe. No local
  gate runs the whole suite; CI does, and GitHub requires it (PAD-18-003/008).

Quick gotchas: specific patterns before general; always `rehydrate()` before
pattern matching; persist with `dl.save(obj)`; return 202 immediately
(`BackgroundTasks`); architecture changes → ADR first.

## Scope of Allowed Work

Agents MAY: implement small–medium features, refactor without behavior change,
add/update tests, improve typing/validation/error handling, update docs/specs,
implement against `proposed` ADRs (the human touch is the epoch-2 ask, ADR-0120).

Agents MUST NOT: introduce breaking API changes, modify auth/crypto logic, change
persistence schemas without explicit instruction, touch production deployment or
secrets (CI workflows are in scope; follow `notes/ci-workflow-authoring.md`).
**Crypto carve-out (ADR-0164):** agents MAY build the prototype's seeded-key signing
and verification (epic #1156); production key handling (#1184) stays excluded, and
a crypto PR waits for human review before merge.

Small tweaks need no ADR; architectural/protocol changes SHOULD have one before merging.

---

## Technology Stack (Authoritative)

Runtime: Python **3.14+** (CI: 3.14), **FastAPI** (BackgroundTasks for long
ops), **Pydantic v2**, **pytest**, **mkdocs** (Material). Dev tools: **uv**,
**ruff** (lint/format), **mypy**, **markdownlint-cli2** (`mdlint.sh`), **pyright** (CI).
No other frameworks/package managers without approval (`ui/` Node/React: ADR-0104;
Streamlit, shadow tool only: ADR-0192).

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
  `VulnerabilityCase` are the same class — ARCH-25-003 (ADR-0099) aliased all 27
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
  wrap**, and no line-length limit (MD013 is off in `docs/`). Do **not**
  reflow docs prose to a column width: it destroys the per-sentence diff SG-38
  exists to give, which is how a doubled-list-marker defect reached green CI in
  #3458. See `.claude/skills/shared/docs-style-guide.md`.
- **Everywhere else** (`notes/`, `specs/`, `plan/`, READMEs, docstrings): 88 chars
  max (exceptions: tables, code blocks, long URLs), enforced by `MD013` and a
  per-added-line guard (PD-10); break long sentences at natural points.
- **`notes/` informs work not yet done** — it is not a project history (NF-08).
  Every note declares `kind: guidance | plan | generated` (`plan` adds `tracks:`);
  write each item as rule + reason + one citation, never the backstory; update
  frontmatter when you edit a note (NF-06-001). Read
  `.agents/skills/shared/notes-writing-guide.md` before adding to any note.
- Use `markdownlint-cli2` for linting; see Miscellaneous tips for commands

### Logging Requirements

DEBUG (details), INFO (lifecycle/state transitions), WARNING (recoverable),
ERROR (failures), CRITICAL (system). Include `activity_id` and `actor_id`
when available. See `specs/structured-logging.yaml`.

---

> **Specification-Driven Development** and **Specification Usage Guidance** have
> moved to `specs/AGENTS.md`; **Testing Expectations** to `test/AGENTS.md`.

## Quick Reference

### Adding a New Message Type

See [`vultron/core/AGENTS.md`](vultron/core/AGENTS.md) for the full
six-step checklist (enum → pattern → use-case → map → tests).

### Key Files Map

- **Enums / MessageSemantics**: `vultron/core/models/events/base.py`
- **Dispatchers**: `vultron/core/dispatcher.py`, `vultron/core/trigger_dispatcher.py`
- **Inbox**: `vultron/adapters/driving/fastapi/routers/actors/` (package; `_routes/`
  defines endpoints)
- **Errors**: `vultron/errors.py`
- **Demo**: `vultron/demo/cli/` (entry point)
- **Case States**: `vultron/core/states/cs/` (CS/VFD/PXA enums, authoritative) and
  `cs_invariants/` (CSB-17) → legacy oracle (ADR-0060): [notes/case-state-model.md](notes/case-state-model.md)

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

For architectural changes, draft an ADR first from `docs/adr/_adr-template.md` (it
may be `proposed`; implement against it, ADR-0120). Use the decision-tree in
`notes/specs-vs-adrs.md` (MS-11-001 through MS-11-006) to decide ADR vs. spec
entry vs. both.

### Commit Workflow

**Before committing**, run skills in order:

1. `run-linters` — ruff (lint + format) and mypy pass; pyright is CI's
   (PAD-18-026/027). Supersedes `format-code`: run it alone.
2. `run-tests` — every local gate is linters plus `targeted-tests`, never the
   whole suite: the first push (PAD-18-001/008), a fix commit (PAD-18-002/003),
   a conflict merge (PAD-18-012/015). Read `exit:`. An overlap runs no local test
   (PAD-18-024). Every push runs `prepush-ci-mirror` last (PAD-18-021/023,
   ADR-0173). An implementation PR opens as a draft; `pr-ship` marks it ready
   once CI's run on its head passes (PAD-18-028/029).
3. `build-docs` if `docs/` modified; `check-docs-sync` runs regardless (PD-03-008)
4. `commit` skill — include Co-authored-by trailer

**PR body**: use `.agents/skills/shared/pr-body-guide.md` template. Put
`- Closes #N` at top, one per line.

**`append-history`**: stage the new entry file (`git add plan/history/`).
The monthly `README.md` under `plan/history/YYMM/` is gitignored — do not stage it.

Pre-commit hooks are fail-only. If a hook fails, run `run-linters` (ruff, mypy)
or `format-code` (ruff fixes + format), re-stage, then commit.

**Lint memoization**: mypy runs through `run-if-changed.sh`, which skips it when
its inputs are unchanged since the last success (a `... skipping` line is
expected, not an error); ruff is fast enough to run bare. See `run-linters`.

**After a PR merges** in a named worktree slot:
`bash "$HOME/.copilot/skills/manage-worktree/scripts/manage_worktree.sh" reset <slot-name>`

---

## Parallel Development (Worktree Slots)

Multiple agents use named git worktree **slots**. See
[`notes/parallel-development.md`](notes/parallel-development.md) and
`~/.copilot/skills/manage-worktree/SKILL.md`.

---

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
  **DEFER** → create follow-up issue + user ack; unattended runs have no DEFER
  (fix in the PR or hold it). Never merge on red; never skip a hook
  (only the documented `actionlint` hang).
  No WARN-and-defer.

---

## Common Pitfalls (Lessons Learned)

This is an **index**, not the write-ups. Find your symptom area below, read the
linked file before touching that area. New pitfalls MUST be routed per
[notes/agents-md-structure.md](notes/agents-md-structure.md): write-up in the nearest
`notes/` or per-directory `AGENTS.md`, then **extend a cell below — this file has a
400-line budget, so trim as you add, never append**.

### Where to look

| Symptom area | Read | Pitfalls covered |
|---|---|---|
| Wire/core boundary | [wire-core-boundary](notes/wire-core-boundary.md) | wire may import only `core/models`+`core/states` (ARCH-22-001 allow-list; ARCH-01-001 is the other direction); union validators raise `ValueError`; core `extra="forbid"`, no alias key beside its twin (ARCH-12-003); IRI branch is `NonEmptyString` → `strip_annotated()` (#3876); unknown inbound keys decided at the parse edge, `@id`/`@type` are near misses (MV-11, #3900) |
| Core needs camelCase | [core-wire-rendering-port](notes/core-wire-rendering-port.md) | `to_camel` inherited by every `CoreObject` (ADR-0099), but core never builds wire shape — delivery via `WireRenderPort` (ARCH-20-001, CLP-07-009/010); empty `by_alias` baseline; missing port is `VultronWiringError`, never a fallback (#3930) |
| Wire vs. core class names | [vocabulary-registry](notes/vocabulary-registry.md) | `as_` prefix (ARCH-14-001); `VOCABULARY` (class name) vs. `WIRE_TYPE_MAP` (derived `type` value) are disjoint (ARCH-23-002, VM-01-004/008); shared `type` → `_wire_type_alias` (VM-01-014); `find_in_vocabulary` is wire-only unless `include_core=True` (VM-06-013); needs a `Literal` `type_` to register (VM-03-002) |
| Domain object validation | [domain-validation](notes/domain-validation.md) | assignment/`append` bypass validation (CM-27-001); no `self` assignment in `mode="after"` (ARCH-21-004); silent `None` = fake `SUCCESS` (ARCH-15); `getattr` misses `ValueError`; `__init_subclass__` pitfalls; report every violation (EH-07-001); `participant_transition_violations()` only (BTND-10-002); `force_rm_state` is bootstrap-only (RMB-14-005); trigger admits only valid steps, receive any forward move, both refuse whole (Postel, RSH-09) |
| Behavior tree nodes | [bt-pitfalls](notes/bt-pitfalls.md) | write nodes validate own transitions (CSB-16); guarded commits as CASE_MANAGER (BT-17-005); store follows executing actor, but a received RM write is about the sender (RSH-08-001); don't clear keys you don't own; guards name the transition; a skip-if-done guard skips only what it encloses, reads before the write, and is read by node type, so one tree asks one question (#5006); **refusal arms fail toward admit** — decide and emit in one `RefusalActTransaction`, guards raise, key on the request; log via `node_logger(node)` (SL-01-005, [structured-logging](notes/structured-logging.md)); time is the act's instant (`_require_act_instant()`), never a clock read (ADR-0176, [act-instant](notes/act-instant.md)) |
| BT integration / concurrency | [bt-integration](notes/bt-integration.md), [bt-pitfalls](notes/bt-pitfalls.md) | module-level `RLock` under `BackgroundTasks`; trigger `execute()` delegates SM transitions (BT-15-001); `internal_error is False` ≠ "no bug" — node `except Exception` and nested `BTBridge` hops hide it; one tree per delivery, helpers count — compose, never chain (CLP-10-005, ADR-0135); one `has_role` question, in the path stage, picks the manager/replica/no-case path, declared once to the factory, and an undeclared path is refused there with a reason composed from the path and the declaration (HP-01-012, HP-01-039, ADR-0153); `resolve_case_manager_id` answers *who* (an id, ~70 legitimate callers), `has_role(…, CASE_MANAGER, …)` answers *is this actor* and is the boolean's only source for any actor — never a comparison of the resolver's id nor a role-list test (ARCH-24-008/009, #5921) |
| Case ledger | [case-ledger-authority](notes/case-ledger-authority.md), [ownership-transfer](notes/ownership-transfer.md) | not a process log (CLP-07); one role-gated commit, already injected by the factory (CLP-09-001); two timestamps — commit stamp vs. claimed `published`, monotonic per snapshot actor but reported, never refused (CLP-15-003/005); blank/missing `published` refused at parse (CLP-15-008); nested times carried as received (ADR-0103); every case-file change is its own entry, so one act may commit several; replicas copy, never mint ids, read clocks or run lifecycle logic (CLP-07-013/014, CM-23-016, CM-23-044, ADR-0124); a participant's `Reject` is a case event and is ledgered — the ledger verdict is *admitted*/*refused*, never accepted/rejected, and a no-entry handler needs a CLP-02-013 ground (CLP-02-012, CLP-02-016, CLP-09-006, #3748) |
| Who sends what to whom | [case-communication-model](notes/case-communication-model.md), [case-joining](notes/case-joining.md) | roster ≠ entitlement — recipients only via `core/participants/recipients/` (CM-10-004/005/007, ADR-0114, #4100); joiners answer the full-case Invite (CM-11-020); participants message only the CASE_MANAGER (PCR-08, ADR-0109); gated effects → `REFUSED` (BT-17-001, HP-01-005); the gate checks the receiver, never the sender — sender entitlement declared once per use case, composed by the factory (HP-01-006/007, ADR-0115); embargo proposals relayed (EP-09, ADR-0113); manager never unfilled (CM-02-014); the addressee door is in every received tree, opt out only via a registered `AddresseeExemption` (HP-01-005, #4832) |
| Pattern matching / semantics | [activitystreams-semantics](notes/activitystreams-semantics.md), [activitystreams-state-update](notes/activitystreams-state-update.md), [`vultron/wire/as2/AGENTS.md`](vultron/wire/as2/AGENTS.md) | patterns match the inbound wire format; `object_` strict by default — a bare id matches no object type (SE-01-006); `target_` lenient unless `strict=True` (SE-08); `Reject(Invite)` case in `inner_target` (CM-11-003); phrase placeholders (SE-07-005); no `origin_` field — examples must match exactly one pattern (#3438) |
| Persistence / stores | [datalayer-design](notes/datalayer-design.md) | `dl.read()` returns core objects (ADR-0034), no wire re-read for semantics (ADR-0035); actor id is a store name (DL-07-004); `_dehydrate_data` keeps inline snapshots; no model defaults a time — the author states the act's instant, a stored record without one is unsupported (#3732, #5758); a renamed stored field is dropped, never aliased — `forbid` refuses its old key, no list of old names (ADR-0175); writes that must land together share one `transaction()`, never a repair pass (ADR-0146) |
| Embargo / consent | [embargo-lifecycle](notes/embargo-lifecycle.md), [participant-embargo-consent](notes/participant-embargo-consent.md) | go through `EmbargoLifecycle`; EM is derived from the append-only `embargo_register`, its `CaseStatus.em` only a stamped copy (ADR-0122); consent is one row per (participant, register entry), starting `UNINVITED` (a missing row raises), created by `write_uninvited_rows`, answered only via `apply_pec_transition(embargo_id, …)`, copied from an entry only via `apply_embargo_change` (CM-18-005, CM-18-025, #4713), answers to a replaced, rejected, cancelled or ended embargo version can't change; a repeat of the same answer changes nothing, while a changed answer is recorded, an Accept after a Reject moving the row straight to `AGREED` (CM-13-005, CM-18-003); signatory and lapsed are reads of the rows, never writes (CM-18-016, ADR-0122); a revision Invite lands on the revision's own row (EP-09-004); termination cancels every proposal in the same register step and writes no consent (EP-08-004); default embargo once per case, keyed on EM ≠ `NONE` (EP-04-012; [embargo-default-semantics](notes/embargo-default-semantics.md), #3393, #4019) |
| Participant records | [participant-role-management](notes/participant-role-management.md) | RM mutation uses `actor_participant_index` (CM-19-003); RM terminal guard before same-state shortcut |
| Devcontainer / tooling | [devcontainer-tooling](notes/devcontainer-tooling.md) | always `uv run`; image exports no `PYTHONPATH`, rebuild if it's `/app` (#5571); `UV_NO_SYNC=1` on sync failure; ruff runs bare (IMPLTS-07-021); `pyright` is CI's, never a local gate's (PAD-18-027), and every other heavy local check takes a per-host slot via `run-heavy.py` (#5947); `SKIP=actionlint` (hangs), and `uvx --from actionlint-py actionlint` is the local lint a workflow change still needs (#5949); `git push -u origin HEAD`, HTTP/1.1 retry (#3893, #3905); edit `.agents/skills`, not the `.claude` symlink |
| Spec/notes/ADR/history tooling | [`vultron/metadata/AGENTS.md`](vultron/metadata/AGENTS.md), [agentic-workflow](notes/agentic-workflow.md) | learning filename slug ≠ `source` (BW-01-008, #1857); loaders name failing files `path:line:col` via `file_loading.py` (MS-17) — YAML errors aren't `ValueError`; pre-code spec needs `lint_suppress: [phantom_path_ref]` |
| git / branches / PRs | [git-workflow-pitfalls](notes/git-workflow-pitfalls.md) | false-positive rebase "local changes"; conflict-free ≠ working merge; integration branches for related fixes; re-check ADR numbers; verify ACs on `origin/main`, always `Closes #N`, prose ACs skip the pre-claim gate (#1907) |
| Issue themes / epic scope | [epic-themes](notes/epic-themes.md) | one `theme:` per leaf, judged from its own outcome, never copied from the parent; an Epic's children share its theme; `Theme: <label> — <outcome>` body line; labels come only from the catalog block via `theme-labels`, which never deletes; `theme-fit` reports every breach, read-only (PAD-02-014–021) |
| GH Actions / CI YAML | [ci-workflow-authoring](notes/ci-workflow-authoring.md) | red job ≠ assertions ran, all-skipped = green; `notify-failure` mandatory (CISEC-05); bare `on:` → `True`; matrix booleans job vs. step; `python3 -c` breaks `actionlint`; YAML apostrophes; artifact names carry `run_attempt`; GitHub writes via `retry.sh`, label swaps split (#4577, #4524); a `.sh` runs on the host's bash, which on macOS is 3.2 — no `mapfile`, no `declare -A` (#5698); the test job's parts stay one matrix job, and its last part is `test` minus the others' claims, never a fourth list (TB-11-002); a new `pull_request` check is seen only on its own pull request and later ones, so a ruleset waits on a verification task after the merge (#5971); a red gate's own log names each red check; the gate is required on `main` with no bypass actor, so a red or unjudged gate blocks every merge, admin included (#5945); the gate judges once per event, so its `types` cover every other pull-request workflow's (#6026); a capping `head` behind a pipe exits 141 under `pipefail` and kills its own step, and only a test that runs the script catches it (#6026); the gate passes on a skip, so a check CI takes over from a local gate needs an unfiltered `pull_request` job — `guard-tests.yml` (PAD-18-023/031) |
| Spec authoring | [spec-authoring-rules](notes/spec-authoring-rules.md) | strict `kind`/`priority`/`rel_type` enums, a link recorded at one end only (SR-13); `adr:` not `references:`; `kind: protocol` needs marker test or strict `xfail`; CASE_MANAGER not "CaseActor" (ADR-0088); item format = field presence, not `isinstance` (ADR-0101); advisories need an owner and a terminal state |
| Specs vs. ADRs, doc drift | [specs-vs-adrs](notes/specs-vs-adrs.md), [documentation-sweeps](notes/documentation-sweeps.md) | an ADR is a historical record — a refactor never obliges an ADR edit, an aged code reference in a body is not a defect and no scrub is owed, live constraints go to a spec or note citing it as provenance, and neither may dereference an ADR body (ADR-0127); ADR "what is removed" is scoped to one use; no counts in long-lived docs (MS-16-001); moving a claim ≠ verifying it, share by `include-markdown` fragment (DF-10-001/002) |
| Tests | [testing-pitfalls](notes/testing-pitfalls.md), [`test/AGENTS.md`](test/AGENTS.md) | killed run reads exit 0 under `tail -5`; in-process green ≠ Docker green for payloads and per-actor config (#4541); vacuous assertions; "falls back to" on malformed input asserts a bug; process-global blackboard/registries; `caplog` catches fixture setup; a timeout trip fails one test, the method not the ceiling (#3603), and a trip with no assertion in its traceback is another heavy run's memory (#3156); a dead xdist worker fails the run and gate exit 124 is a hang (#4809); directory-hook markers checked over real collection (#3604); a two-sided count pin races concurrent PRs, keep a per-item record (#3984); nesting turned into sequence moves the skip only a test of the new caller reaches (#5533, #5534); a ratchet keyed on an implementation name loses subjects to a rename and its non-empty guard still passes (#5535, [architecture-ratchet-corpus](notes/architecture-ratchet-corpus.md)); a guard reached only by direct call covers nothing, and a caller that omits the gating argument leaves it dead (#3156); a test spawning children sizes them from the cgroup, not `os.cpu_count()`, and an `xdist_group` never bounds a sibling worker (#5184); a child writes its ready marker only once the signal it awaits kills it — bash and Python handlers drop one (#6223); a harness red for the environment hides real failures — skip on the filesystem's refusal, not on `sys.platform` (#5449, #5698); CI runs the suite as four partitioned sessions, so no test may assert over the whole collection (TB-11-002); read a signature via `signature_of`, never bare `inspect.signature` — PEP 649 makes it raise on `TYPE_CHECKING` names (#6054) |
| Demo scenarios | [`vultron/demo/AGENTS.md`](vultron/demo/AGENTS.md), [demo-scenario-authoring](notes/demo-scenario-authoring.md), [demo-scenario-registry](notes/demo-scenario-registry.md) | puppeteer via triggers, never inbox injection (DEMOMA-00-002); gate steps on their cause (EDF-06, ADR-0058); protocol activity lives in `helpers/workflow/` ([demo-ci-diagnostics](notes/demo-ci-diagnostics.md)); declare a scenario once with `@scenario`, all inventories generated, no `@main.command`, unbuilt ones go in `demo-future-ideas.md` (ADR-0098, DEMOCI-11); every proposal goes to `http://case-actor:7999/api/v2/actors/case-actor`, whose container holds the canonical case and ledger and is re-seeded by the reset — read and act on its store through that container's client, never a participant's replica ([case-proposal](notes/case-proposal.md) § dedicated container, #1876); two milestones in a row assert two different things, each label describing only its own block, and the holding test compares the halves' reads *each way* — a half whose reads are a subset of the other's adds nothing (#5602) |
| Inbox / outbox | [inbox-orchestration](notes/inbox-orchestration.md), [inbox-pipeline](notes/inbox-pipeline.md), [outbox-delivery-reliability](notes/outbox-delivery-reliability.md), [`vultron/adapters/AGENTS.md`](vultron/adapters/AGENTS.md) | inbox policy in `core/behaviors/inbox/`, `process_payload` sole entry (IO-02-001/003); catch a new raise below the retry loop; retry caps composing to `4 × ∞` (OX-13); inbox has no read surface (IE-02-003/004, #3141); outbox relays the sealed body, never a re-read (OX-07-001, OX-07-004, VM-08-003); a sent act commits after its outbox write, so a rebuildable send needs a derived id (SYNC-09-002, OX-06-002); the outcome stage decorates `DispatchNode` and maps the verdict onto what is kept — applied is archived, a refusal (an unhandled type too) leaves a bodiless receipt stub, no verdict leaves the record in holding (CLP-10-018/073/074); a resend is answered by the seen-before door from that record, never re-run (ADR-0154) |
| Call-out points | [call-out-configuration](notes/call-out-configuration.md) | automation potential ≠ call-out shape (ADR-0024); an externally-versioned capability is **one** call-out unit (BTND-05-007) |

### Cross-cutting rules with no other home

- **Module splits** (no god modules, re-export moved names, importer proof before
  deleting), small coding habits, Protocol sync (CS-20), `HashChainLedgerRecord`
  ≠ `CaseLedgerEntry`: [notes/codebase-structure.md](notes/codebase-structure.md).
- **BT/use-case**: no DataLayer writes in `execute()`, even via a helper (CLP-10-020,
  `test_no_dl_mutations_in_execute.py`); received trees run doors → intake →
  guards → commit → effects, ledger commits only via `CommitCaseLedgerEntryNode`
  (CLP-10-006/010/019, BT-06-006, ADR-0154) — [notes/bt-integration.md](notes/bt-integration.md);
  emit nodes fail fast without a CASE_MANAGER recipient (PCR-08-011), broadcasts
  never mask delivery failure (BT-14-001) — [notes/bt-pitfalls.md](notes/bt-pitfalls.md).
- **Adapters/ports**: stubs raise `NotImplementedError` (OX-10-004, OX-11-004),
  transport-role names stay explicit —
  [notes/architecture-adapters.md](notes/architecture-adapters.md); idempotency chain
  [`vultron/core/AGENTS.md`](vultron/core/AGENTS.md); no `BaseModel` in ports
  [`vultron/core/ports/AGENTS.md`](vultron/core/ports/AGENTS.md).
- **Logging**: level refactors need a grep pass; self-healing never at ERROR; an arm a
  sibling can overrule at DEBUG — [structured-logging](notes/structured-logging.md).
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

Ask the user anything per
[`.agents/skills/shared/asking-the-user.md`](.agents/skills/shared/asking-the-user.md),
in every session and when skills compose (`learn` → `grill-me`). The core rules: one
question at a time; problem before decision, with your recommendation; ask about the
behavior behind a spec rule, not its wording; plain language with every cited ID
summarized; and run the guide's pre-ask check first.

---

## Governance note for agents

Agents MAY update `AGENTS.md` to correct/clarify rules, but substantive changes
SHOULD be discussed via Issue or PR. Include rationale in the commit message.

---

## Miscellaneous tips

- Use `markdownlint-cli2` for markdown; `ruff format` skips it. Default config
  ignores vendor trees, `wip_notes/**`, `**/.claude/worktrees/**` and
  `**/plan/history/**` (HM-01-005, #2952, #6232).
- **Docs links must be relative** and MUST NOT go above `docs/`. Run
  the `build-docs` skill before committing docs. `docs/developer/` pages
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

Issues live in GitHub Issues. Full rules and CLI patterns:
[notes/parallel-development.md](notes/parallel-development.md)
§ "GitHub Issue Tracker". Non-negotiables:

- **Create issues only through the `create-issue` skill** — never `gh issue
  create` or a raw `createIssue`. Its script refuses an issue without one
  `theme:`, a `Theme:` line, and a same-theme parent (PAD-02-022).
- **Epics are the `Epic` issue type, not a label** — detect by
  `issueType.name == "Epic"`, not a label query; create with the `create-epic`
  skill.
- **Never pass backtick markdown in a double-quoted `--body`** — use a
  single-quoted heredoc.

### Triage labels

`needs-info` (the only hold), `ready-for-human` (agents skip it); see
[notes/epic-themes.md](notes/epic-themes.md) § "Triage Labels" (#3717).

### Domain docs

Single-context repo: one `CONTEXT.md` + `docs/adr/` at root; if absent, proceed
silently, never propose creating them (`domain-modeling` does, lazily). Use glossary
terms (a missing one is a gap, not a licence to invent); flag ADR contradictions.
