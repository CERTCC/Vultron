---
title: test_communication.py::test_queues_offer_and_writes_activity_id is order-dependent on ActorConfig env
type: learning
timestamp: "2026-07-30T22:15:00+00:00"
source: ISSUE-1777-d
signal: tooling-issue
---

`test/core/behaviors/case/nodes/test_communication.py::TestSendOfferCaseManagerRoleNode::test_queues_offer_and_writes_activity_id`
fails when that file is run alone or in a small subset, with
`ResolveCaseActorUrlsNode: case_actor_service_url is not configured in
ActorConfig (set VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL)` and then
`AssertionError: CreateCaseActorNode must write case_actor_id`. It passes in the
full-suite run. Reproduced on a clean stashed base, so it is pre-existing and
unrelated to #1777.

**Why:** The test depends on `VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL` being set by
some other test's fixture rather than establishing it itself, so it is
order-dependent. That makes subset runs (the normal way to iterate on a change)
report a false failure and costs time proving it is not yours.

**How to apply:** If this test fails during a targeted run, verify against a
clean base before investigating your own diff. The real fix is for the test to
set the ActorConfig env/monkeypatch in its own fixture — worth a Concern issue if
it bites again. Related: [[feedback_completeness_doctrine]] § Finding Severity on
pre-existing-failure proof.

**Promoted**: 2026-07-31 — captured in `notes/bt-pitfalls.md` (test order-dependence note). GitHub concern: #1897.
Docs PR: TBD.
