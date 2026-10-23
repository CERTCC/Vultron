---
title: Outbox Notes
status: active
kind: guidance
description: >
  Rules for outbox addressing enforcement (OX-08), the structure of
  `handle_outbox_item`, and the test coverage every delivery change carries.
related_specs:
  - specs/outbox.yaml
related_notes:
  - notes/outbox-delivery-reliability.md
  - notes/case-communication-model.md
  - notes/architecture-adapters.md
  - notes/wire-artifact-immutability.md
relevant_packages:
  - fastapi
  - vultron/adapters/driving/fastapi
---

# Outbox Notes

Delivery ordering, retry, and dead-lettering are in
[outbox-delivery-reliability](outbox-delivery-reliability.md).

## Addressing Is `to:` Only (OX-08)

Every outbound Vultron activity is a direct message and MUST carry a non-empty `to:`
(OX-08-001/002); an empty list is as bad as `None`. `handle_outbox_item` refuses one
without it with `VultronOutboxToFieldMissingError` (`vultron/errors.py`). Any
`cc`/`bto`/`bcc` logs a WARNING with no exemption, including a copy naming the sender:
the emitting tree commits its own entry, so no outbound activity addresses its own
sender (OX-08-004, ADR-0109).

---

## `handle_outbox_item` Orchestrates Named Helpers

`handle_outbox_item()` (`vultron/adapters/driving/fastapi/outbox_handler.py`) only
sequences named helpers (`_load_sealed_body`, `_validate_to_field`,
`_warn_secondary_addressing`, `_validate_inline_object` in `outbox_delivery.py`;
`_extract_recipients` in `outbox_addressing.py`). A new `OX-*` or `MV-*` outbox
requirement is a new `_<action>_<subject>` helper called from it, never inline logic, so
each protocol check stays independently reviewable and testable.

**A helper guards or refuses; it never repairs.** The handler is a dumb relay
(VM-08-003, OX-07-001): it delivers the body the emitting adapter sealed
(`vultron/adapters/outbox_sealed_body.py`) and reads nothing else. Expansion,
re-typing, or hydration helpers make the wire disagree with the ledger; do not add one.
See `notes/wire-artifact-immutability.md` § "How the blob reaches delivery".

---

## Every Delivery Change Carries Targeted Unit Tests

A change to recipient routing, the sealed-body relay, or activity validation in the
outbox handler MUST add or update the unit test for that behavior, because a delivery
regression is silent message loss (#653):

| Behavior | Tests |
|---|---|
| Recipient extraction and dedup | `test/adapters/driving/fastapi/test_outbox_helpers.py` |
| Sealed body reaches the emitter byte for byte; a missing sealed body is dropped with an ERROR | `test_outbox_handle_item_delivery.py`, `test_outbox_sealed_body_delivery.py` |
| `to:` refusal, secondary-addressing warning, inline-object integrity | `test_outbox_handle_item_validation.py` |

Multi-actor behavior is covered by the demo suites, not these unit tests. A change that
modifies an existing test says why in the commit message.
