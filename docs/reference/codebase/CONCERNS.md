---
stakeholder_type: [project-contributor]
---

# Codebase Concerns

## Core Sections (Required)

### 1) Top Risks (Prioritized)

| Severity | Concern | Evidence | Impact | Suggested action |
|----------|---------|----------|--------|------------------|
| Low | Architecture boundary tests fully passing | `test/architecture/test_core_no_adapter_imports.py` `KNOWN_VIOLATIONS: frozenset()` | Both `test_core_no_adapter_imports.py` and `test_core_no_wire_imports.py` have empty violation sets — boundary is clean | Maintain: new violations will fail the ratchet test immediately |
| High | SQLite not suitable for multi-node/concurrent writes | `vultron/adapters/driven/datalayer_sqlite/` | Prototype-only scalability ceiling; federation requires a distributed or replicated store | Define migration plan to postgres or equivalent before production deployment |
| Medium | No test coverage measurement | `pyproject.toml` `[dependency-groups].dev` (no `pytest-cov`) | Coverage gaps are invisible; regressions in untested code go undetected | Add `pytest-cov` and set a minimum coverage threshold in CI |
| Medium | BT blackboard is process-global across BT runs | `vultron/bt/base/bt_node.py`, py-trees blackboard | A fresh `BtNode` tree constructed per-test does not automatically clear the py-trees global blackboard; residual state from a prior run can silently affect the next tree instance | Explicitly clear the blackboard (`py_trees.blackboard.Blackboard.enable_activity_stream(); ...`) between runs, or construct a scoped blackboard namespace per run |
| Low | Production TODO/FIXME backlog now essentially cleared (was 11 per GitHub #505) | `grep TODO vultron/**/*.py` → 1 genuine deferred TODO: `vultron/bt/report_management/_behaviors/report_to_others.py:106` (AllPartiesKnown simulated-annealing idea); the former wire/BT TODOs at `case_participant.py` and `bt_node.py:267` are resolved (see the "Prior TODOs (now removed)" comment) and `cs.py:121` is now a resolution NOTE (CONCERN-2099 / #2834) | Backlog materially reduced; the remaining item is a speculative enhancement, not tech debt | Convert `report_to_others.py:106` into a tracked Idea or drop it; #505 can likely be closed |

### 2) Technical Debt

| Debt item | Why it exists | Where | Risk if ignored | Suggested fix |
|-----------|---------------|-------|-----------------|---------------|
| `transitions` state machine library in core | Core `vultron/core/states/` wraps `transitions`; third-party lib in domain layer | `vultron/core/states/em.py`, `rm.py`, `cs.py` | Library API changes affect core domain directly | Encapsulate behind a domain-owned state-machine port if transitions ever becomes a migration blocker |
| `vultron/demo/` imports from adapters | Demo is intentionally a user of adapters, but boundary between demo and production code is fuzzy | `vultron/demo/` | Demo code mutating shared state could silently affect production code paths | Document or test which demo modules are safe to import in non-demo contexts |

### 3) Security Concerns

| Risk | OWASP category | Evidence | Current mitigation | Gap |
|------|----------------|----------|--------------------|-----|
| No inbound authentication / signature verification on inbox endpoint | A07 Identification & Authentication Failures | `vultron/adapters/driving/fastapi/inbox_handler.py` (surface scan) | Outbound design intends HTTP Signatures (`prod_http_delivery.py` docstring, OX-10-004), but the outbound adapter is an unimplemented stub and no inbound verification was observed | Implement and document inbound HTTP Signature verification before any networked deployment |
| Secrets management strategy undocumented | A02 Cryptographic Failures | `.env.example` (only `PROJECT_NAME` documented) | Config loaded from YAML/env; no hardcoded secrets observed | Document required secrets, their lifecycle, and rotation procedure |
| SQLite single-file store accessible to any local process | A01 Broken Access Control | `vultron/adapters/driven/datalayer_sqlite/engine.py` | No file-system permission controls observed in code | For production, enforce OS-level file permissions or migrate to a server-based DB with access controls |

### 4) Performance and Scaling Concerns

| Concern | Evidence | Current symptom | Scaling risk | Suggested improvement |
|---------|----------|-----------------|-------------|-----------------------|
| SQLite serializes writes | SQLite architecture | Acceptable for prototype single-actor demo | Multi-actor or federated deployment cannot share one SQLite file | Plan data store migration for production (see risk #2 above) |
| BT tree execution is synchronous | `vultron/bt/base/bt_node.py`, `py-trees` library | Acceptable for current use; no measured bottleneck | Long-running BT ticks block the event loop if called from async context | Ensure BT execution runs in `BackgroundTasks` (already used in FastAPI layer) |
| High-churn files signal fragile areas | Scan (90 days): `AGENTS.md` (114), `mkdocs.yml` (105), `docs/adr/index.md` (87), `specs/case-management.yaml` (73), `uv.lock` (66), `pyproject.toml` (52) | Top churn is now dominated by docs/specs/agent-guidance and dependency lockfile, not production code | Low-risk day-to-day; heavy spec/ADR churn reflects active protocol design, not code instability | Monitor `uv.lock`/`pyproject.toml` churn; pin critical deps once stabilized |

### 5) Fragile/High-Churn Areas

| Area | Why fragile | Churn signal (90 days) | Safe change strategy |
|------|-------------|-------------|----------------------|
| `vultron/demo/scenario/fvcv_handoff_demo.py` | Demo exercises many layers; any layer change can break it | 51 commits (highest churn in production source) | Run `uv run pytest -m integration` before touching demo scenarios |
| `vultron/demo/scenario/fccv_handoff_demo.py` | Companion multi-actor handoff scenario, co-evolving with fvcv | 40 commits | Run demo integration tests after scenario changes |
| `vultron/demo/scenario/fvcv_extension_demo.py` | Embargo-extension demo scenario under active development | 37 commits | Run demo integration tests after scenario changes |
| `vultron/demo/scenario/fcvcv_demo.py` | Multi-vendor demo scenario | 36 commits | Run demo integration tests after scenario changes |
| `vultron/core/behaviors/case/case_proposal_received_tree.py` | Case proposal BT tree under active development | 37 commits | Verify BT spec IDs and run case-proposal tests |
| `vultron/core/behaviors/sync/nodes/chain.py` | Sync chain nodes evolving with replication work | still active (`conditions.py` split into `conditions.py` + `event_conditions.py`) | Run sync BT tests; check both condition modules |
| `specs/*.yaml` + `docs/adr/index.md` + `AGENTS.md` + `mkdocs.yml` | Highest-churn files overall are design/spec/doc artifacts, not code — reflects active protocol design | `AGENTS.md` 114, `mkdocs.yml` 105, `docs/adr/index.md` 87, `specs/case-management.yaml` 73 | Treat spec edits as design changes; re-run `spec-lint` / `spec-check.yml` |

### 6) `[ASK USER]` Questions

1. [ASK USER] The outbound-delivery design targets HTTP Signatures (per the `prod_http_delivery.py` stub docstring / OX-10-004), but that adapter is unimplemented and no *inbound* signature verification exists on the FastAPI inbox endpoint. Is inbound HTTP Signature verification the planned auth model, and when is it scheduled?
2. [ASK USER] What is the intended production database backend? SQLite is explicitly prototype-only; is a migration path to PostgreSQL or another server-based store planned?
3. [ASK USER] Should PII from vulnerability reports (reporter identity, affected software details) be redacted at log boundaries? No redaction logic was observed.
4. [ASK USER] Is there a minimum test coverage percentage target, or is coverage tracking not yet a goal?
5. [ASK USER] Are the connector adapters (`vultron/adapters/connectors/example/`) production-ready or examples only? Their package name (`example`) suggests the latter.

### 7) Evidence

- `.codebase-scan.txt` "HIGH-CHURN FILES" and "TODO / FIXME / HACK" sections (2026-09-17 scan; note the scan's TODO section is polluted with `site/` and `graphify-out/` build artifacts — the production count was re-derived with `grep TODO vultron/**/*.py`)
- `test/architecture/test_core_no_adapter_imports.py`
- `test/architecture/test_no_bare_register_key_datalayer_nodes.py`
- `vultron/bt/base/bt_node.py`
- `vultron/wire/as2/vocab/activities/case_participant.py:18-19`
- `vultron/adapters/driven/datalayer_sqlite/schema.py`
- `pyproject.toml` `[dependency-groups].dev`
