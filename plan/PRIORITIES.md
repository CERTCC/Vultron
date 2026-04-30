# Priorities

## Important note about priority numbers

Priority numbers are ascending, so lower numbers are higher priority.
The scale is not linear, it's just intended to provide a rough ordering and
allow for space between to add new priorities in the future if needed. The
priority numbers themselves do not have any inherent meaning beyond their
relative order. Completed priorities should be archived via `uv run append-history priority`
(writes to `plan/history/YYMM/priority/`) and then removed from this file to keep
`plan/PRIORITIES.md` focused on pending and in-progress work.

## Priority 472: Docs Batch — LaTeX Fixes and Versioning Updates

A batch of small, independent documentation fixes tracked under parent issue
[#404](https://github.com/CERTCC/Vultron/issues/404).

Also carried in this top priority block:

- [#386](https://github.com/CERTCC/Vultron/issues/386) — Remaining open
  Priority 471 follow-up: defer unresolved `Accept.object_` references instead
  of immediately storing dead-letter records

Sub-issues:

- [#154](https://github.com/CERTCC/Vultron/issues/154) — Update versioning background to reflect CalVer adoption (remove semver references)
- [#186](https://github.com/CERTCC/Vultron/issues/186) — SSVC crosswalk has some unrendered LaTeX
- [#234](https://github.com/CERTCC/Vultron/issues/234) — Unrendered LaTeX in Formal Vultron Protocol Redux
- [#235](https://github.com/CERTCC/Vultron/issues/235) — Unrendered LaTeX in Transitions
- [#271](https://github.com/CERTCC/Vultron/issues/271) — SSVC Crosswalk page has broken LaTeX

These are all self-contained doc fixes that can be resolved in a single
focused pass. Higher priority than a full docs refactor or platform migration
([#294](https://github.com/CERTCC/Vultron/issues/294)) but lower than
active code bugs.

## Priority 473: Architecture Hardening

RFC-level improvements that deepen module design, reduce coupling, and
improve testability. Tracked under parent issue
[#405](https://github.com/CERTCC/Vultron/issues/405).

Sub-issues:

- [#400](https://github.com/CERTCC/Vultron/issues/400) — RFC: Deepen the trigger path — replace 4-layer shallow stack with TriggerService + TriggerServicePort
- [#401](https://github.com/CERTCC/Vultron/issues/401) — RFC: Deep-module BT test harness — replace duplicated setup_node_blackboard boilerplate with BTTestScenario
- [#402](https://github.com/CERTCC/Vultron/issues/402) — RFC: Consolidate extractor.py — move find_matching_semantics to semantic_registry
- [#403](https://github.com/CERTCC/Vultron/issues/403) — RFC: Narrow the DataLayer port — introduce CasePersistence and CaseOutboxPersistence

Resolving these before cyclomatic complexity reduction (Priority 480) enables
cleaner refactors: narrower interfaces and deeper modules reduce CC
organically.

Additional implementation-level architecture tasks (no GitHub issues yet):

- **TASK-AF** — Activity Factory Functions: introduce
  `vultron/wire/as2/factories/` as the sole public construction API for
  outbound Vultron protocol activities; migrate all call sites; make internal
  vocab subclasses private.
- **TASK-ARCHVIO** — Fix ARCH-03-001 violations: core use cases in `sync.py`
  call `from_core()` on wire objects, violating the hexagonal constraint.
  Introduce a driven port adapter for domain→wire translation. Depends on
  TASK-AF.
- **TASK-BTND5** — Generalize Participant BT Nodes: replace
  `CreateInitialVendorParticipant` with a config-driven
  `CreateCaseOwnerParticipant`; add `CVDRoles.CASE_OWNER`; remove the
  `CreateFinderParticipantNode` alias; refactor `CVDRoles` from `Flag` to
  `StrEnum`.
- **TASK-DL-REHYDRATE** — DataLayer auto-rehydration residual: add a typed
  `list(type_key)` method to the `DataLayer` Protocol and SQLite adapter;
  remove manual `model_validate()` coercions from use cases.

## Priority 474: Unified Configuration and Trigger Classification

Introduce a single unified configuration API and formally separate demo-only
trigger endpoints from general-purpose ones. No GitHub issues yet.

- **TASK-CFG**: Introduce `vultron/config.py` with `AppConfig`,
  `ServerConfig`, `DatabaseConfig`, `RunMode(StrEnum)`, `get_config()`, and
  `reload_config()`. Replace all `os.environ.get()` calls; refactor
  `SeedConfig`/`LocalActorConfig` to `pydantic-settings`.
- **TASK-TRIGCLASS**: Separate demo-only triggers (`add-note-to-case`,
  `sync-log-entry`) into a dedicated router mounted only when
  `RunMode.PROTOTYPE`; add a general-purpose `add-object-to-case` trigger.
  Blocked by TASK-CFG.

## Priority 475: Outbox Integrity Enforcement

All outbound Vultron activities are direct messages and MUST have a non-empty
`to:` field. Enforce this at `handle_outbox_item` so no activity leaves the
outbox without an addressee. No GitHub issue yet.

- **TASK-OUTBOX-TO**: Add `VultronOutboxToFieldMissingError` and enforce
  `to:` presence in `handle_outbox_item`; log `WARNING` when `cc`/`bto`/`bcc`
  are non-empty.

## Priority 480: Cyclomatic Complexity Enforcement

Cyclomatic complexity (CC) is treated as a policy boundary, not just a
measurement. High CC correlates with harder-to-test, harder-to-maintain
code and is a leading indicator of defects.

The project currently has 23 functions exceeding CC=10, including one at
CC=34. `flake8-mccabe` (already bundled in the project's flake8 7.3.0
install) provides the enforcement mechanism with zero new dependencies.
The gate integrates into the existing `lint-flake8` CI job.

Enforcement is two-phase to avoid a big-bang refactor:

- **Phase 1** (CC-1): Reduce the 5 worst offenders (CC>15) to CC≤10, then
  activate a `max-complexity = 15` gate in `.flake8`. This immediately
  blocks future regressions at a reachable bar.
- **Phase 2** (CC-2): Reduce the remaining 18 functions (CC 11–15) to
  CC≤10, then tighten the gate to `max-complexity = 10` — the generally
  accepted upper bound for maintainable functions.

Each refactoring task explicitly targets CC≤10 (the final goal) so no
function needs to be revisited when the threshold drops in Phase 2.

See `plan/IMPLEMENTATION_PLAN.md` `TASK-CC` for the task breakdown (CC.1 and
CC.2), and `plan/BUILD_LEARNINGS.md` CC-ENFORCEMENT for the full
violation inventory, per-function refactoring notes, and configuration details.

## Priority 500: Re-implement "fuzzer" nodes from the original simulator

As we originally built out the `py_trees` implementation, we replaced
certain fuzzer nodes from the simulator (`vultron/bt`) with deterministic nodes
that simply
return success. While this initially allowed us to focus on the core
behavior tree logic, it also means that we are not able to demonstrate the
full range of behaviors that the Vultron Protocol is designed to support.
Re-implementing these nodes with more realistic behavior will be important for showcasing the
capabilities of the system and for moving towards a production-ready implementation.
The "fuzzer" implementation in the simulator worked well enough, so there is
not much need to change the overall design, but we will need to reimplement
it in the new codebase using `py_trees` as the foundation. The underlying
`vultron/bt/base/fuzzer.py` module (and all the other `fuzzer.py` modules in
`vultron/bt/`) can be used as a structural reference for the new implementation.

## Priority 1000: Agentic AI readiness

We are going to want to allow for the possibility of agentic AI integration
into the vultron coordination process in the future. How this will happen is
still an open question. One possibility we can imagine coordination agents
that behave as ActivityPub Actors and participate in cases as CaseParticipants alongside
humans.

A more likely scenario is that we want to support agentic AI agents
interacting with cases as well on the
backend (i.e., not as ActivityPub Actors, but as API or command
line clients.) We may have local agents that interact directly with
the behavior trees or other internal system components via MCP. This would
be an adapter that parallels the API and CLI adapters in the hexagonal
architecture. These agents would not be ActivityPub Actors and would not
directly participate in cases, but would instead be more like assistants to human participants
who are directing them to perform specific tasks.

`AR-09-001` through `AR-09-004` and similar tasks will fall here.

We will need to design the system in a way that allows for either of these
possibilities to be implemented in the future without requiring major refactoring.

## Priority 2000: Upgrade former "fuzzer" nodes to full implementations

See `notes/bt-fuzzer-nodes.md` for details on a set of fuzzer nodes that
were implemented as placeholders in the original simulator, but that
represent external touchpoints for the real process. Some of these nodes can
be fully automated, others will require outside judgment, human input, or
manual work. They might rely on external tools or services that we will need
to integrate with. Implementing these nodes will be important for moving
from a prototype to a production-ready system, but they also represent a
number of decisions and implementation work that is not core to being able
to demonstrate the core behavior tree and coordination logic.

## Priority 3000: Miscellaneous tasks

BT-2.2, BT-2.3

## Priority 50000: Full RAFT consensus implementation

SYNC-4 enables RAFT consensus for the CaseActor process. Before we get here
we will need to establish how we want to handle the CaseActor scaling and
failover process.

## Priority 95000: Documentation Enhancements — Crosswalks and Framework Integration

Low-priority documentation work to expand coverage of related frameworks
and scoring systems. These will be addressed as part of a broader
documentation refresh, after higher-priority code and architecture work is
complete.

- [#5](https://github.com/CERTCC/Vultron/issues/5) — Integrate FIRST services frameworks
- [#6](https://github.com/CERTCC/Vultron/issues/6) — Add CVSSv4 crosswalk

## Priority 99999: Remaining Requirements and Documentation Updates

The project is currently in prototype development mode, therefore requirements
that are marked as `PROD_ONLY` are temporarily a lower priority than other
requirements. See `specs/prototype-shortcuts.yaml` for the prototype-stage
deferral policy.

USE-CASE-01
USE-CASE-02
EP-02
EP-03
AR-04
AR-05
AR-06
AGENTIC-00
FUZZ-00
