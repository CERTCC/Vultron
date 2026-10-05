---
stakeholder_type: [project-contributor]
---

# Codebase Structure

## Core Sections (Required)

### 1) Top-Level Map

| Path | Purpose | Evidence |
|------|---------|----------|
| `vultron/` | Main Python package — all production source | `pyproject.toml` `[tool.setuptools.packages.find]` |
| `vultron/core/` | Domain layer: models, ports, use cases, states, behaviors, services, predicates, participants, scoring, case-state hypercube, and the two dispatchers (`dispatcher.py` for received activities, `trigger_dispatcher.py` for trigger verbs) | `vultron/core/AGENTS.md` |
| `vultron/wire/` | Wire format layer: AS2 vocabulary, parser, unknown-key disposition, rehydration, semantic extractor, factories | `vultron/wire/as2/AGENTS.md` |
| `vultron/adapters/` | Adapter layer: driving (FastAPI HTTP, CLI, shared-inbox stub), driven (SQLite, delivery, trigger-activity adapter, wire render), connectors, outbox dead-letter and sealed-body helpers | `vultron/adapters/AGENTS.md` |
| `vultron/semantic_registry/` | Ordered ActivityStreams pattern registry and `use_case_map()` for received activities | `vultron/semantic_registry/__init__.py` |
| `vultron/trigger_registry/` | Verb-keyed `TRIGGER_REGISTRY` table for trigger use cases, one sub-module per domain (ADR-0110); a data table for enumeration, not a router | `vultron/trigger_registry/__init__.py` |
| `vultron/bt/` | Original behavior tree simulator (read-only reference for the protocol BTs; backs the `vultrabot*` CLIs); production BTs live in `vultron/core/behaviors/` | `notes/bt-composability.md`, `vultron/bt/base/bt_node.py` |
| `vultron/config/` | Layer-neutral configuration models and loading logic | `vultron/config/app.py`, `vultron/config/actor.py`, `vultron/config/ledger.py` |
| `vultron/enums/` | Shared CVD-domain enums (roles, object types) imported by config and core | `vultron/enums/roles.py`, `vultron/enums/object_types.py` |
| `vultron/errors.py`, `vultron/primitives.py`, `vultron/logging_setup.py` | Shared exception hierarchy, shared type aliases (`NonEmptyString`), logging configuration | `vultron/errors.py`, `vultron/primitives.py` |
| `vultron/demo/` | Demo CLI, scenario registry, multi-actor scenarios (`scenario/`), single-exchange demos (`exchange/`), shared helpers (`helpers/`), stochastic fuzzers (`fuzzer/`) | `vultron/demo/AGENTS.md`, `vultron/demo/cli.py` |
| `vultron/metadata/` | Project tooling: spec registry, history CLI, notes and ADR metadata, docs-site validators, demo-scenario sync, JSON-LD context generation (`wire_context/`), planning helpers (`planning/`), message-semantics mapping renderer; `file_loading.py` attributes every loader failure to its file (MS-17) | `vultron/metadata/AGENTS.md`, `vultron/metadata/file_loading.py` |
| `test/` | Pytest test suite (mirrors `vultron/` layout) | `pyproject.toml` `[tool.pytest.ini_options]` |
| `test/architecture/` | Architecture-boundary and ratchet tests | `test/architecture/test_core_no_adapter_imports.py` |
| `specs/` | Structured YAML specification files | `specs/README.md` |
| `notes/` | Durable design insight Markdown files | `notes/README.md` |
| `archived_notes/` | Superseded design notes kept for reference | `archived_notes/README.md` |
| `docs/` | MkDocs documentation source | `mkdocs.yml` |
| `doc/examples/` | Committed JSON examples of the activity vocabulary | `doc/README.md` |
| `ontology/` | RDF/OWL Turtle ontologies for AS2 and the Vultron protocol | `ontology/vultron_protocol.ttl` |
| `plan/` | Agent workflow files: incoming learnings queue and history archive | `plan/history/`, `plan/incoming/` |
| `scripts/` | One-shot maintenance scripts (spec relabelling, story backfill, velocity report) | `scripts/velocity.py`, `scripts/relabel_spec_kinds.py` |
| `prompts/` | Standalone agent prompt files | `prompts/ARCHITECTURE_REVIEW_prompt.md` |
| `.agents/skills/` | Agent skills; `.claude/skills` is a symlink to it | `AGENTS.md` |
| `.github/workflows/`, `.github/actions/` | CI/CD pipeline definitions and composite actions | `.github/workflows/python-app.yml`, `.github/actions/setup-python-uv/action.yml` |
| `.githooks/` | Repository git hooks (pre-commit, post-commit, post-checkout) | `.githooks/pre-commit` |
| `.devcontainer/` | Dev container configuration | `.devcontainer/Dockerfile` |
| `docker/` | Containerized multi-actor demo (Dockerfile, two compose files, seed configs, entrypoint) | `docker/docker-compose-multi-actor.yml` |
| `integration_tests/demo/` | Shell drivers for the Docker-based demo integration runs, invoked by the `Makefile` `integration-test*` targets; not a pytest suite | `integration_tests/README.md`, `integration_tests/demo/run_multi_actor_integration_test.sh` |
| `overrides/` | MkDocs Material theme overrides | `overrides/partials/copyright.html` |
| `help/` | Declared as a `uv` workspace member, but no `help/` directory exists in the tree | `pyproject.toml` `[tool.uv.workspace]` |

### 2) Entry Points

- **Main ASGI app** (uvicorn/production): `vultron.adapters.driving.fastapi.main:app`, which mounts the API sub-app at `/api/v2`.
- **Sub-app for dev/tests**: `vultron.adapters.driving.fastapi.app:app_v2`
- **CLI scripts** (`[project.scripts]` in `pyproject.toml`):
  - `vultron-demo` → `vultron.demo.cli:main`; its scenario sub-commands are built from the scenario registry at import time.
    `vultron-demo-report` → `vultron.demo.report:main`
  - `vultrabot` / `vultrabot_cvd` → `vultron.bt.base.demo.cvd:main`; `vultrabot_pacman` → `...demo.pacman:main`; `vultrabot_robot` → `...demo.robot:main`
  - `spec-dump` / `spec-dump-llm-json` → `vultron.metadata.specs.render:main_llm_json`
  - `spec-lint` → `vultron.metadata.specs.lint:main`.
    Hard errors exit 1, and that includes the MS-12 kind tree (`vultron/metadata/specs/kind_classification.py`).
    An unverified `MUST`/`MUST_NOT` requirement without its own `verification_debt` marker is a hard error.
    The marked ones are printed as one line per kind, `--list-unverified` names the IDs, and `--check-debt-owners` checks that each owner issue is open.
  - `spec-coverage` → `vultron.metadata.specs.coverage:main`
  - `spec-backstop` → `vultron.metadata.specs.backstop:main` (spec groups governing the changed code, checked against a Spec manifest)
  - `glossary-index` → `vultron.metadata.docs.glossary_index:main` (term index of `docs/reference/glossary.md`)
  - `adr-index` → `vultron.metadata.adr.index_gen:main`
  - `docs-frontmatter` → `vultron.metadata.docs.page_frontmatter:main`.
    It validates the `stakeholder_type` and `level` every `docs/` page declares (DF-11-001), skipping include fragments.
    It also fails a working-record page that is in the nav or matched by no `not_in_nav` pattern (DF-11-003).
  - `docs-level-order` → `vultron.metadata.docs.level_order:main`.
    It fails when a `docs/` page uses a glossary term that a higher-level page declares in `introduces:`, unless the page links that introducing page at or before the first use or the use itself links to the glossary (DF-11-002).
    Working-record pages and pages with no level are skipped, and include fragments are checked at their lowest host's level.
    Pre-existing violations sit in a shrink-only baseline, pinned by key in its test, where each entry names a reason; `--prune-baseline` drops entries that are no longer violations.
  - `docs-site` → `vultron.metadata.docs.site_sync:main`.
    `--write` regenerates the contents listing of each section landing page whose `index.md` declares `contents: generated`, at any nav depth, from the `mkdocs.yml` nav and each listed page's `description:` frontmatter.
    It also checks that a `contents: routing` index links every member of its section, directly or through a fragment it includes uncut (DF-11-005), and regenerates `docs/includes/stakeholder_types.md` from the page schema (DF-11-011) and `notes/site-coverage-matrix.md` (DF-11-008).
    `--check` fails if any committed copy is stale.
  - `docs-withheld` → `vultron.metadata.docs.withheld:main` (a withheld artifact produces no `site/` files), `docs-links` → `vultron.metadata.docs.links:main` (every internal reference in the built `site/` resolves), `docs-legacy-urls` → `vultron.metadata.docs.legacy_urls:main` (a URL the site once published still answers)
  - `demo-scenarios` → `vultron.metadata.demo_scenarios.sync:main`.
    `--write` regenerates the artifacts derived from the demo scenario registry.
    `--check` verifies those, and also the consumers that are checked rather than generated: the `mkdocs.yml` nav, the `notes/` scenario tables (including their event-type columns, resolved from the invariant-harness constants), the `DEMOCI-06-002`/`-003` spec enumerations, and the register of scenarios that are specified but not yet built.
    It also rejects a restated scenario count and a stray `include-markdown` directive.
  - `wire-context` → `vultron.metadata.wire_context.sync:main` (generates the normative JSON-LD `@context` from the wire vocabulary, VM-10-001)
  - `bundle-fit` → `vultron.metadata.planning.bundle_fit:main` (two-stage issue-bundle selection for the `propose-bundle` skill); `pr-size` → `vultron.metadata.planning.size_bands:main` (the `size:` label band table)
  - `learnings-index` → `vultron.metadata.history.incoming:main` (validates and indexes `plan/incoming/learnings/`)
  - `append-history` → `vultron.metadata.history.cli:main`; `show-history` → `vultron.metadata.history.show_history_cli:main`; `backfill-implementation-history` → `vultron.metadata.history.backfill_implementation:main`
- **How entry is selected**: via `[project.scripts]` in `pyproject.toml`; uvicorn deployment (`docker/Dockerfile`) uses `vultron.adapters.driving.fastapi.main:app`.
  The `Makefile` `api_dev` target still names `vultron.api:app`, which does not exist (see `CONCERNS.md`).

### 3) Module Boundaries

| Boundary | What belongs here | What must not be here |
|----------|-------------------|------------------------|
| `vultron/core/` | Domain models, ports (Protocol classes), use cases, states, behaviors, services, predicates | FastAPI, wire-format (AS2), adapter or demo imports |
| `vultron/core/predicates/` | Pure predicate functions over domain values (role checks, embargo eligibility, state invariants) | I/O, DataLayer, `behaviors/`, `services/`, `ports/` imports |
| `vultron/core/participants/` | Neutral participant-layer helpers below both `behaviors/` and `use_cases/`; resolves role-based authority (ADR-0088) | `behaviors/`, `use_cases/`, adapter imports |
| `vultron/core/behaviors/` | py_trees trees and nodes, run through `BTBridge` | `use_cases/` imports |
| `vultron/wire/as2/` | AS2 vocabulary (Pydantic models), parser, semantic extractor, factories | Any `vultron/core/` package other than `models/` and `states/`; FastAPI |
| `vultron/trigger_registry/` | One `TriggerEntry` row per trigger verb | Per-verb behavior (ADR-0110) |
| `vultron/adapters/` | HTTP handlers, SQLite data layer, outbound delivery, CLI, connectors | Core domain logic (no business rules) |
| `vultron/config/` | Configuration models and loading only | Imports from `vultron.adapters` or `vultron.core` |
| `vultron/enums/` | Shared CVD enums usable by `config/` and `core/` | Adapter or wire-specific types |
| `vultron/demo/` | Demo scenarios driven through HTTP triggers | `vultron/bt/` imports (sole permitted exception: `vultron/demo/cli.py`, DC-01-001) |

Enforced by: `test/architecture/test_core_no_adapter_imports.py`, `test/architecture/test_core_no_wire_imports.py`, `test/architecture/test_core_no_demo_imports.py`, `test/architecture/test_wire_core_import_allowlist.py`, `test/architecture/test_behaviors_no_use_case_imports.py`, `test/architecture/test_enums_import_graph.py`, `test/architecture/test_demo_no_bt_imports.py`, `test/architecture/test_trigger_registry_ratchets.py`

### 4) Naming and Organization Rules

- **File naming**: `snake_case.py` for modules (e.g., `bt_node.py`, `receive_activity_tree.py`); leading `_` marks package-private modules (e.g., `_routes.py`, `_entry.py`)
- **Class naming**: `PascalCase`.
  The `as_` prefix marks a wire class only for unpaired AS2 vocabulary (e.g., `as_Activity`, `as_Link`); for the paired domain types, `as_VulnerabilityCase` and `VulnerabilityCase` are the same class (ADR-0099, ARCH-14-001).
- **Domain abbreviation**: `vul` (not `vuln`) for vulnerability; `em` for embargo management; `rm` for report management; `cs` for case state
- **Role enum**: `CvdRole.OBSERVER` (alias `O`, formerly `OTHER`) identifies monitoring participants, in `vultron/enums/roles.py` and `vultron/bt/roles/enums.py`
- **Use-case naming**: trigger use cases are `Svc` + verb + noun + `UseCase` (e.g., `SvcCloseCaseUseCase`, `SvcEngageCaseUseCase`); received-message use cases end in `ReceivedUseCase` (e.g., `CreateReportReceivedUseCase`); see `vultron/core/AGENTS.md`
- **Directory organization**: by architectural layer (`core/`, `wire/`, `adapters/`) then by CVD domain area within layers
- **Import conventions**: absolute `vultron.*` imports dominate; relative imports appear in some package `__init__.py` files and in the `datalayer_sqlite/` and `trigger_activity_adapter/` subpackages.
  Core must not import from adapters or wire, and split modules re-export from `__init__.py` (CS-18-003).

### 5) Notable New Modules (2026-09 to 2026-10)

| Module | Purpose |
|--------|---------|
| `vultron/trigger_registry/` | `TRIGGER_REGISTRY`, the verb-keyed table that every trigger route, the dispatcher and the ratchets read (ADR-0110) |
| `vultron/core/ports/trigger_dispatcher.py` + `vultron/core/trigger_dispatcher.py` | One-method `TriggerDispatcher` port and its `RegistryTriggerDispatcher` implementation; replaced the deleted `TriggerService` facade |
| `vultron/adapters/driving/fastapi/trigger_runner.py` | `run_trigger()`, the single call every trigger route makes; it schedules a drain of the emitting actor's outbox after the use case returns |
| `vultron/core/use_cases/triggers/request_bodies.py` | Trigger request-body models; the core `*TriggerRequest` models derive from them and add `actor_id` |
| `vultron/core/behaviors/case/receive_activity_tree.py` + `nodes/intake.py` | Four-stage received-side tree factory (intake → guards → commit → effects) and the intake node that archives every received activity (ADR-0111) |
| `vultron/core/models/received_activity_record.py` | The receiver's archive record for one received activity (CLP-10-017) |
| `vultron/core/behaviors/embargo/nodes/relay.py` | The CASE_MANAGER relays an adjudicated embargo proposal as Invites to the other participants (ADR-0113) |
| `vultron/core/services/embargo_lifecycle/` | `EmbargoLifecycle` split into a per-responsibility package (activation, answers, consent, PEC, proposals) |
| `vultron/adapters/driving/fastapi/outbox_lanes.py` | Per-recipient ordered delivery lanes for one actor's outbox (ADR-0112) |
| `vultron/adapters/outbox_sealed_body.py` | Seals the outbound activity JSON at emission so delivery relays it byte for byte (VM-08-003) |
| `vultron/wire/as2/unknown_keys.py` | Inbound unknown-key disposition at the parse edge (MV-11) |
| `vultron/metadata/specs/kind_classification.py`, `vultron/metadata/specs/yaml_items.py` | MS-12 kind-tree enforcement for `spec-lint`, and the spec-YAML item slicer shared by `scripts/` |
| `vultron/demo/exchange/report_with_embargo_demo.py` + `vultron/demo/helpers/embargo_outcome.py` | Exchange demo where the Reporter proposes embargo terms with the report, and its creation-time embargo checks |

### 6) Evidence

- `vultron/` directory listing
- `pyproject.toml` `[project.scripts]`, `[tool.uv.workspace]`
- `vultron/core/AGENTS.md`
- `vultron/trigger_registry/__init__.py`
- `notes/architecture-hexagonal.md`
- `notes/bt-composability.md`
- `AGENTS.md`
- `Makefile`
- `test/architecture/test_core_no_adapter_imports.py`
- `test/architecture/test_wire_core_import_allowlist.py`
