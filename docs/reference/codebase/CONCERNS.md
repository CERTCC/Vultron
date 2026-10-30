---
stakeholder_type: [project-contributor]
---

# Codebase Concerns

## Core Sections (Required)

### 1) Top Risks (Prioritized)

| Severity | Concern | Evidence | Impact | Suggested action |
|----------|---------|----------|--------|------------------|
| High | SQLite not suitable for multi-node/concurrent writes | `vultron/adapters/driven/datalayer_sqlite/` | Prototype-only scalability ceiling; federation requires a distributed or replicated store | Define a migration plan to PostgreSQL or equivalent before production deployment |
| High | No inbound authentication on the inbox endpoint | `vultron/adapters/driving/fastapi/routers/actors/_routes.py`, `vultron/adapters/driving/shared_inbox.py` (stub) | Any network peer can post activities as any actor | Build the ADR-0164 signing and verification (epic #1156); see §3 Security Concerns |
| Medium | Many production modules exceed the CS-18-001 500-line threshold, including core files | `git ls-files 'vultron/*.py' \| xargs wc -l \| sort -rn`; 96 tracked modules exceed 500 lines on 2026-10-30; largest in core: `vultron/core/behaviors/sender_entitlement.py` (2,417 lines), `vultron/core/behaviors/helpers.py` (1,393), `vultron/core/ports/trigger_activity.py` (1,249); largest overall is `vultron/demo/helpers/polling.py` (2,519) | Large mixed-responsibility modules are where merge conflicts and missed edits concentrate | Split per CS-18-001/002; #3952 tracks `vultron/metadata/specs/lint.py`; [ASK USER] whether the remaining oversized modules should be filed as split issues |
| Medium | Inline lint suppressions baselined in production code | `# ruff-baseline #NNNN` markers in `vultron/` (find with `git grep "ruff-baseline" -- vultron/`), owned by #3353 (exception-handling rules), #3768 (BT node broad catches), #3326 (broad `except Exception`), #3989 (one broad catch in `vultron/demo/in_process.py`) | Broad catches can turn internal errors into refusals (#3768); each marker is a known deviation from CS-23-001 | Drain each issue's markers; RUF100 keeps a removed finding's stale marker from lingering |
| Medium | No test coverage measurement | `pyproject.toml` `[dependency-groups].dev` (no `pytest-cov`) | Coverage gaps are invisible; regressions in untested code go undetected | Add `pytest-cov` and set a minimum coverage threshold in CI |
| Low | Process-global py_trees blackboard | `vultron/core/behaviors/bridge.py` (`_BT_GLOBAL_LOCK`, an `RLock`), `vultron/core/behaviors/blackboard_scope.py`, `test/core/behaviors/conftest.py` | Executions are serialized and execution-scoped keys are snapshotted and restored, and BT tests clear storage before each test; a key outside the managed sets can still outlive its execution | Add any new execution-scoped key to the managed set (BT-17-007) |
| Low | Architecture boundary tests fully passing | `test/architecture/test_core_no_adapter_imports.py`, `test/architecture/test_core_no_wire_imports.py` (`KNOWN_VIOLATIONS: frozenset()`) | Boundary is clean | Maintain: new violations fail the ratchet test immediately |
| Low | Most CI workflows have jobs with no `timeout-minutes` cap, though TB-14-006 now requires one on every job | `.github/workflows/` (only `python-app.yml` caps every job; `ui.yml`, `spec-check.yml`, `verification-debt-owners.yml` and the single-job workflows have none); `specs/testability.yaml` TB-14-006; `test/metadata/test_gate_ceiling.py` checks only `python-app.yml` | A hung job holds a runner until GitHub's default limit and reads as cancelled, not failed | Implementation is tracked in #5507: add the caps and widen the test to every workflow |
| Low | One production TODO remains | `vultron/bt/report_management/_behaviors/report_to_others.py:106` (AllPartiesKnown simulated-annealing idea, in the legacy simulator); the former backlog issue #505 is closed; `vultron/core/states/cs.py:121` is a resolution NOTE (CONCERN-2099 / #2834) | A speculative enhancement in read-only reference code, not tech debt | Convert it into a tracked Idea or drop it |

### 2) Technical Debt

| Debt item | Why it exists | Where | Risk if ignored | Suggested fix |
|-----------|---------------|-------|-----------------|---------------|
| `transitions` state machine library in core | Core state machines wrap `transitions`; third-party lib in domain layer | `vultron/core/states/em.py`, `rm.py`, `cs.py`, `participant_embargo_consent.py`; `vultron/core/services/embargo_lifecycle/base.py` | Library API changes affect core domain directly | Encapsulate behind a domain-owned state-machine port if `transitions` ever becomes a migration blocker |
| `vultron/demo/` imports from adapters | Demo is intentionally a user of adapters, but the boundary between demo and production code is fuzzy | `vultron/demo/` | Demo code mutating shared state could silently affect production code paths | Document or test which demo modules are safe to import in non-demo contexts |
| `scipy` declared as a production dependency but never imported | No module in `vultron/` or `test/` imports it; it appears only in docs prose | `pyproject.toml` `dependencies` | Install size and supply-chain surface for no runtime use | [ASK USER] whether to drop it |
| `help/` declared as a `uv` workspace member but absent | `[tool.uv.workspace] members = ["help"]` with no `help/` directory in the tree | `pyproject.toml` | Confusing workspace config; tooling may warn | Remove the member or add the package |
| Unimplemented adapter stubs | Production delivery, shared inbox and connector loading are designed but not built | `vultron/adapters/driven/prod_http_delivery.py`, `vultron/adapters/driving/shared_inbox.py`, `vultron/adapters/connectors/loader.py` | No production-ready transport or plugin path | Implement per OX-10, OX-11 when scheduled |
| Stub docstrings describe an auth model ADR-0164 set aside | The delivery and shared-inbox stubs predate ADR-0164 | `vultron/adapters/driven/prod_http_delivery.py` and `vultron/adapters/driving/shared_inbox.py` docstrings (HTTP Signatures, OX-10-004, OX-11); `docs/adr/0164-actors-sign-content-with-object-level-proofs-from-seeded-keys.md` (object-level proofs, HTTP Signatures deferred to #1184) | An agent reading the stubs builds the wrong signing layer | [ASK USER] whether the stubs and OX-10-004/OX-11 should be reworded now |

### 3) Security Concerns

| Risk | OWASP category | Evidence | Current mitigation | Gap |
|------|----------------|----------|--------------------|-----|
| No inbound authentication / signature verification on inbox endpoint | A07 Identification & Authentication Failures | `vultron/adapters/driving/fastapi/routers/actors/_routes.py`; strict-`xfail` tests `test/adapters/driving/fastapi/test_signed_delivery_refusal.py` and `test/core/use_cases/received/test_signed_ledger_entries.py` | ADR-0164 decides the model: an FEP-8b32 proof inside every activity, verified strictly with no switch; nothing signs or verifies yet | Land signing and verification (epic #1156); ADR-0164's seeded keys let anyone who knows the scheme sign as a prototype actor, so production keys (#1184) are needed before any networked deployment |
| Secrets management strategy undocumented | A02 Cryptographic Failures | `.env.example` (only `PROJECT_NAME` documented) | Config loaded from YAML/env; no hardcoded secrets observed | Document required secrets, their lifecycle, and rotation procedure |
| SQLite single-file store accessible to any local process | A01 Broken Access Control | `vultron/adapters/driven/datalayer_sqlite/engine.py` | No file-system permission controls observed in code | For production, enforce OS-level file permissions or migrate to a server-based DB with access controls |

### 4) Performance and Scaling Concerns

| Concern | Evidence | Current symptom | Scaling risk | Suggested improvement |
|---------|----------|-----------------|-------------|-----------------------|
| SQLite serializes writes | SQLite architecture | Acceptable for prototype demos | Multi-actor or federated deployment cannot share one SQLite file | Plan data store migration for production (see §1) |
| BT execution is synchronous and globally serialized | `vultron/core/behaviors/bridge.py` (`_BT_GLOBAL_LOCK`), `vultron/adapters/driving/fastapi/inbox_orchestration.py` | Measured (#3033, #2898): 0.2–2.5 s per inbound BT tick under CI load. The inbox background task now runs the tick in a worker thread (IE-06-003), but every BT execution in a process still takes the one lock | Any new `async` adapter path that calls into the BT bridge inline reintroduces the event-loop stall; throughput is bounded by one tree at a time | Keep BT execution off the event loop: sync `def` routes run in Starlette's threadpool, async tasks use `asyncio.to_thread` (ratchet: `test/adapters/driving/fastapi/test_inbox_orchestration_offloop.py`) |
| Inbox queue replay holds the actor store's write lock for the whole attempt (#5051) | `vultron/adapters/driving/fastapi/inbox_queue_drain.py` (one `actor_dl.transaction()` per attempt); SQLite busy timeout of 5 s | None observed. Attempts are rare (deferred items and startup only) and last one BT tick, measured at 0.2–2.5 s under CI load (#3033). Outbox writes from the event loop wait for the lock, briefly stalling the loop | Under heavy traffic to one actor, a large case or a slow disk, an attempt can pass the 5 s busy timeout, and the waiting outbox write fails with "database is locked" (the outbox retries it). The event-loop stall grows with the attempt | Before production, move outbox store writes off the event loop, or migrate to a server database (see the SQLite row) |
| High-churn files signal fragile areas | Scan (90 days to 2026-10-30), highest churn first: `specs/case-management.yaml`, `docs/adr/index.md`, `AGENTS.md`, `mkdocs.yml`, `specs/case-ledger-processing.yaml`, `notes/embargo-lifecycle.md`, `notes/README.md` | The top 20 are specs, notes and docs, plus one test file (`test/core/behaviors/case/test_case_proposal_received_tree.py`); no production module and no lockfile | Low-risk day-to-day; heavy spec/ADR churn reflects active protocol design | Treat spec edits as design changes (see §5) |

### 5) Fragile/High-Churn Areas

| Area | Why fragile | Churn signal | Safe change strategy |
|------|-------------|-------------|----------------------|
| `vultron/demo/scenario/rvcv_handoff_demo.py` | Demo exercises many layers; any layer change can break it | Among the highest-churn production files over 90 days (counted as `fvcv_handoff_demo.py` before the Finder-to-Reporter rename) | Run `uv run pytest -m integration` before touching demo scenarios |
| `vultron/demo/scenario/rccv_handoff_demo.py`, `rvcv_extension_demo.py`, `rcvcv_demo.py`, `rccv_extension_demo.py` | Companion multi-actor scenarios that co-evolve | Each among the highest-churn production files over 90 days | Run demo integration tests after scenario changes |
| `vultron/demo/helpers/polling.py` | Causal-polling helpers shared by every scenario; the largest file in `vultron/` | Highest churn in production source over 90 days | Run `test/demo_unit/test_polling_helpers.py` and the demo suite |
| `vultron/core/behaviors/case/case_proposal_received_tree.py` | Case proposal BT tree under active development (embargo initialization, MS-12 tree) | Among the highest-churn production files over 90 days | Verify BT spec IDs and run case-proposal tests |
| `vultron/core/behaviors/sender_entitlement.py`, `vultron/core/ports/trigger_activity.py` | The single home of every sender check (ADR-0115), and the port every trigger use case and BT node builds outbound activities through; the two largest core modules | Highest churn in core over the last 30 days | Run `test/architecture/test_sender_entitlement_ratchet.py` and the trigger and received-side suites |
| `vultron/core/behaviors/case/receive_activity_tree.py`, `vultron/core/behaviors/sync/` | The shared received-tree factory, and the ledger-sync trees and nodes (announce, replay of held entries) | High churn in core over the last 30 days | Run `test/core/behaviors/` and `test_receive_side_intake_first.py` |
| `vultron/wire/as2/factories/case.py`, `vultron/wire/as2/extractor/` | Outbound case-activity factories, and event building at the parse edge | Highest churn in the wire layer over the last 30 days | Run `test/wire/` and `test_vocab_examples_dispatchable.py` |
| `vultron/adapters/driven/trigger_activity_adapter/actors.py` | The adapter side of `TriggerActivityPort` | Highest churn in adapters over the last 30 days | Run `test/adapters/driven/` and the trigger route tests |
| `vultron/core/use_cases/received/embargo/` | Embargo proposal adjudication and relay through the CASE_MANAGER (ADR-0113); split into a per-verb package (#4105) | High churn over the last 30 days | Run embargo received-side and relay tests |
| `vultron/adapters/driving/fastapi/routers/trigger_*.py` + `trigger_runner.py` | Every trigger route was cut over to `run_trigger` and the registry in 2026-09/10 (ADR-0110) | New since 2026-09-30 | Regenerate the OpenAPI snapshot deliberately; run `test_trigger_registry_ratchets.py` |
| `specs/*.yaml` + `docs/adr/index.md` + `AGENTS.md` + `mkdocs.yml` | Highest-churn files overall are design/spec/doc artifacts | See §4 | Treat spec edits as design changes; re-run `spec-lint` / `spec-check.yml` |

### 6) `[ASK USER]` Questions

1. [ASK USER] ADR-0164 chooses object-level proofs and defers HTTP Signatures to #1184, but the `prod_http_delivery.py` and `shared_inbox.py` stub docstrings, and OX-10-004 and OX-11 behind them, still describe HTTP Signatures.
   Should they be reworded to match ADR-0164 now, or left until #1184 settles whether HTTP Signatures come back as a transport layer?
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

- `/tmp/codebase-scan.txt` "HIGH-CHURN FILES" section (2026-10-30 scan); the production TODO list was derived with `git grep -nE "TODO|FIXME|HACK" -- 'vultron/*.py'`
- `git log --since=30.days --name-only -- vultron/` and `git log --since=90.days --name-only -- 'vultron/*.py'` (production churn)
- `git ls-files 'vultron/*.py' | xargs wc -l` (module sizes)
- `test/architecture/test_core_no_adapter_imports.py`
- `test/architecture/test_no_bare_register_key_datalayer_nodes.py`
- `vultron/core/behaviors/bridge.py`
- `vultron/core/behaviors/blackboard_scope.py`
- `vultron/adapters/driving/shared_inbox.py`
- `vultron/adapters/driven/prod_http_delivery.py`
- `vultron/adapters/driven/datalayer_sqlite/schema.py`
- `pyproject.toml` `dependencies`, `[dependency-groups].dev`, `[tool.uv.workspace]`, `[tool.ruff.lint]`
- `docs/adr/0164-actors-sign-content-with-object-level-proofs-from-seeded-keys.md`
- `specs/testability.yaml` (TB-14-006)
- `test/metadata/test_gate_ceiling.py`
- `notes/lint-tooling.md`
