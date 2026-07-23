---
source: CONCERN-1633
timestamp: '2026-07-23T14:36:11.030422+00:00'
title: 'Spec gap + code defect: CaseActor service URL must be explicit config, not
  derived from server_base_url'
type: learning
---

## Summary

The original concern was framed as a missing documentation invariant about where the CaseActor sub-actor is stored. After investigation, the real problem is deeper: `ResolveCaseActorUrlsNode` constructs the CaseActor identity by prepending the *running container's own base URL* to a case slug. This hard-wires a co-location assumption that is architecturally wrong — no actor should assume another actor shares its base URL. Actor URLs are opaque endpoint identifiers; whether they are host-local or host-remote is irrelevant to callers.

## Category

Spec Gap + Code Defect

## Severity

High

## Root Cause Analysis

`ResolveCaseActorUrlsNode` (`vultron/core/behaviors/case/nodes/case_setup.py`):

```python
server_base_url = _resolve_server_base_url(self.blackboard)
case_actor_id = f"{server_base_url}/actors/case-actor-{case_slug}"
```

This means the CaseActor sub-actor always lands on whichever container executes the BT. When a dedicated CaseActor container exists (as required by DEMOMA-12-001), the CaseProposal is addressed to the wrong endpoint.

## What Must Change

1. `ActorConfig` gains a `case_actor_service_url: HttpUrl | None = None` field
2. `ResolveCaseActorUrlsNode` reads from `ActorConfig`, not `server_base_url`
3. `specs/case-proposal.yaml` CP-08-001 through CP-08-003 added as invariants
4. `docker-compose-multi-actor.yml` supplies `VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL` for case-creating actors
5. `three_actor_demo.py` and `multi_vendor_demo.py` removed (superseded)

**Resolved**: 2026-07-23 — implementation tracked in #1640, #1641.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1639>.
Spec: `specs/case-proposal.yaml` CP-08-001 through CP-08-003.
Notes: `notes/case-proposal.md` § "CaseActor Service URL Configuration".
Notes: `notes/configuration.md` § "case_actor_service_url`.
