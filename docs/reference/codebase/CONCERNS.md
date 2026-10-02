---
stakeholder_type: [project-contributor]
---

# Codebase Concerns

## Core Sections (Required)

### 1) Top Risks (Prioritized)

| Severity | Concern | Evidence | Impact | Suggested action |
|----------|---------|----------|--------|------------------|
| High | SQLite not suitable for multi-node/concurrent writes | `vultron/adapters/driven/datalayer_sqlite/` | Prototype-only scalability ceiling; federation requires a distributed or replicated store | Define a migration plan to PostgreSQL or equivalent before production deployment |
| High | No inbound authentication on the inbox endpoint | `vultron/adapters/driving/fastapi/routers/actors/_routes.py`, `vultron/adapters/driving/shared_inbox.py` (stub) | Any network peer can post activities as any actor | See §3 Security Concerns |
| Medium | Many production modules exceed the CS-18-001 500-line threshold, including core files | `git ls-files 'vultron/*.py' \| xargs wc -l \| sort -rn`; largest in core: `vultron/core/behaviors/helpers.py`, `vultron/core/use_cases/received/embargo.py`, `vultron/core/behaviors/bridge.py`, `vultron/core/case_states/hypercube.py`; largest overall are demo files (`vultron/demo/helpers/polling.py`, `vultron/demo/scenario/fvcv_handoff_demo.py`) | Large mixed-responsibility modules are where merge conflicts and missed edits concentrate | Split per CS-18-001/002; #3952 tracks `vultron/metadata/specs/lint.py`; [ASK USER] whether the remaining oversized modules should be filed as split issues |
| Medium | Inline lint suppressions baselined in production code | `# ruff-baseline #NNNN` markers in `vultron/` (find with `git grep "ruff-baseline" -- vultron/`), owned by #3353 (exception-handling rules), #3768 (BT node broad catches), #3326 (broad `except Exception`), #3985 (module-level `global`) | Broad catches can turn internal errors into refusals (#3768); each marker is a known deviation from CS-23-001 | Drain each issue's markers; RUF100 keeps a removed finding's stale marker from lingering |
| Medium | No test coverage measurement | `pyproject.toml` `[dependency-groups].dev` (no `pytest-cov`) | Coverage gaps are invisible; regressions in untested code go undetected | Add `pytest-cov` and set a minimum coverage threshold in CI |
| Low | Process-global py_trees blackboard | `vultron/core/behaviors/bridge.py` (`_BT_GLOBAL_LOCK`, an `RLock`), `vultron/core/behaviors/blackboard_scope.py`, `test/core/behaviors/conftest.py` | Executions are serialized and execution-scoped keys are snapshotted and restored, and BT tests clear storage before each test; a key outside the managed sets can still outlive its execution | Add any new execution-scoped key to the managed set (BT-17-007) |
| Low | Architecture boundary tests fully passing | `test/architecture/test_core_no_adapter_imports.py`, `test/architecture/test_core_no_wire_imports.py` (`KNOWN_VIOLATIONS: frozenset()`) | Boundary is clean | Maintain: new violations fail the ratchet test immediately |
| Low | One production TODO remains | `vultron/bt/report_management/_behaviors/report_to_others.py:106` (AllPartiesKnown simulated-annealing idea, in the legacy simulator); the former backlog issue #505 is closed; `vultron/core/states/cs.py:121` is a resolution NOTE (CONCERN-2099 / #2834) | A speculative enhancement in read-only reference code, not tech debt | Convert it into a tracked Idea or drop it |

### 2) Technical Debt

| Debt item | Why it exists | Where | Risk if ignored | Suggested fix |
|-----------|---------------|-------|-----------------|---------------|
| `transitions` state machine library in core | Core state machines wrap `transitions`; third-party lib in domain layer | `vultron/core/states/em.py`, `rm.py`, `cs.py`, `participant_embargo_consent.py`; `vultron/core/services/embargo_lifecycle/base.py` | Library API changes affect core domain directly | Encapsulate behind a domain-owned state-machine port if `transitions` ever becomes a migration blocker |
| `vultron/demo/` imports from adapters | Demo is intentionally a user of adapters, but the boundary between demo and production code is fuzzy | `vultron/demo/` | Demo code mutating shared state could silently affect production code paths | Document or test which demo modules are safe to import in non-demo contexts |
| `Makefile` `api_dev` target names a module that does not exist | Target predates the move of the app to `vultron/adapters/driving/fastapi/main.py` | `Makefile` (`uv run uvicorn vultron.api:app --reload --port 7999`) | `make api_dev` fails at import | Point it at `vultron.adapters.driving.fastapi.main:app`, as `docker/Dockerfile` does |
| `scipy` declared as a production dependency but never imported | No module in `vultron/` or `test/` imports it; it appears only in docs prose | `pyproject.toml` `dependencies` | Install size and supply-chain surface for no runtime use | [ASK USER] whether to drop it |
| `help/` declared as a `uv` workspace member but absent | `[tool.uv.workspace] members = ["help"]` with no `help/` directory in the tree | `pyproject.toml` | Confusing workspace config; tooling may warn | Remove the member or add the package |
| Unimplemented adapter stubs | Production delivery, shared inbox and connector loading are designed but not built | `vultron/adapters/driven/prod_http_delivery.py`, `vultron/adapters/driving/shared_inbox.py`, `vultron/adapters/connectors/loader.py` | No production-ready transport or plugin path | Implement per OX-10, OX-11 when scheduled |

### 3) Security Concerns

| Risk | OWASP category | Evidence | Current mitigation | Gap |
|------|----------------|----------|--------------------|-----|
| No inbound authentication / signature verification on inbox endpoint | A07 Identification & Authentication Failures | `vultron/adapters/driving/fastapi/routers/actors/_routes.py`; `vultron/adapters/driving/shared_inbox.py` docstring plans HTTP Signature validation (OX-11) but raises `NotImplementedError` | Outbound design intends HTTP Signatures (`prod_http_delivery.py` docstring, OX-10-004), but that adapter is also a stub | Implement and document inbound HTTP Signature verification before any networked deployment |
| Secrets management strategy undocumented | A02 Cryptographic Failures | `.env.example` (only `PROJECT_NAME` documented) | Config loaded from YAML/env; no hardcoded secrets observed | Document required secrets, their lifecycle, and rotation procedure |
| SQLite single-file store accessible to any local process | A01 Broken Access Control | `vultron/adapters/driven/datalayer_sqlite/engine.py` | No file-system permission controls observed in code | For production, enforce OS-level file permissions or migrate to a server-based DB with access controls |

### 4) Performance and Scaling Concerns

| Concern | Evidence | Current symptom | Scaling risk | Suggested improvement |
|---------|----------|-----------------|-------------|-----------------------|
| SQLite serializes writes | SQLite architecture | Acceptable for prototype demos | Multi-actor or federated deployment cannot share one SQLite file | Plan data store migration for production (see §1) |
| BT execution is synchronous and globally serialized | `vultron/core/behaviors/bridge.py` (`_BT_GLOBAL_LOCK`), `vultron/adapters/driving/fastapi/inbox_orchestration.py` | Measured (#3033, #2898): 0.2–2.5 s per inbound BT tick under CI load. The inbox background task now runs the tick in a worker thread (IE-06-003), but every BT execution in a process still takes the one lock | Any new `async` adapter path that calls into the BT bridge inline reintroduces the event-loop stall; throughput is bounded by one tree at a time | Keep BT execution off the event loop: sync `def` routes run in Starlette's threadpool, async tasks use `asyncio.to_thread` (ratchet: `test/adapters/driving/fastapi/test_inbox_orchestration_offloop.py`) |
| High-churn files signal fragile areas | Scan (90 days to 2026-10-01): `AGENTS.md` (184), `mkdocs.yml` (151), `docs/adr/index.md` (123), `notes/README.md` (107), `specs/case-management.yaml` (101), `uv.lock` (81), `pyproject.toml` (63) | Top churn is dominated by docs, specs, agent guidance and the lockfile, not production code | Low-risk day-to-day; heavy spec/ADR churn reflects active protocol design | Monitor `uv.lock`/`pyproject.toml` churn; pin critical deps once stabilized |

### 5) Fragile/High-Churn Areas

| Area | Why fragile | Churn signal | Safe change strategy |
|------|-------------|-------------|----------------------|
| `vultron/demo/scenario/fvcv_handoff_demo.py` | Demo exercises many layers; any layer change can break it | 61 commits in 90 days (highest in production source) | Run `uv run pytest -m integration` before touching demo scenarios |
| `vultron/demo/scenario/fccv_handoff_demo.py`, `fvcv_extension_demo.py`, `fcvcv_demo.py`, `fccv_extension_demo.py` | Companion multi-actor scenarios that co-evolve | 43–50 commits each in 90 days | Run demo integration tests after scenario changes |
| `vultron/demo/helpers/polling.py` | Causal-polling helpers shared by every scenario; the largest file in `vultron/` | 45 commits in 90 days | Run `test/demo/test_polling_helpers.py` and the demo suite |
| `vultron/core/behaviors/case/case_proposal_received_tree.py` | Case proposal BT tree under active development (embargo initialization, MS-12 tree) | 42 commits in 90 days | Verify BT spec IDs and run case-proposal tests |
| `vultron/core/models/base.py`, `vultron/core/models/_helpers.py` | Base `CoreObject` behavior (aliases, reference fields, time handling) that every domain type inherits | 21 commits each in the last 30 days (highest in core) | Run the full unit suite; check `test/architecture/test_core_extra_forbid.py` and `test_core_reference_fields_reject_blank.py` |
| `vultron/wire/as2/parser.py`, `vultron/wire/as2/extractor/_builders.py` | Parse edge (unknown keys, `published` refusal) and event building | 16 and 18 commits in the last 30 days | Run `test/wire/` and `test_vocab_examples_dispatchable.py` |
| `vultron/core/use_cases/received/embargo.py` | Embargo proposal adjudication and relay through the CASE_MANAGER (ADR-0113); over the CS-18 cap | 16 commits in the last 30 days | Run embargo received-side and relay tests |
| `vultron/adapters/driving/fastapi/routers/trigger_*.py` + `trigger_runner.py` | Every trigger route was cut over to `run_trigger` and the registry in 2026-09/10 (ADR-0110) | New since 2026-09-30 | Regenerate the OpenAPI snapshot deliberately; run `test_trigger_registry_ratchets.py` |
| `specs/*.yaml` + `docs/adr/index.md` + `AGENTS.md` + `mkdocs.yml` | Highest-churn files overall are design/spec/doc artifacts | See §4 | Treat spec edits as design changes; re-run `spec-lint` / `spec-check.yml` |

### 6) `[ASK USER]` Questions

1. [ASK USER] The outbound-delivery design targets HTTP Signatures (per the `prod_http_delivery.py` stub docstring / OX-10-004), and the shared-inbox stub plans inbound signature validation (OX-11), but neither is implemented and the per-actor inbox route checks nothing.
   Is inbound HTTP Signature verification the planned auth model for the per-actor inbox too, and when is it scheduled?
2. [ASK USER] What is the intended production database backend?
   SQLite is explicitly prototype-only; is a migration path to PostgreSQL or another server-based store planned?
3. [ASK USER] Should PII from vulnerability reports (reporter identity, affected software details) be redacted at log boundaries?
   Only `_log_label()` hashing of some identifiers was observed.
4. [ASK USER] Is there a minimum test coverage percentage target, or is coverage tracking not yet a goal?
5. [ASK USER] Are the connector adapters (`vultron/adapters/connectors/example/`) examples only?
   Their package name and the stub loader suggest so.
6. [ASK USER] Should `scipy` remain a production dependency when nothing imports it?
7. [ASK USER] Should each core module over the CS-18-001 threshold get its own split issue, or is the threshold treated as advisory (it is a SHOULD) for files that hold one responsibility?

### 7) Evidence

- `/tmp/.codebase-scan.txt` "HIGH-CHURN FILES" and "TODO / FIXME / HACK" sections (2026-10-01 scan; the scan's TODO section is polluted with `site/` build artifacts, so the production list was re-derived with `git grep -nE "TODO|FIXME|HACK" -- 'vultron/*.py'`)
- `git log --since=30.days --name-only -- vultron/` (30-day churn)
- `git ls-files 'vultron/*.py' | xargs wc -l` (module sizes)
- `test/architecture/test_core_no_adapter_imports.py`
- `test/architecture/test_no_bare_register_key_datalayer_nodes.py`
- `vultron/core/behaviors/bridge.py`
- `vultron/core/behaviors/blackboard_scope.py`
- `vultron/adapters/driving/shared_inbox.py`
- `vultron/adapters/driven/prod_http_delivery.py`
- `vultron/adapters/driven/datalayer_sqlite/schema.py`
- `pyproject.toml` `dependencies`, `[dependency-groups].dev`, `[tool.uv.workspace]`, `[tool.ruff.lint]`
- `Makefile`
- `notes/lint-tooling.md`
