---
source: TASK-OUTBOX-TO
timestamp: '2026-05-04T19:04:30.694877+00:00'
title: Outbox Integrity Enforcement (Priority 475, TASK-OUTBOX-TO)
type: priority
---

TASK-OUTBOX-TO is complete: VultronOutboxToFieldMissingError added to vultron/errors.py, enforced in handle_outbox_item (outbox_handler.py lines 232-253). The to: field is now validated at handle_outbox_item before any activity leaves the outbox. WARNING is logged when cc/bto/bcc are non-empty. CC violation on handle_outbox_item CC=11 is a follow-on and tracked under CC.2.
