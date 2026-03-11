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

"""
DeliveryQueue port — the outbound activity delivery interface used by
the core domain layer.

Concrete implementations live in the adapter layer at
``vultron/adapters/driven/delivery_queue.py``.

No adapter-layer types appear here.
"""

from typing import Protocol


class DeliveryQueue(Protocol):
    """Protocol for an outbound activity delivery queue.

    Defines the minimum interface that any concrete delivery adapter must
    satisfy.  The core layer calls ``enqueue`` to schedule delivery of an
    outbound activity to one or more recipients; ``drain`` processes all
    pending items.
    """

    def enqueue(self, activity_id: str, recipient_id: str) -> None:
        """Schedule delivery of ``activity_id`` to ``recipient_id``.

        The activity is identified by its URI; the adapter resolves
        the full object from the ``DataLayer`` when it processes the item.
        """
        ...

    def drain(self) -> int:
        """Deliver all pending queue items.

        Returns the number of items successfully delivered.
        """
        ...
