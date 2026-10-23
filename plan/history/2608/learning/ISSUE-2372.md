---
title: CaseProposal loopback delivery blocked at depth > 0 in shared TestClient
type: learning
timestamp: 2026-08-19T18:30:00Z
source: ISSUE-2372
signal: concern
---

During implementation of issue #2372, the real CaseProposal round-trip
(`validate-report → Create(CaseProposal) → CaseActor → Accept + Create(VulnerabilityCase)`)
fails to complete in `TestRunTwoActorDemo.test_full_workflow_succeeds` because
the `_TestClientRouter` loopback delivery is blocked when all actors share the
same `api_app` TestClient portal (depth > 0 guard prevents deadlock).

This is already documented in the `_create_case_from_offer` test helper comment,
but there is no Concern issue tracking the limitation or a plan to resolve it.

The workaround is a test-level monkeypatch that replicates the equivalent RM
state transitions via the manual fallback. `TestDeliveryIsolation` covers the
real round-trip using isolated actor apps with separate portals.

Consider opening a Concern issue to track: (a) the exact blocking condition in
`anyio.to_thread.run_sync(client.post(...))` within the shared portal context,
and (b) whether `test_full_workflow_succeeds` should be migrated to use isolated
actor apps (like `TestDeliveryIsolation`) to exercise the full chain end-to-end.

**Promoted**: 2026-08-24 — captured in GitHub Concern #2533.
Docs PR: [PR URL TBD].
