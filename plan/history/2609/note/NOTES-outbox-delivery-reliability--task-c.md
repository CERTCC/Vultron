---
source: NOTES-outbox-delivery-reliability--task-c
timestamp: '2026-09-17T17:32:39.341850+00:00'
title: Task C — Timeout, jitter, connection-pool
type: note
---

**Archived:** 2026-09-17
**Reason:** (a) delivered
**Superseded by:** http_delivery.py DEFAULT_DELIVERY_TIMEOUT + jitter + pool limits (SYNC-05-004)

---

## Task C — Timeout, jitter, and connection-pool configuration

**File:** `vultron/adapters/driven/http_delivery.py`

### Timeout as constructor parameter (SYNC-05-004)

Add `timeout` to `HttpDeliveryAdapter.__init__`:

```python
DEFAULT_DELIVERY_TIMEOUT: float = 30.0  # module-level constant

class HttpDeliveryAdapter:
    def __init__(
        self,
        max_retries: int = DEFAULT_MAX_RETRIES,
        initial_delay: float = DEFAULT_INITIAL_DELAY,
        backoff_multiplier: float = DEFAULT_BACKOFF_MULTIPLIER,
        max_delay: float = DEFAULT_MAX_DELAY,
        timeout: float = DEFAULT_DELIVERY_TIMEOUT,
    ) -> None:
        ...
        self._timeout = timeout
```

Pass `self._timeout` to `client.post(..., timeout=self._timeout)` in
`_deliver_with_retry`.

### Jitter in inner retry

Add `random.uniform(0, 0.5)` before `asyncio.sleep` in `_deliver_with_retry`:

```python
jitter = random.uniform(0, 0.5)
await asyncio.sleep(delay + jitter)
```

This matches the formula already used in `outbox_handler.py:265` and
desynchronises retry waves from fan-out failures.

### Connection-pool limits

Construct `httpx.AsyncClient` with explicit limits in `emit()`:

```python
limits = httpx.Limits(max_connections=20, max_keepalive_connections=5)
async with httpx.AsyncClient(limits=limits) as client:
    ...
```

Default httpx pool is 100 connections. Under fan-out to 6 actors with all failing,
100 × 3 retry slots = 300 potential concurrent connections. `max_connections=20`
bounds pool growth while still supporting normal multi-actor fan-out.

**Tests:** `test/adapters/driven/test_delivery_backoff.py` — add tests confirming
the timeout parameter flows through and jitter is applied.

---
