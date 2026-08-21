---
source: CONCERN-2323
timestamp: '2026-08-21T18:08:35.856880+00:00'
title: test infra config management footguns — _config_cache order sensitivity and
  _TestClientRouter silent drops
type: learning
---

## Two related test-infrastructure fragilities that obscure config leaks

### 1) `reload_config()` before `monkeypatch.undo()` leaks stale config

`vultron/config/app.py` holds a module-level `_config_cache`. `reload_config()`
re-reads the environment. `pytest`'s `monkeypatch` undoes environment changes in
fixture teardown **after** the requesting fixture's teardown body runs.

Calling `reload_config()` in a fixture teardown before `monkeypatch.undo()` fires
re-caches the still-patched fake values. The undo then runs too late. The re-cached
stale value persists into later tests, surfacing as flakiness that depends on test
execution order (and therefore looks random under `pytest-randomly`).

Four demo fixtures in `test/demo/` had this buggy order (issue #2086). An autouse
guard in `test/demo/conftest.py` contains the blast radius, but any **new** demo
fixture must explicitly follow `monkeypatch.undo(); reload_config()` order or it
will re-introduce the leak.

**Long-term fix**: expose config via a `config_override()` context manager in
`vultron/config/app.py` that owns both the env patch and cache invalidation
atomically. Specified as CFG-06-006, CFG-06-007.

### 2) `_TestClientRouter` silent drops mask unintentional misrouting

`_TestClientRouter.emit` in `test/demo/conftest.py` drops deliveries when no client
is registered for the recipient's base URL, logging only at `DEBUG`. This is
intentional for fictional external URLs (`https://vultron.example/...`) that must
not become real HTTP requests.

However, the same silence swallows *unintentional* misrouting. When a config leak
causes `Create(CaseProposal)` to be addressed to `http://coordinator-otc.test` — a
host no router registered — the delivery vanishes without a WARNING, the CaseActor
never creates the canonical case, and the failure surfaces three steps downstream as
`SvcValidateReportUseCase: no routable recipients`. Nothing in the output names the
actual cause.

**Suggested fix**: maintain a `_KNOWN_FICTIONAL_HOSTS` allowlist (e.g. `vultron.example`)
that keeps `DEBUG` logging. Anything outside the allowlist that is dropped should
log at `WARNING` — a `.test` host that was not registered is almost always a bug.

**Resolved**: 2026-08-21 — implementation tracked in #2475, #2476.
Docs PR: <https://github.com/CERTCC/Vultron/pull/2474>.
Spec: `specs/configuration.yaml` CFG-06-006, CFG-06-007.
Notes: `notes/configuration.md`.
