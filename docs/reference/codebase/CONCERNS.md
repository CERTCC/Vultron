# Codebase Concerns

## Core Sections (Required)

### 1) Top Risks (Prioritized)

| Severity | Concern | Evidence | Impact | Suggested action |
|----------|---------|----------|--------|------------------|
| high | `vultron/demo/utils.py` and `vultron/demo/scenario/two_actor_demo.py` import `requests`, but `requests` is not declared in `project.dependencies` | `vultron/demo/utils.py`, `vultron/demo/scenario/two_actor_demo.py`, `pyproject.toml` | Fresh non-dev installs may fail when demos run outbound HTTP calls; `httpx` (`>=0.28.1`) is already a declared runtime dep and could replace `requests` | Migrate demo HTTP calls from `requests` to `httpx` (already declared) |
| high | Shared and actor-scoped DataLayer behavior depends on canonical actor-ID resolution and process-local façades | `vultron/adapters/driving/fastapi/deps.py`, `vultron/adapters/driving/fastapi/inbox_handler.py`, `vultron/adapters/driven/datalayer.py` | Subtle routing/storage bugs can appear when queue and object reads use different scopes | Keep scope boundaries explicit and add regression tests around actor-ID normalization |
| medium | Outbox draining is implemented as a 1-second polling loop over all actor DataLayers | `vultron/adapters/driving/fastapi/outbox_monitor.py` | Polling cost grows with actor count and can hide queue-depth issues | Consider event-driven wakeups or queue metrics if actor count grows |
| medium | Several source files exceed 500 lines and mix multiple responsibilities | `vultron/demo/scenario/two_actor_demo.py` (2050 lines), `vultron/core/behaviors/case/nodes.py` (1502 lines), `vultron/adapters/driven/datalayer_sqlite.py` (1042 lines), `vultron/wire/as2/extractor.py` (821 lines), `vultron/semantic_registry.py` (783 lines) | Large, multi-responsibility files are harder to test, review, and maintain; `nodes.py` is also high-churn | Incrementally extract cohesive sub-modules; prioritize `nodes.py` and `extractor.py` given their churn rate |

### 2) Technical Debt

| Debt item | Why it exists | Where | Risk if ignored | Suggested fix |
|-----------|---------------|-------|-----------------|---------------|
| 15 outstanding TODOs in protocol/state code | Incremental development; partially-finished refactors left in place | `vultron/bt/report_management/_behaviors/report_to_others.py`, `vultron/wire/as2/vocab/objects/embargo_event.py`, `vultron/core/states/cs.py`, `vultron/wire/as2/vocab/activities/case_participant.py`, `vultron/bt/base/bt_node.py` | Ambiguous future work and partially-finished refactors accumulate silently | Triage each TODO into a tracked issue or remove it; do not leave XXX markers in BT factory calls |
| `http_delivery.py` and `shared_inbox.py` are stubs with no implementation | Placeholder-driven design for future signed HTTP delivery and shared-inbox fan-out | `vultron/adapters/driven/http_delivery.py`, `vultron/adapters/driving/shared_inbox.py` | No production delivery path for signed or shared-inbox flows; callers may assume these are functional | Implement or clearly gate behind feature flags before any production use |
| Documentation/code drift around architecture targets | Notes describe both target and current structure | `notes/architecture-ports-and-adapters.md`, `AGENTS.md` | New contributors may confuse target layout with what exists today | Keep onboarding docs explicitly split into "current reality" vs "target direction" |
| High churn in planning and specification files | Planning/spec docs evolve rapidly during active development | `plan/IMPLEMENTATION_PLAN.md` (386 changes), `plan/IMPLEMENTATION_NOTES.md` (306), `AGENTS.md` (87) in last 90 days | Agent guidance and task context can go stale quickly | Treat `plan/` and guidance docs as volatile areas during onboarding; re-read before each session |
| `vultron/semantic_registry.py` is a 783-line centralized dispatch table | Single module consolidates all message-type to handler wiring | `vultron/semantic_registry.py` | Any new message type requires editing this file; tight coupling can cause merge conflicts | Consider splitting by domain area (report, case, embargo, actor) once the registry stabilises |

### 3) Security Concerns

| Risk | OWASP category (if applicable) | Evidence | Current mitigation | Gap |
|------|--------------------------------|----------|--------------------|-----|
| No explicit auth/signing was evident in sampled outbound or inbound HTTP delivery paths | A01 / N/A | `vultron/adapters/driven/delivery_queue.py`, `vultron/adapters/driving/fastapi/app.py`, `vultron/adapters/driving/fastapi/routers/actors.py` | Local actor IDs and inbox URLs are explicit | Authentication, authorization, or message-signing behavior was not evident in sampled files |
| Secret handling appears to rely on plain env vars and Compose files | A05 / N/A | `.env.example`, `docker/docker-compose.yml`, `docker/docker-compose-multi-actor.yml` | Example files avoid committed secrets | No secret-rotation or secret-manager integration was found |

### 4) Performance and Scaling Concerns

| Concern | Evidence | Current symptom | Scaling risk | Suggested improvement |
|---------|----------|-----------------|-------------|-----------------------|
| Polling outbox handler scans every actor DataLayer once per second | `vultron/adapters/driving/fastapi/outbox_monitor.py` | Constant polling work even when queues are empty | More actors mean more unnecessary wakeups and reads | Add queue-driven wakeups or adaptive polling |
| SQLite is the only active persistence backend exposed by the facade | `vultron/adapters/driven/datalayer.py`, `vultron/adapters/driven/datalayer_sqlite.py` | Local-file DB is simple for tests and demos | Multi-writer or higher-volume deployments may hit SQLite limits | Define the next backend/operational profile before scaling beyond demos |

### 5) Fragile/High-Churn Areas

| Area | Why fragile | Churn signal | Safe change strategy |
|------|-------------|-------------|----------------------|
| `plan/` documentation set | Planning/history docs change very frequently | `plan/IMPLEMENTATION_PLAN.md`, `plan/IMPLEMENTATION_NOTES.md` top the 90-day churn list | Read current files immediately before editing; expect stale assumptions |
| `AGENTS.md` and spec guidance | Repo rules change often and affect coding behavior | `AGENTS.md` (87 changes in 90 days), `specs/README.md` in high-churn output | Re-read guidance before non-trivial changes |
| `vultron/core/behaviors/case/nodes.py` | Encodes case-protocol BT semantics; largest source file at 1502 lines | 47 git changes in last 90 days | Make narrow changes with focused tests; extract sub-modules to reduce blast radius |
| `vultron/wire/as2/extractor.py` | AS2-to-domain semantic extraction; pattern ordering is order-sensitive | 36 git changes in last 90 days | Run `test/test_semantic_activity_patterns.py` after every edit; add pattern tests before adding patterns |
| `vultron/core/use_cases/triggers/embargo.py` | Embargo use-case trigger logic; 31 changes in 90 days at 792 lines | 31 git changes in last 90 days | Narrow PRs with explicit test coverage for each embargo state transition |

### 6) `[ASK USER]` Questions

1. [ASK USER] Which HTTP entrypoint should onboarding docs treat as canonical:
   `vultron.adapters.driving.fastapi.main:app` for deployment, or direct
   `app_v2` usage for local development and tests?
2. [ASK USER] Demo HTTP calls (`vultron/demo/utils.py`,
   `vultron/demo/scenario/two_actor_demo.py`) use `requests`, which is not in
   `project.dependencies`. The tech-stack spec (IMPLTS-03-002) requires `httpx`
   and prohibits `requests`. Migrate demo HTTP calls to `httpx` (already a
   declared runtime dep).
3. [ASK USER] Are `http_delivery.py` and `shared_inbox.py` stubs intended for
   near-term implementation, or are they architectural placeholders with no active
   implementation timeline?

### 7) Evidence

- `docs/reference/codebase/.codebase-scan.txt`
- `pyproject.toml`
- `docker/Dockerfile`
- `vultron/adapters/driving/fastapi/deps.py`
- `vultron/adapters/driving/fastapi/inbox_handler.py`
- `vultron/adapters/driving/fastapi/outbox_monitor.py`
- `vultron/adapters/driving/shared_inbox.py`
- `vultron/adapters/driven/datalayer.py`
- `vultron/adapters/driven/datalayer_sqlite.py`
- `vultron/adapters/driven/delivery_queue.py`
- `vultron/adapters/driven/asgi_emitter.py`
- `vultron/adapters/driven/http_delivery.py`
- `vultron/adapters/driven/sync_activity_adapter.py`
- `vultron/adapters/driven/trigger_activity_adapter.py`
- `vultron/demo/utils.py`
- `vultron/demo/scenario/two_actor_demo.py`
- `vultron/semantic_registry.py`
- `vultron/core/behaviors/case/nodes.py`
- `vultron/wire/as2/extractor.py`
- `vultron/core/use_cases/triggers/embargo.py`
- `git log --since="90 days ago"` (churn data)
