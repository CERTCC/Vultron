---
title: "TASK-OUTBOX-TO: Outbox to: Field Enforcement"
type: implementation
timestamp: '2026-04-30T19:55:29+00:00'

source: TASK-OUTBOX-TO
---

## TASK-OUTBOX-TO — Outbox `to:` Field Enforcement

Added `VultronOutboxToFieldMissingError` to `vultron/errors.py` and enforced
the `to:` presence check in `handle_outbox_item` before the object-expansion
block. Activities with a `None` or empty-list `to:` raise the new error
immediately; activities with non-empty `cc`/`bto`/`bcc` log a WARNING but
still deliver. Added 6 new unit tests in `test/adapters/driving/fastapi/test_outbox.py`
covering both raise branches (None and []) and the three warning branches
(cc, bto, bcc), including assertions on exception attributes. Fixed one
pre-existing test that built a `VultronActivity` without a `to:` field
(`test_handle_outbox_item_raises_on_bare_string_object`).
Specs satisfied: OX-08-001, OX-08-002, OX-08-003, OX-08-004.
