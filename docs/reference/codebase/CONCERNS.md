# Codebase Concerns

## Core Sections (Required)

### 1) Top Risks (Prioritized)

| Severity | Concern | Evidence | Impact | Suggested action |
|----------|---------|----------|--------|------------------|
| Low | Architecture boundary tests fully passing | `test/architecture/test_core_no_adapter_imports.py` `KNOWN_VIOLATIONS: frozenset()` | Both `test_core_no_adapter_imports.py` and `test_core_no_wire_imports.py` have empty violation sets — boundary is clean | Maintain: new violations will fail the ratchet test immediately |
| High | SQLite not suitable for multi-node/concurrent writes | `vultron/adapters/driven/datalayer_sqlite/` | Prototype-only scalability ceiling; federation requires a distributed or replicated store | Define migration plan to postgres or equivalent before production deployment |
| Medium | No test coverage measurement | `pyproject.toml` `[dependency-groups].dev` (no `pytest-cov`) | Coverage gaps are invisible; regressions in untested code go undetected | Add `pytest-cov` and set a minimum coverage threshold in CI |
| Medium | BT blackboard is process-global across BT runs | `vultron/bt/base/bt_node.py`, py-trees blackboard | A fresh `BtNode` tree constructed per-test does not automatically clear the py-trees global blackboard; residual state from a prior run can silently affect the next tree instance | Explicitly clear the blackboard (`py_trees.blackboard.Blackboard.enable_activity_stream(); ...`) between runs, or construct a scoped blackboard namespace per run |
| Medium | 11 outstanding TODO/FIXME markers in production code (GitHub #505) | `vultron/wire/as2/vocab/activities/case_participant.py:18-19`, `vultron/bt/base/bt_node.py:267`, others | Partially-finished refactors and deferred design decisions in wire layer and BT core | Triage each into a tracked issue or remove; prioritise `vultron/wire/` and `vultron/core/` items first |
| Low | `pacman.py` demo uses pre-Pydantic idioms | `vultron/bt/base/demo/pacman.py:37` | Demo code mixing old and new patterns; misleading for new contributors | Convert to Pydantic idioms or annotate as legacy demo |

### 2) Technical Debt

| Debt item | Why it exists | Where | Risk if ignored | Suggested fix |
|-----------|---------------|-------|-----------------|---------------|
| `datalayer_sqlite.py` backward-compat shim | DataLayer was split into subpackage; shim keeps callers working | `vultron/adapters/driven/datalayer_sqlite.py` | Shim is low-risk but signals incomplete migration; shim should not accumulate more re-exports | Remove shim once all callers import from subpackage directly |
| `transitions` state machine library in core | Core `vultron/core/states/` wraps `transitions`; third-party lib in domain layer | `vultron/core/states/em.py`, `rm.py`, `cs.py` | Library API changes affect core domain directly | Encapsulate behind a domain-owned state-machine port if transitions ever becomes a migration blocker |
| `vultron/demo/` imports from adapters | Demo is intentionally a user of adapters, but boundary between demo and production code is fuzzy | `vultron/demo/` | Demo code mutating shared state could silently affect production code paths | Document or test which demo modules are safe to import in non-demo contexts |

### 3) Security Concerns

| Risk | OWASP category | Evidence | Current mitigation | Gap |
|------|----------------|----------|--------------------|-----|
| No observed HTTP authentication on inbox endpoint | A07 Identification & Authentication Failures | `vultron/adapters/driving/fastapi/inbox_handler.py` (surface scan) | [TODO] — auth mechanism not confirmed | Confirm or document auth model; add to INTEGRATIONS.md |
| Secrets management strategy undocumented | A02 Cryptographic Failures | `.env.example` (only `PROJECT_NAME` documented) | Config loaded from YAML/env; no hardcoded secrets observed | Document required secrets, their lifecycle, and rotation procedure |
| SQLite single-file store accessible to any local process | A01 Broken Access Control | `vultron/adapters/driven/datalayer_sqlite/engine.py` | No file-system permission controls observed in code | For production, enforce OS-level file permissions or migrate to a server-based DB with access controls |

### 4) Performance and Scaling Concerns

| Concern | Evidence | Current symptom | Scaling risk | Suggested improvement |
|---------|----------|-----------------|-------------|-----------------------|
| SQLite serializes writes | SQLite architecture | Acceptable for prototype single-actor demo | Multi-actor or federated deployment cannot share one SQLite file | Plan data store migration for production (see risk #2 above) |
| BT tree execution is synchronous | `vultron/bt/base/bt_node.py`, `py-trees` library | Acceptable for current use; no measured bottleneck | Long-running BT ticks block the event loop if called from async context | Ensure BT execution runs in `BackgroundTasks` (already used in FastAPI layer) |
| High-churn files signal fragile areas | Scan: `plan/BUILD_LEARNINGS.md` (96), `AGENTS.md` (92), `plan/IMPLEMENTATION_PLAN.md` (88), `pyproject.toml` (71) | Frequent edits to planning files expected; `pyproject.toml` churn reflects active dependency management | Planning files are low-risk; `pyproject.toml` churn may indicate dependency pinning instability | Monitor `pyproject.toml` churn; pin critical deps once stabilized |

### 5) Fragile/High-Churn Areas

| Area | Why fragile | Churn signal | Safe change strategy |
|------|-------------|-------------|----------------------|
| `vultron/demo/scenario/fvcv_handoff_demo.py` | Demo exercises many layers; any layer change can break it | 44 commits in 90 days (highest churn in production source) | Run `uv run pytest -m integration` before touching demo scenarios |
| `vultron/demo/helpers/polling.py` | Causal polling helpers added in 2026-08 (PR #2695); gating logic actively evolving | 33 commits in 90 days | Run demo integration tests after any polling-helper change |
| `vultron/core/behaviors/case/case_proposal_received_tree.py` | Case proposal BT tree under active development | 34 commits in 90 days | Verify BT spec IDs and run case-proposal tests |
| `vultron/core/behaviors/sync/nodes/chain.py` | Sync chain nodes evolving with replication work | 32 commits in 90 days | Run sync BT tests and check chain invariants |
| `vultron/core/use_cases/triggers/actor.py` | Actor trigger use cases expand with new protocol transitions | 31 commits in 90 days | Check `USE_CASE_MAP` consistency after changes |
| `vultron/adapters/driven/trigger_activity_adapter/actors.py` | Driven adapter mirrors trigger use-case growth | 28 commits in 90 days | Run integration tests after changes |
| `vultron/core/behaviors/embargo/nodes/lifecycle.py` | Embargo lifecycle BT nodes track active embargo spec work | 25 commits in 90 days | Verify embargo spec IDs in tests after changes |
| `vultron/core/behaviors/case/nodes/` | BT node refactoring ongoing — `case_setup.py` was split into `case_setup.py` + `case_actor_setup.py` in 2026-08 | High churn; active decomposition | Test BT execution before any node reorganization |
| `vultron/core/ports/trigger_activity.py` | Trigger port evolves with use-case expansion | 27 commits in 90 days | Run integration tests after changes; check `USE_CASE_MAP` consistency |
| `vultron/core/behaviors/sync/nodes/` | Sync nodes refactored — `conditions.py` split into `conditions.py` + `event_conditions.py` | Active decomposition in 2026-08 | Check both modules when touching sync BT conditions |

### 6) `[ASK USER]` Questions

1. [ASK USER] Is there an authentication/authorization mechanism on the FastAPI inbox endpoint in production? The source scan did not confirm an auth scheme.
2. [ASK USER] What is the intended production database backend? SQLite is explicitly prototype-only; is a migration path to PostgreSQL or another server-based store planned?
3. [ASK USER] Should PII from vulnerability reports (reporter identity, affected software details) be redacted at log boundaries? No redaction logic was observed.
4. [ASK USER] Is there a minimum test coverage percentage target, or is coverage tracking not yet a goal?
5. [ASK USER] Are the connector adapters (`vultron/adapters/connectors/example/`) production-ready or examples only? Their package name (`example`) suggests the latter.

### 7) Evidence

- `.codebase-scan.txt` "HIGH-CHURN FILES" and "TODO / FIXME / HACK" sections (2026-08-26 scan)
- `test/architecture/test_core_no_adapter_imports.py`
- `test/architecture/test_no_bare_register_key_datalayer_nodes.py`
- `vultron/bt/base/bt_node.py`
- `vultron/wire/as2/vocab/activities/case_participant.py:18-19`
- `vultron/adapters/driven/datalayer_sqlite/schema.py`
- `pyproject.toml` `[dependency-groups].dev`
