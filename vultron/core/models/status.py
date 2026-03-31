"""Status models for Vultron Protocol domain objects.

This module belongs to the core domain layer.
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

from enum import StrEnum

from pydantic import BaseModel, Field


class OfferStatusEnum(StrEnum):
    """Enumeration of Offer Statuses"""

    RECEIVED = "RECEIVED"
    ACCEPTED = "ACCEPTED"
    TENTATIVELY_REJECTED = "TENTATIVELY_REJECTED"
    REJECTED = "REJECTED"


class ObjectStatus(BaseModel):
    """Represents the status of an object being tracked in the Vultron Protocol."""

    object_type: str = Field(
        description="The type of the object whose status is being represented. Taken from the type_ field of the object.",
    )
    object_id: str = Field(
        description="The ID of the object whose status is being represented. Taken from the id_ field of the object."
    )
    actor_id: str | None = Field(
        default=None,
        description="The actor to whom this status is relevant, if applicable.",
    )
    status: str  # replace with a StrEnum in subclasses


class OfferStatus(ObjectStatus):
    """Represents the status of an Offer object."""

    status: OfferStatusEnum = Field(
        default=OfferStatusEnum.RECEIVED,
        description=f"The status of the Offer. Possible values are: {', '.join([s.name for s in OfferStatusEnum])}.",
    )
