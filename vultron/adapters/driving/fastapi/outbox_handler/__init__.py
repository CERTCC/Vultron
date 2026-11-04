#!/usr/bin/env python

#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University
"""
Provides an outbox handler for Vultron Actors.

Implements OX-1.1 (local/remote delivery via HTTP POST), OX-1.2
(background delivery after inbox processing), and partial OX-1.3
(delivery failures are isolated per-recipient) from ``specs/outbox.yaml``.

One drain runs per actor outbox at a time (OX-01-004), and within a drain
rows are delivered in per-recipient lanes (OX-01-005, OX-01-006, ADR-0112;
see ``outbox_lanes.py``).  Every inbound activity's background task and the
``OutboxMonitor`` call :func:`outbox_handler`; before ADR-0112 those calls
drained one FIFO concurrently and a recipient could see rows complete in any
order, which is what turned a ledger fan-out into a Reject/replay storm
(#3602, #3033, #2898).

OX-1.3 idempotency is enforced at the receiving inbox endpoint
(``POST /actors/{id}/inbox/``) rather than at delivery time, because actors
run as isolated processes with no direct access to each other's DataLayers.

The handler is a dumb relay (VM-08-003, ADR-0074): each row's *sealed body*
— the JSON text the emitting adapter produced and stored alongside the
activity — is delivered exactly as sealed.  Nothing here reads the activity
record back, expands a reference, hydrates an object, or re-serialises.  That
is what keeps the ledger's ``payloadSnapshot`` and the wire identical.

The handler itself is a package grouped by concern (CS-18-005):

- ``drain`` — the locked per-actor drain, per-row delivery and the default
  emitter
- ``bookkeeping`` — attempt budgets and the dead letter

Helper concerns live in sibling modules:

- ``outbox_addressing`` — recipient extraction from the parsed body
- ``outbox_delivery`` — sealed-body loading and last-resort guards

Tests that stub per-row delivery patch the name where the drain looks it up:
``monkeypatch.setattr(drain, "handle_outbox_item", …)`` on
``outbox_handler.drain``.
"""

from vultron.adapters.driving.fastapi.outbox_handler.bookkeeping import (
    MAX_PER_PASS_ATTEMPTS,
    MAX_TOTAL_ATTEMPTS,
    UNDELIVERABLE_BODY_ERRORS,
)
from vultron.adapters.driving.fastapi.outbox_handler.drain import (
    configure_default_emitter,
    get_default_emitter,
    handle_outbox_item,
    outbox_handler,
)

__all__ = [
    "MAX_PER_PASS_ATTEMPTS",
    "MAX_TOTAL_ATTEMPTS",
    "UNDELIVERABLE_BODY_ERRORS",
    "configure_default_emitter",
    "get_default_emitter",
    "handle_outbox_item",
    "outbox_handler",
]
