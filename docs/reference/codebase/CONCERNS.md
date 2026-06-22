# Codebase Concerns

## Core Sections (Required)

### 1) Top Risks (Prioritized)

| Severity | Concern | Evidence | Impact | Suggested action |
|----------|---------|----------|--------|------------------|
| high | The production-style path still uses module-level shared emitter/DataLayer facilities alongside newer per-app isolation work | `vultron/adapters/driving/fastapi/main.py`, `vultron/adapters/driving/fastapi/outbox_handler.py`, `vultron/adapters/driven/datalayer_sqlite/__init__.py` | Shared-process startup order can still affect runtime behavior | Continue migrating mounted-app wiring toward app-scoped state and keep isolation tests in place |
| high | Remote signed delivery and shared inbox handling are not implemented | `vultron/adapters/driven/prod_http_delivery.py`, `vultron/adapters/driving/shared_inbox.py` | Remote interoperability and security posture remain prototype-only | Treat these paths as explicit future work and avoid production claims |
| medium | Outbox draining is a 1-second safety-net polling loop over all registered actor DataLayers | `vultron/adapters/driving/fastapi/outbox_monitor.py` | Polling cost grows with actor count and queue depth is not surfaced | Add stronger event-driven wakeups and queue observability if actor count grows |
| medium | Several source files are large and likely mix responsibilities | `vultron/demo/scenario/two_actor_demo.py` (1029 lines), `vultron/core/case_states/hypercube.py` (909), `vultron/core/services/embargo_lifecycle.py` (880), `vultron/core/behaviors/case/accept_invite_tree.py` (828) | Review and testing costs increase in high-change areas | Extract cohesive submodules incrementally |
| medium | The scan script reports false negatives for entry points, containerization, and security/compliance despite committed files existing | `docs/reference/codebase/.codebase-scan.txt`, `docker/Dockerfile`, `.github/dependabot.yml` | Blind reliance on scan output can mis-document the repo | Keep Phase 2 manual verification as mandatory; improve scan heuristics if this skill is reused frequently |

### 2) Technical Debt

| Debt item | Why it exists | Where | Risk if ignored | Suggested fix |
|-----------|---------------|-------|-----------------|---------------|
| TODO/FIXME/HACK comments remain in production code | Incremental refactors and placeholder notes | `docs/reference/codebase/.codebase-scan.txt` TODO section | Future work stays ambiguous and can drift | Triage each item into a tracked issue or remove it |
| Shared vs actor-scoped DataLayer caching is still subtle | Backward-compatible adapter evolution | `vultron/adapters/driven/datalayer_sqlite/__init__.py`, `vultron/core/ports/datalayer.py` | Queue operations can silently hit the wrong scope | Keep narrowing callers to actor-scoped ports and expand regression coverage |
| `mcp_server.py` exposes tool functions but is not an in-tree registered MCP server | Priority 1000 is still future work | `vultron/adapters/driving/mcp_server.py` | Readers may overestimate current MCP readiness | Document it as a callable surface, not a fully registered server |
| Docs/build tooling lives in `project.dependencies`, not only dev dependencies | Packaging choice keeps docs buildable from runtime installs | `pyproject.toml` | Install footprint is larger than a minimal API runtime | [ASK USER] Confirm whether this packaging split is intentional or temporary |

### 3) Security Concerns

| Risk | OWASP category (if applicable) | Evidence | Current mitigation | Gap |
|------|--------------------------------|----------|--------------------|-----|
| No implemented signed/authenticated remote inbox delivery was found in the active adapter path | A07 / N/A | `vultron/adapters/driven/demo_http_delivery.py`, `vultron/adapters/driven/prod_http_delivery.py` | Prototype notes and stub placeholders make the limitation visible | The active remote-delivery path still posts unsigned HTTP requests |
| Config/secrets handling relies on env vars and Compose files | A05 / N/A | `.env.example`, `config.example.yaml`, `docker/docker-compose-multi-actor.yml` | Example files avoid committing secrets | No secret manager, rotation workflow, or auth material lifecycle was found |

### 4) Performance and Scaling Concerns

| Concern | Evidence | Current symptom | Scaling risk | Suggested improvement |
|---------|----------|-----------------|-------------|-----------------------|
| Polling-based outbox drain loop | `vultron/adapters/driving/fastapi/outbox_monitor.py` | Constant background work even with empty queues | More actors mean more unnecessary wakeups and reads | Add queue-driven wakeups/metrics and reduce full-scan polling |
| SQLite is the only active backend behind the public DataLayer facade | `vultron/adapters/driven/datalayer.py`, `vultron/adapters/driven/datalayer_sqlite/__init__.py` | Simple local persistence works well for demos/tests | Multi-writer or larger deployments may hit SQLite limits | Define the next supported backend before scaling beyond prototype use |

### 5) Fragile/High-Churn Areas

| Area | Why fragile | Churn signal | Safe change strategy |
|------|-------------|-------------|----------------------|
| `plan/` files and `AGENTS.md` | Guidance and priorities change frequently | top entries in scan churn section | Re-read before editing; expect stale assumptions |
| `pyproject.toml` and `uv.lock` | Dependency and tooling changes are active | both appear in top churn output | Verify commands and dependency names before documenting them |
| `vultron/core/behaviors/case/nodes.py` | Dense BT semantics in a hot area | 40 churn hits in scan output | Make narrow changes with focused tests |
| `vultron/demo/scenario/two_actor_demo.py` | Large scenario orchestrator with active edits | 32 churn hits and 1029 lines | Prefer small refactors backed by demo tests |
| `vultron/adapters/driving/fastapi/outbox_handler.py` and actor routes | Delivery/inbox glue is both central and active | 30 and 31 churn hits in scan output | Change with focused adapter tests plus integration coverage |

### 6) `[ASK USER]` Questions

1. [ASK USER] Are `ProdHttpDeliveryAdapter` and `SharedInboxAdapter` near-term
   deliverables, or should they remain documented as dormant placeholders?
2. [ASK USER] Is the current packaging choice of keeping MkDocs-related packages
   in `project.dependencies` intentional for runtime installs, or should docs
   tooling eventually move to a dev-only group?
3. [ASK USER] Should `mcp_server.py` be presented as an internal callable surface
   only, or is external MCP SDK registration expected soon enough to call it an
   active interface?

### 7) Evidence

- `docs/reference/codebase/.codebase-scan.txt`
- `vultron/adapters/driving/fastapi/main.py`
- `vultron/adapters/driving/fastapi/outbox_handler.py`
- `vultron/adapters/driving/fastapi/outbox_monitor.py`
- `vultron/adapters/driving/shared_inbox.py`
- `vultron/adapters/driving/mcp_server.py`
- `vultron/adapters/driven/datalayer.py`
- `vultron/adapters/driven/datalayer_sqlite/__init__.py`
- `vultron/adapters/driven/demo_http_delivery.py`
- `vultron/adapters/driven/prod_http_delivery.py`
- `pyproject.toml`
- `.github/dependabot.yml`
