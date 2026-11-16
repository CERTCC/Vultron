---
source: CONCERN-4541
timestamp: '2026-11-16T19:41:07.708659+00:00'
title: In-process demo tests share one process-global ActorConfig
type: learning
---

Theme: theme:test-and-ci — makes in-process demo tests give each actor its own config so they catch what Docker catches.

## Summary

Every in-process demo node (the shared `TestClient` app, and every `IsolatedActorApp` in `test/demo/conftest.py`) reads one process-global `get_config()`. So a CaseActor that reads its *own* configuration for a fact that belongs to another actor gets the right answer in process, because "its own" configuration is everyone's. Only the Docker demos give each container its own configuration and expose the bug.

## Evidence

#1876 / PR #4539: the CaseActor seated the report receiver using its own `default_case_roles` (CP-09-007 as it then read). Every in-process test passed, including `TestRunTwoActorDemo::test_full_workflow_succeeds`. In Docker with the dedicated case-actor container, the four vendor-receiver scenarios failed with `CVDRole.VENDOR required for VF state`. Fixed by ADR-0133 (roles ride on the proposal).

This is a second witness for the ISSUE-2655 learning (`plan/incoming/learnings/20260930-2655-…`). That learning found the same class from the payload-completeness side: in-process seeding hides defects that only the Docker topology exposes.

## Why it matters

Any remaining read of `get_config()` or of the local store, on a CASE_MANAGER path, for a fact about a *different* actor is a defect of the same shape. The suite cannot find it, and Docker CI can find it only for the scenarios and configurations it happens to run.

## Possible directions (to plan, not decided)

- A ratchet listing the `get_config()` reads reachable from received-side CASE_MANAGER trees, each annotated as the executing actor's own setting.
- A multi-node in-process topology with distinct per-node configuration (needs `get_config` to be resolvable per app, not per process).

Where: test/demo/conftest.py

**Resolved**: 2026-11-16 — implementation tracked in #6537, #6538.
Docs PR: https://github.com/CERTCC/Vultron/pull/6536.
Notes: `notes/configuration.md`.
ADR: `docs/adr/0206-each-app-resolves-its-own-configuration.md` (proposed).
Finding: the #1876 read is already fixed (ADR-0133); the six remaining core config reads are each the executing node's own setting. The gap is detection: in-process apps share one config. Chosen: each app resolves its own AppConfig; a ratchet of config reads was rejected.
