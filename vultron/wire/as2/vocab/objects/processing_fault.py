"""Wire-layer vocabulary type for the ProcessingFault protocol message.

Provides :class:`as_ProcessingFault`, the AS2 Object type used in the
``Create(as_ProcessingFault)`` NACK message flow defined in ADR-0080.

A receiver emits ``Create(ProcessingFault)`` to an authenticated sender when
it cannot process the sender's status assertion (ASK-07-001).

Spec: ``specs/protocol-asks.yaml`` ASK-07-001 through ASK-07-006.
"""

# pyright: reportGeneralTypeIssues=false

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

from pydantic import Field

from vultron.core.models.base import NonEmptyString
from vultron.core.models.enums import VultronObjectType as VO_type
from vultron.wire.as2.vocab.objects.base import VultronAS2Object


class as_ProcessingFault(VultronAS2Object):
    """Wire representation of a ProcessingFault NACK object (ASK-07-001).

    Emitted by a receiver toward an authenticated sender when a status
    assertion activity could not be processed (ADR-0080).

    Per ASK-07-004: ``in_reply_to`` carries a pointer to the failed activity
    URI; the failed activity is never echoed inline.
    Per ASK-07-005: ``failure_class`` is a URI under the Vultron namespace.
    Per ASK-07-006: no implementation diagnostics are included.

    Fields:
        type_: Always ``"ProcessingFault"``; registered in ``VultronObjectType``.
        failure_class: Required URI identifying the failure class (ASK-07-003).
        in_reply_to: Optional URI of the failed activity (ASK-07-004).
    """

    type_: VO_type = Field(
        default=VO_type.PROCESSING_FAULT,
        validation_alias="type",
        serialization_alias="type",
    )

    failure_class: NonEmptyString = Field(
        ...,
        validation_alias="failureClass",
        serialization_alias="failureClass",
        description="URI identifying the failure class (ASK-07-003).",
    )

    in_reply_to: NonEmptyString | None = Field(
        default=None,
        validation_alias="inReplyTo",
        serialization_alias="inReplyTo",
        description="URI of the failed activity (ASK-07-004).",
    )
