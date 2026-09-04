"""Factory functions for ProcessingFault protocol activities.

Provides :func:`create_processing_fault_activity` for building the
``Create(ProcessingFault)`` NACK message (ADR-0080, ASK-07-001).
"""

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

from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Create
from vultron.wire.as2.vocab.objects.processing_fault import as_ProcessingFault


def create_processing_fault_activity(
    actor: str,
    fault: as_ProcessingFault,
    to: list[str] | None = None,
) -> as_Create:
    """Build a ``Create(ProcessingFault)`` NACK activity.

    Args:
        actor: URI of the receiving actor emitting the fault.
        fault: The ``as_ProcessingFault`` object describing the failure.
        to: Recipient URI list; SHOULD contain the original sender's URI.

    Returns:
        An ``as_Create`` activity wrapping the ``as_ProcessingFault``.
    """
    return as_Create(
        actor=actor,
        object_=fault,
        to=to,
    )
