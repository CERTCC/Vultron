---
source: ISSUE-1319
timestamp: '2026-07-10T16:47:59.132200+00:00'
title: Resolve per-actor ActorConfig at dispatch time
type: implementation
---

## Issue #1319 — Resolve per-actor ActorConfig at dispatch time so auto_create_case is honored in production

Added `_resolve_actor_config()` and `_submit_report_port_factory()` to `inbox_port_factories.py`, wired into `make_dispatcher()` via a new `_SUBMIT_REPORT_SEMANTICS` set. `SubmitReportReceivedUseCase` now receives `actor_config` from `SeedConfig` at dispatch time so `auto_create_case=False` is honoured in real deployments. Four new tests including AC-2 end-to-end test through `DirectActivityDispatcher`. PR: <https://github.com/CERTCC/Vultron/pull/1331>
