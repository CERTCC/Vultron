---
source: NOTES-outbox-delivery-reliability--task-ab
timestamp: '2026-09-17T17:32:39.076142+00:00'
title: Task AB — Abort-scope isolation + 4xx terminal
type: note
---

**Archived:** 2026-09-17
**Reason:** (a) delivered
**Superseded by:** outbox_handler.py activity_err_counts; http_delivery.py 4xx terminal

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
