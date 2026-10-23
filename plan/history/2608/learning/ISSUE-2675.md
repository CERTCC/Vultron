---
title: "STATUS_AUTHORIZATION_PERMISSIVE injected via port-factory pattern in adapter, not demo layer"
type: learning
timestamp: "2026-08-28T14:40:00Z"
source: ISSUE-2675
signal: design-question
---

The issue specified flipping the `StatusAuthorizationCallOutBundle` defaults and adding `RequireCaseOwnerApprovalNode`, but left unspecified where the permissive bundle should be injected to keep the integration demo working.

**Decision made:** `STATUS_AUTHORIZATION_PERMISSIVE` lives in `vultron/core/` (not `vultron/demo/`), and is injected at the FastAPI adapter layer via two new port-factory functions (`_status_auth_trigger_port_factory`, `_status_auth_sync_trigger_port_factory`) wired into `make_dispatcher()`. The two status-receive semantics were moved from the shared trigger/sync-trigger sets into dedicated frozensets so the disjoint guard in `make_dispatcher()` catches any future overlap.

**Rationale:** The adapter layer is the natural configuration boundary between "what the core protocol enforces" and "what a given deployment is trusted to do." Placing `STATUS_AUTHORIZATION_PERMISSIVE` in core (not demo) keeps it importable from adapters without violating the no-core→demo import constraint. The port-factories pattern was already established for `SUBMIT_REPORT` and `CREATE_CASE_PROPOSAL` (both inject `ActorConfig`), so the same structure was used here.

**Implication for production deployments:** A production deployment wanting a live Offer/Accept/Reject round-trip would replace `_status_auth_trigger_port_factory` and `_status_auth_sync_trigger_port_factory` with factories that inject a custom `StatusAuthorizationCallOutBundle` whose gates implement the actual approval workflow.

## Audit disposition (2026-09-02)

Closed decision, no promotion owed (BW-07-008). The decision was made, applied, and shipped in its originating PR; the commit and PR body are its record. Archived without promotion.
