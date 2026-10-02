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

"""Durable marker for a pending ``Create(VulnerabilityCase)`` obligation.

The ``PendingCreateCaseActivity`` record is written to the DataLayer after
``Accept(CaseProposal)`` has been sent but *before* the
``Create(VulnerabilityCase)`` delivery is attempted.  If delivery of
``Create(VulnerabilityCase)`` fails (or the process crashes between the two
sends), the marker persists so that a retry runner (#1139) can discover the
unfulfilled obligation and complete it.

Spec: ``specs/case-proposal.yaml`` CP-05-005.
"""

import urllib.parse
import uuid
from typing import Any, Literal

from pydantic import Field, model_validator

from vultron.core.models.base import CoreRecord, NonEmptyString, UriString


class PendingCreateCaseActivity(CoreRecord):
    """Durable marker recording a pending ``Create(VulnerabilityCase)`` obligation.

    The marker stores the minimum information needed to reconstruct and
    re-deliver the ``Create(VulnerabilityCase)`` activity without re-running
    the full BT tree.

    Attributes:
        proposal_id: URI of the ``as_CaseProposal`` that was accepted.
            Used as the stable key component for ``build_id()``.
        case_actor_id: URI of the case-actor service that issued the
            ``Accept(CaseProposal)`` and owns the ``Create(VulnerabilityCase)``
            obligation.
        vendor_uri: URI of the report receiver (the CASE_OWNER) to whom
            ``Create(VulnerabilityCase)`` must be delivered.
        create_activity_payload: Pre-constructed
            ``Create(VulnerabilityCase)`` payload as a plain dict
            (the ``WireRenderPort`` rendering).  The retry runner (#1139)
            reconstructs the activity from this dict rather than rebuilding
            it from scratch.

    Spec: CP-05-005.
    """

    type_: Literal["PendingCreateCaseActivity"] = Field(  # type: ignore[assignment]
        default="PendingCreateCaseActivity",
        validation_alias="type",
        serialization_alias="type",
    )
    proposal_id: UriString = Field(
        ..., description="URI of the CaseProposal that was accepted"
    )
    case_actor_id: UriString = Field(
        ..., description="URI of the case-actor service sending the Create"
    )
    vendor_uri: UriString = Field(
        ...,
        description="URI of the report receiver owed Create(VulnerabilityCase)",
    )
    create_activity_payload: dict[NonEmptyString, Any] = Field(
        default_factory=dict,
        description=(
            "Pre-constructed Create(VulnerabilityCase) payload "
            "(its WireRenderPort AS2 rendering) for retry use"
        ),
    )

    @classmethod
    def build_id(cls, proposal_id: str) -> str:
        """Return the stable DataLayer ID for *proposal_id*."""
        slug = urllib.parse.quote(proposal_id, safe="")
        return f"pending-create-case/{slug}"

    @classmethod
    def create_activity_id(cls, proposal_id: str) -> str:
        """Return the id of the ``Create(VulnerabilityCase)`` answering
        *proposal_id*.

        Derived from the proposal rather than minted, so a redelivered
        proposal names the activity its first delivery announced.  The marker
        is deleted once that Create is queued, so this id is how a later
        delivery tells the case was already announced (CP-05-005, #4146).
        """
        name = f"{proposal_id}#create-case"
        return f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, name)}"

    @model_validator(mode="before")
    @classmethod
    def _set_id(cls, data: Any) -> Any:
        """Compute ``id_`` deterministically from ``proposal_id``."""
        if isinstance(data, dict):
            proposal_id = data.get("proposal_id")
            if proposal_id is not None:
                data = dict(data)
                data["id"] = cls.build_id(proposal_id)
        return data


__all__ = ["PendingCreateCaseActivity"]
