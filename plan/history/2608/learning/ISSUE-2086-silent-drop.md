---
title: "_TestClientRouter silently drops unroutable deliveries, masking config leaks as flaky failures"
type: learning
timestamp: "2026-08-08T00:00:00Z"
source: ISSUE-2086-silent-drop
signal: concern
---

`_TestClientRouter.emit` (`test/demo/conftest.py`) drops a delivery when no
client is registered for the recipient's base URL, logging only at `DEBUG`:

```python
client = self._clients.get(base)
if client is None:
    logger.debug("... dropping delivery to %s", recipient_id)
    continue
```

This is deliberate — demo tests address fictional external URLs
(`https://vultron.example/users/...`) that must not become real HTTP requests
(#527). But the same silence swallows *unintentional* misrouting.

In #2086 a leaked `VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL` caused every
subsequent demo test's `Create(CaseProposal)` to be addressed to
`http://coordinator-otc.test` — a host no router registered. The delivery
vanished, the CaseActor never created the canonical case, and the failure
surfaced three steps downstream as `SvcValidateReportUseCase: no routable
recipients`. Nothing in the failure output named the actual cause.

**Why this cost time**: the observable symptom pointed at
`_compute_report_addressees` (a fail-closed routing check in production code)
rather than at test infrastructure. An initial hypothesis of an async race in
the CaseActor proposal chain was wrong, and a candidate production fix that
made `_compute_report_addressees` fall through to the offer actor broke the
fail-closed invariant from issue #1854 AC-2, asserted by
`test_close_report_raises_when_case_exists_without_case_manager`. Only reading
the CI logs (delivery target `coordinator-otc.test`, a string appearing in
exactly one test module) identified the real cause.

**Suggested follow-up**: distinguish expected drops from unexpected ones —
e.g. an allowlist of known-fictional hosts (`vultron.example`) that keeps
`DEBUG`, with anything else logged at `WARNING`. A dropped delivery to a
`.test` host that a sibling module registers is almost always a bug.

**Related**: the config-cache leak itself (`reload_config()` before
`monkeypatch.undo()`) is fixed at the source in four demo modules plus an
autouse guard in `test/demo/conftest.py`.

**Promoted**: 2026-08-17 — captured in GitHub #2323 (Concern: test infra config management footguns).
Docs PR: <https://github.com/CERTCC/Vultron/pull/2330>0>0>0>0>0>0>0>0>0>.
