---
title: Outbox Delivery Reliability
status: active
description: >
  Implementation guidance for the outbox delivery reliability hardening tasks:
  per-activity abort scope, 4xx terminal classification, timeout/jitter/pool
  configuration, and per-activity attempt counter with dead-letter store.
related_specs:
  - specs/outbox.yaml
  - specs/sync-ledger-replication.yaml
related_issues:
  - https://github.com/CERTCC/Vultron/issues/2302
relevant_packages:
  - vultron/adapters/driven/http_delivery.py
  - vultron/adapters/driving/fastapi/outbox_handler.py
---

# Outbox Delivery Reliability

Implementation guidance for CONCERN-2302 remediation. See ADR-0066 for the
architectural rationale and option analysis.

---

## Root Cause Summary (CONCERN-2302 §7 resolution)

`outbox_handler.py`'s `err_count > 3: break` does **not** silently drop outbox
entries — `outbox_pop()` removes the item and `outbox_append()` re-queues it before
the break. The liveness failure is: when the first *N* items in the queue all fail
in the same drain pass, `err_count` hits 4 before later (non-failing) activities are
reached. Critical ledger-entry deliveries for healthy recipients are delayed past the
scenario timeout. Severity: **liveness/performance failure**, not data-integrity loss.

---

## Task AB — Abort-scope isolation + 4xx terminal classification

**Files:** `vultron/adapters/driving/fastapi/outbox_handler.py`,
`vultron/adapters/driven/http_delivery.py`

### Abort scope fix

Replace the single `err_count` variable (function-local, shared across all
activities in a drain pass) with a per-activity approach:

```python
# BEFORE (outbox_handler.py ~L243)
err_count = 0
while dl.outbox_list():
    activity_id = dl.outbox_pop()
    ...
    except Exception as e:
        dl.outbox_append(activity_id)
        err_count += 1
        if err_count > 3:
            break

# AFTER
activity_err_counts: dict[str, int] = {}  # declared OUTSIDE the while loop
while dl.outbox_list():
    activity_id = dl.outbox_pop()
    ...
    except Exception as e:
        dl.outbox_append(activity_id)
        activity_err_counts[activity_id] = activity_err_counts.get(activity_id, 0) + 1
        per_err = activity_err_counts[activity_id]
        if per_err > 3:
            # Break only when every remaining item is also capped.
            if all(activity_err_counts.get(i, 0) > 3 for i in dl.outbox_list()):
                break
            continue  # skip this activity for this pass, process others
        backoff = (2 ** (per_err - 1)) + random.uniform(0, 0.5)
        await asyncio.sleep(backoff)
```

The per-activity dict is declared **outside** the while loop so error counts
persist across queue iterations within a drain pass. `continue` replaces `break`
so other activities in the queue are unaffected. Break fires only when every
remaining item in the queue has also hit its per-pass cap (OX-13-006).

**Spec:** OX-13-006.

### 4xx terminal classification

In `_deliver_with_retry`, catch `httpx.HTTPStatusError` before the generic
`Exception` handler and raise `DeliveryError` immediately on 4xx:

```python
# In _deliver_with_retry, inside the for-attempt loop:
try:
    response = await client.post(...)
    response.raise_for_status()
    ...
    return
except httpx.HTTPStatusError as exc:
    if 400 <= exc.response.status_code < 500:
        # Terminal: 4xx will never succeed with the same payload
        logger.error(
            "Terminal delivery failure (HTTP %d) for activity %s to %s"
            " — not retrying (OX-13-005)",
            exc.response.status_code, activity_id, inbox_url,
        )
        raise DeliveryError([recipient_id], activity_id) from exc
    # 5xx: fall through to retry logic below
    exc_to_log = exc
except Exception as exc:
    exc_to_log = exc
# ... existing retry/backoff code
```

**Spec:** OX-13-005.

**Tests:**

- `test/adapters/driving/fastapi/test_outbox_handler.py`: add a test that a
  failing activity does not delay healthy activities in the same pass (AC-3).
- `test/adapters/driven/test_delivery_backoff.py`: add tests for 4xx-terminal and
  5xx-retryable paths.

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

## Task D — Per-activity attempt counter + dead-letter store ✅ IMPLEMENTED

**Implemented in PR #2371 (2026-08-19). See ADR-0066.**

**Implementation files:**

- `vultron/adapters/outbox_dead_letter.py` — `OutboxDeadLetterEntry` model and
  `OutboxRetryStore` Protocol (adapter layer, not core port)
- `vultron/adapters/driven/datalayer_sqlite/queues.py` — `get_outbox_attempt_count`,
  `set_outbox_attempt_count`, `clear_outbox_attempt_count`, `dead_letter_append`,
  `dead_letter_list`
- `vultron/adapters/driven/datalayer_sqlite/schema.py` — `OutboxAttemptEntry` SQLModel
  table (`vultron_outbox_attempts`)
- `vultron/adapters/driving/fastapi/outbox_handler.py` — `MAX_TOTAL_ATTEMPTS = 12`,
  exhaustion branch, `cast(OutboxRetryStore, dl)` pattern
- `test/adapters/driven/test_sqlite_outbox_dead_letter.py` — 13 tests (OX-13-001–004)
- `test/adapters/driving/fastapi/test_outbox_handler.py` — 4 new handler tests

**Design choices (supersedes guidance above):**

- Side-table approach used (`OutboxAttemptEntry` SQLModel, `vultron_outbox_attempts`),
  keeping queue API unchanged.
- `OutboxRetryStore` is an adapter-level Protocol; `SqliteDataLayer` satisfies it
  structurally. `outbox_handler` uses `cast(OutboxRetryStore, dl)` to access the
  delivery-infrastructure methods without polluting the core `CasePersistence` /
  `CaseOutboxPersistence` ports. (This said `ActorScopedDataLayer`; that protocol
  refinement was deleted by ADR-0073 — no DataLayer is unscoped, so there was
  nothing left for it to distinguish.)
- `MAX_TOTAL_ATTEMPTS = 12` is a module-level constant (not constructor-configurable).
- Counter is cleared when an activity is dead-lettered (OX-13-002) so the side-table
  does not accumulate stale rows.

**Remaining open items:**

- Protocol-level NACK on exhaustion (ADR-0066 Option C) still deferred to #1880.

---

## Coordination Notes

- **#2202 AC-7**: that issue consolidates demo-side timeout constants. Once
  `HttpDeliveryAdapter.timeout` is configurable (Task C), #2202 can set it from
  a single config source rather than the hardcoded 5 s.
- **#1880**: inbound unprocessable activities — the analogous inbound terminal-state
  question. ADR-0066 defers the protocol-level NACK to that issue; the dead-letter
  store model should be unified when #1880 is planned.
- **OX-12-001**: HTTP-only delivery (ADR-0042) is not in question. All changes here
  are about the reliability envelope, not the delivery mechanism.
