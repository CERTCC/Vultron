---
source: ISSUE-1779
timestamp: '2026-07-29T15:24:34.960882+00:00'
title: Route cross-actor test delivery through TestClient
type: implementation
---

## Issue #1779 — Route cross-actor test delivery through TestClient (drop hand-rolled ASGITransport)

Rewired the isolated multi-actor demo test harness (`test/demo/conftest.py`) to
route cross-actor delivery through each target actor's FastAPI `TestClient`
inbox instead of a hand-rolled `httpx.ASGITransport`, per ADR-0042 /
`outbox.yaml` OX-12-003.

- `_TestASGIRouter` → `_TestClientRouter`; `emit()` POSTs to the target
  `TestClient` inbox, offloading the blocking call via
  `anyio.to_thread.run_sync` to avoid a same-portal deadlock on CaseActor
  `cc:`-to-self loopback delivery.
- `register()` now takes a `TestClient`; all call sites updated.
- `serialize_as_any=True` preserved (no SYNC-02-004 / SYNC-13-004 regression).
- No test module constructs `httpx.ASGITransport` (AC-2 grep-clean).
- Full suite green: 6576 passed, 265 skipped, 3 xfailed.

PR: <https://github.com/CERTCC/Vultron/pull/1796>
