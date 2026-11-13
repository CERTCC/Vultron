#!/usr/bin/env python

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
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

"""Resolve the receiving actor before a received use case reads its store.

A handler that still reads the DataLayer before its tree runs (the reads
#6394 moves into the tree) resolves the receiver first, so a delivery with
no resolvable receiver raises as a wiring fault before any read rather than
being refused for what the read found (BT-17-009, ARCH-15-001).
"""

from typing import Protocol

from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.services.receiving_actor import resolve_receiving_actor_id


class _ReceivedRequest(Protocol):
    """A received event: it may name the actor it was delivered to."""

    @property
    def receiving_actor_id(self) -> str | None: ...


def resolve_receiver_before_reads(
    dl: CasePersistence, request: _ReceivedRequest
) -> str:
    """Return the receiving actor; call it just before the first store read.

    Place the call immediately before ``execute()``'s first DataLayer read.
    A refusal that reads only the request (a missing id) may come first: it
    reads no store, so it cannot report a fact of the wrong one.  The
    received-tree runner resolves the receiver again for the run, from the
    same inputs.

    Raises:
        VultronValidationError: Neither the request nor the DataLayer names
            a receiving actor (CM-01-001).
    """
    return resolve_receiving_actor_id(dl, request.receiving_actor_id)


__all__ = ["resolve_receiver_before_reads"]
