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

"""Core state record capturing the domain facts from a submitted report Offer.

Per ADR-0035 DL-06-002: every domain fact an actor must remember from a
received protocol message MUST be recorded as core state at extraction time.
Core MUST NOT reconstruct such a fact by re-reading the stored activity later.

``VultronOfferRecord`` captures the three domain facts that core uses from the
Offer(VulnerabilityReport) wire activity:

- ``report_id``: the URI of the embedded ``VulnerabilityReport``
- ``offer_actor_id``: the URI of the actor that submitted the report (used for
  fallback addressing when no case is found)
- ``offer_to``: the original ``to`` field of the Offer (used to compute
  ``CreateCaseActivity`` addressees)

The record is keyed deterministically by ``offer_id`` via :meth:`build_id`,
so core can look it up given only the offer ID.
"""

import urllib.parse
from typing import Literal

from pydantic import Field, model_validator

from vultron.core.models.base import UriString, VultronObject


class VultronOfferRecord(VultronObject):
    """Core state record for the domain facts carried in a report Offer.

    Stored by the adapter layer (``TriggerActivityAdapter.submit_report``)
    immediately after the Offer activity is created.  Core reads this record
    instead of re-reading the stored wire Offer activity.
    """

    type_: Literal["OfferRecord"] = Field(
        default="OfferRecord",
        validation_alias="type",
        serialization_alias="type",
    )
    offer_id: UriString = Field(..., description="URI of the Offer activity")
    report_id: UriString = Field(
        ..., description="URI of the embedded VulnerabilityReport"
    )
    offer_actor_id: UriString = Field(
        ..., description="URI of the actor that submitted the Offer"
    )
    offer_to: list[str] = Field(
        default_factory=list,
        description="'to' recipients from the original Offer",
    )

    @classmethod
    def build_id(cls, offer_id: str) -> str:
        """Return the stable DataLayer ID for *offer_id*."""
        slug = urllib.parse.quote(offer_id, safe="")
        return f"offer-record/{slug}"

    @model_validator(mode="after")
    def _set_id(self) -> "VultronOfferRecord":
        """Compute ``id_`` deterministically from ``offer_id``."""
        self.id_ = self.build_id(self.offer_id)
        return self
