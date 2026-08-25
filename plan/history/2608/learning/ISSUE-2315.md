---
title: Per-activity outbox error counter requires a dict outside the while loop, not a reset-per-iteration variable
type: learning
timestamp: '2026-08-18T00:00:00+00:00'
source: ISSUE-2315
signal: design-question
---

## Decision

`notes/outbox-delivery-reliability.md` Task AB shows pseudocode with
`per_activity_err = 0` *inside* the `while dl.outbox_list():` block:

```python
while dl.outbox_list():
    activity_id = dl.outbox_pop()
    per_activity_err = 0        # <-- resets every iteration
    ...
    except Exception as e:
        per_activity_err += 1
        if per_activity_err > 3:
            continue
```

This never fires: `per_activity_err` resets to 0 at the top of each iteration,
so it can only ever reach 1 per iteration, never exceeding the cap of 3.

## Correct Implementation

Use a dict keyed by activity ID, declared *outside* the while loop:

```python
activity_err_counts: dict[str, int] = {}
while dl.outbox_list():
    activity_id = dl.outbox_pop()
    try:
        ...
    except Exception as e:
        activity_err_counts[activity_id] = activity_err_counts.get(activity_id, 0) + 1
        per_err = activity_err_counts[activity_id]
        if per_err > 3:
            # Terminate only when ALL remaining queue entries are also capped
            if all(activity_err_counts.get(i, 0) > 3 for i in dl.outbox_list()):
                break
            continue
        backoff = (2 ** (per_err - 1)) + random.uniform(0, 0.5)
        await asyncio.sleep(backoff)
```

The all-capped termination guard is required: without it, a single
permanently-failing activity is re-queued and re-popped forever, producing an
infinite loop.

## Implication

The pseudocode in `notes/outbox-delivery-reliability.md` should be updated to
reflect the correct implementation before the next implementation of Task C/D.

**Promoted**: 2026-08-24 — captured in archive only (stale, already in notes).
Docs PR: [PR URL TBD].
