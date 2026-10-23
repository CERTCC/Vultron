---
title: "inbox_handler._process_inbox_item re-queues VultronProtocolViolationError indefinitely"
type: learning
timestamp: "2026-08-31T14:28:32Z"
source: ISSUE-2861
signal: concern
---

`vultron/adapters/driving/fastapi/inbox_handler.py` `_process_inbox_item` (line ~347) uses
`except Exception` which catches `VultronProtocolViolationError` and re-queues the item.

`err_count=3` bounds retries **per call** only — the counter resets on every poll cycle,
so a malformed message that raises `VultronProtocolViolationError` causes infinite retries
across poll cycles.

**Why:** Identified during sibling scan for PR fixing #2861/#2766/#2767. `inbox_handler` is
being phased out by `InboxPipeline` (ADR-0020), but the handler is still active in production.

**How to apply:** Tracked as Bug #2865. When touching `inbox_handler._process_inbox_item`,
add a `VultronProtocolViolationError` catch before the generic `except Exception` that does
NOT re-queue (permanent failure path). See `InboxPipeline.process()` for the reference
implementation.

Related: [[feedback-inbox-pipeline-exception-ordering]], [[project-inbox-pipeline-migration]]

## Audit disposition (2026-09-02)

Tracked as #2861.
