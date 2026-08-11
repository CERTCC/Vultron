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

"""Core state record for the domain facts carried in an ownership-transfer Offer.

Per ADR-0035 DL-06-002: every domain fact an actor must remember from a
received protocol message MUST be recorded as core state at extraction time.

``VultronOwnershipTransferOfferRecord`` captures the two domain facts that
core uses from the forwarded ``Offer(VulnerabilityCase)`` activity:

- ``offer_id``: the URI of the Offer activity (used as ``id_`` so that
  ``SvcAcceptCaseOwnershipTransferUseCase._prepare`` can look it up via
  ``dl.read(offer_id)``)
- ``object_``: the URI of the offered ``VulnerabilityCase`` (extracted from
  the ``object`` field of the snapshot; used by ``_as_id()`` in ``_prepare``
  to recover ``case_id``)

Populated by ``ApplyOfferOwnershipTransferFromLedgerNode`` on the SYNC
ledger-replication path (#2195, ISSUE-2195).
"""

from typing import Literal

from pydantic import Field, model_validator

from vultron.core.models.base import CoreObject, UriString


class VultronOwnershipTransferOfferRecord(CoreObject):
    """Core state record for the domain facts in an ownership-transfer Offer.

    Stored by ``ApplyOfferOwnershipTransferFromLedgerNode`` when a participant
    replica processes the ``offer_case_ownership_transfer`` ledger entry.

    ``id_`` is set to ``offer_id`` directly so that ``dl.read(offer_id)``
    finds this record — matching what the HTTP-inbox path stores for the
    same Offer via ``_idempotent_create``.
    """

    type_: Literal["VultronOwnershipTransferOfferRecord"] = Field(
        default="VultronOwnershipTransferOfferRecord",
        validation_alias="type",
        serialization_alias="type",
    )
    offer_id: UriString = Field(..., description="URI of the Offer activity")
    object_: str = Field(
        default="",
        description="URI of the offered VulnerabilityCase",
    )

    @model_validator(mode="after")
    def _set_id(self) -> "VultronOwnershipTransferOfferRecord":
        self.id_ = self.offer_id
        return self
