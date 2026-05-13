# Codebase Concerns

## Core Sections (Required)

### 1) Top Risks (Prioritized)

| Severity | Concern | Evidence | Impact | Suggested action |
|----------|---------|----------|--------|------------------|
| high | `vultron/demo/utils.py` and `vultron/demo/scenario/two_actor_demo.py` import `requests`, but `requests` is not declared in `project.dependencies` | `vultron/demo/utils.py`, `vultron/demo/scenario/two_actor_demo.py`, `pyproject.toml` | Fresh non-dev installs may fail when demos run outbound HTTP calls; `httpx` (`>=0.28.1`) is already a declared runtime dep and could replace `requests` | Migrate demo HTTP calls from `requests` to `httpx` (already declared) |
| high | Shared and actor-scoped DataLayer behavior depends on canonical actor-ID resolution and process-local façades | `vultron/adapters/driving/fastapi/deps.py`, `vultron/adapters/driving/fastapi/inbox_handler.py`, `vultron/adapters/driven/datalayer.py` | Subtle routing/storage bugs can appear when queue and object reads use different scopes | Keep scope boundaries explicit and add regression tests around actor-ID normalization |
| medium | The automated scan over-reports generated/cache artifacts and under-reports real infra/security files | `docs/reference/codebase/.codebase-scan.txt`, `docker/docker-compose.yml`, `.github/dependabot.yml` | Repository mapping or metrics can mislead maintainers if consumed without manual correction | Update the scan ignore list or post-processing rules before using it as a durable source |
| medium | Outbox draining is implemented as a 1-second polling loop over all actor DataLayers | `vultron/adapters/driving/fastapi/outbox_handler.py` | Polling cost grows with actor count and can hide queue-depth issues | Consider event-driven wakeups or queue metrics if actor count grows |

### 2) Technical Debt

| Debt item | Why it exists | Where | Risk if ignored | Suggested fix |
|-----------|---------------|-------|-----------------|---------------|
| Outstanding TODOs in protocol/state code | Several production modules still carry TODO markers | `docs/reference/codebase/.codebase-scan.txt` | Ambiguous future work and partially-finished refactors accumulate | Triage TODOs into tracked issues or implementation-plan items |
| Documentation/code drift around architecture targets | Notes describe target architecture as well as current structure | `notes/architecture-ports-and-adapters.md`, `AGENTS.md` | New contributors may confuse target layout with what exists today | Keep onboarding docs explicitly split into “current reality” vs “target direction” |
| High churn in planning and specification files | Planning/spec docs change frequently | `docs/reference/codebase/.codebase-scan.txt` | Agent guidance and task context can go stale quickly | Treat `plan/` and guidance docs as volatile areas during onboarding |

### 3) Security Concerns

| Risk | OWASP category (if applicable) | Evidence | Current mitigation | Gap |
|------|--------------------------------|----------|--------------------|-----|
| No explicit auth/signing was evident in sampled outbound or inbound HTTP delivery paths | A01 / N/A | `vultron/adapters/driven/delivery_queue.py`, `vultron/adapters/driving/fastapi/app.py`, `vultron/adapters/driving/fastapi/routers/actors.py` | Local actor IDs and inbox URLs are explicit | Authentication, authorization, or message-signing behavior was not evident in sampled files |
| Secret handling appears to rely on plain env vars and Compose files | A05 / N/A | `.env.example`, `docker/docker-compose.yml`, `docker/docker-compose-multi-actor.yml` | Example files avoid committed secrets | No secret-rotation or secret-manager integration was found |

### 4) Performance and Scaling Concerns

| Concern | Evidence | Current symptom | Scaling risk | Suggested improvement |
|---------|----------|-----------------|-------------|-----------------------|
| Polling outbox handler scans every actor DataLayer once per second | `vultron/adapters/driving/fastapi/outbox_handler.py` | Constant polling work even when queues are empty | More actors mean more unnecessary wakeups and reads | Add queue-driven wakeups or adaptive polling |
| SQLite is the only active persistence backend exposed by the façade | `vultron/adapters/driven/datalayer.py`, `vultron/adapters/driven/datalayer_sqlite.py` | Local-file DB is simple for tests and demos | Multi-writer or higher-volume deployments may hit SQLite limits | Define the next backend/operational profile before scaling beyond demos |

### 5) Fragile/High-Churn Areas

| Area | Why fragile | Churn signal | Safe change strategy |
|------|-------------|-------------|----------------------|
| `plan/` documentation set | Planning/history docs change very frequently | `plan/IMPLEMENTATION_PLAN.md`, `plan/IMPLEMENTATION_NOTES.md`, `plan/BUGS.md` top the 90-day churn list in `docs/reference/codebase/.codebase-scan.txt` | Read current files immediately before editing; expect stale assumptions |
| `AGENTS.md` and spec guidance | Repo rules change often and affect coding behavior | `AGENTS.md`, `specs/README.md` both appear in high-churn output | Re-read guidance before non-trivial changes |
| Behavior and semantic extraction code | These modules encode protocol/state semantics and have recent churn | `vultron/core/behaviors/case/nodes.py`, `vultron/core/behaviors/report/nodes.py`, `vultron/wire/as2/extractor.py` appear in high-churn output | Make narrow changes with focused tests and explicit evidence checks |

### 6) `[ASK USER]` Questions

1. [ASK USER] Which HTTP entrypoint should onboarding docs treat as canonical:
   `vultron.adapters.driving.fastapi.main:app` for deployment, or direct
   `app_v2` usage for local development and tests?
2. Should demo HTTP calls (`vultron/demo/utils.py`, `vultron/demo/scenario/two_actor_demo.py`)
   be migrated from `requests` to `httpx` (already a declared runtime dep), or
   should `requests` be formally added to `project.dependencies`?

### 7) Evidence

- `docs/reference/codebase/.codebase-scan.txt`
- `pyproject.toml`
- `docker/Dockerfile`
- `vultron/adapters/driving/fastapi/deps.py`
- `vultron/adapters/driving/fastapi/inbox_handler.py`
- `vultron/adapters/driving/fastapi/outbox_handler.py`
- `vultron/adapters/driven/datalayer.py`
- `vultron/adapters/driven/delivery_queue.py`
- `vultron/adapters/driven/asgi_emitter.py`
- `vultron/demo/utils.py`
