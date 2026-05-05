# Vultron API v2 Implementation Plan

## Overview

This plan tracks forward-looking work against `specs/*` and
`plan/PRIORITIES.md`. Contains only pending, in-progress, and blocked tasks.

**Completed tasks**: see `plan/history/IMPLEMENTATION_HISTORY.md`
(append-only archive).

**Priority ordering**: `plan/PRIORITIES.md` is authoritative for project
priority. Sections here are organized by topic (see
`specs/project-documentation.yaml` PD-06). Do not infer priority from
section order.

---

## Deferred (Per PRIORITIES.md)

- USE-CASE-01 **`CloseCaseUseCase` wire-type construction** — Replace direct
  construction of `VultronActivity(as_type="Leave")` with domain event
  emission through the `ActivityEmitter` port. Defer until outbound delivery
  integration beyond OX-1.0 is implemented.
- USE-CASE-02 **UseCase Protocol generic enforcement** — Decide on a
  consistent `UseCaseResult` Pydantic return envelope; enforce via mypy.
  Defer to after TECHDEBT-21/22.
- **EP-02/EP-03** — EmbargoPolicy API + compatibility evaluation
  (`PROD_ONLY`)
- **AR-04/AR-05/AR-06** — Job tracking, pagination, bulk ops (`PROD_ONLY`)
- AGENTIC-00 **Agentic AI integration** (Priority 1000) — out of scope until
  protocol foundation is stable
- FUZZ-00 **Fuzzer node re-implementation** (Priority 500) — see
  `notes/bt-fuzzer-nodes.md`
- DEMOMA **Multi-actor demo infrastructure** — Core infrastructure is
  substantially complete (Docker Compose, healthchecks, per-actor isolation,
  trigger-based puppeteering all done; see
  `plan/history/IMPLEMENTATION_HISTORY.md`). Remaining work tracked in
  Vultron#387. See `specs/multi-actor-demo.yaml` DEMOMA-01 through DEMOMA-05
  and `notes/demo-review-26042001.md`.
- ARCH-VIOLATIONS **Broader core→wire ARCH-01-001 violations** — BT nodes
  (`behaviors/case/nodes.py`, `suggest_actor_tree.py`) and trigger use cases
  (`triggers/embargo.py`, `triggers/case.py`, `triggers/actor.py`,
  `triggers/note.py`, `triggers/report.py`) all import wire vocab types
  directly. Each requires its own driven port or ActivityEmitter expansion.
  The deferred sync cleanup is complete; this work may now proceed.
