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

"""Durable record that a ``Create(as_CaseProposal)`` was declined.

The admission decision writes the record and queues the
``Reject(as_CaseProposal)`` in one transaction (``RefusalActTransaction``,
CLP-07-015), so the store holds both or neither.  Two properties depend on it:

- **The decision is terminal.** Once the record exists, a later delivery of
  the proposal finds it and neither re-adjudicates nor runs the accept path.
- **Redelivery is idempotent.** A retrying proposer is not sent a new
  ``Reject`` each time, and a stateful or stochastic backend cannot accept what
  it previously refused (CP-05-006 applies the same rule to the accept side).

``reject_activity_id`` names the ``Reject`` that answered the proposal.

Spec: ``specs/case-proposal.yaml`` CP-05-002, CP-05-004.
"""

import urllib.parse
from collections.abc import Mapping
from typing import Any, ClassVar, Literal

from pydantic import Field, model_validator

from vultron.core.models.base import (
    NonEmptyString,
    UriString,
    with_record_id,
)
from vultron.core.models.retired_stored_fields import (
    RetiredFieldsRecord,
    RetiredStoredField,
)


class CaseProposalDeclineRecord(RetiredFieldsRecord):
    """Durable record that this service declined a ``CaseProposal``.

    Attributes:
        proposal_id: URI of the ``as_CaseProposal`` that was declined. Used as
            the stable key component for ``build_id()``.
        case_actor_id: URI of the case actor service that made the decision.
        proposer_uri: URI of the proposing actor owed the ``Reject``.
        reason: Optional human-readable reason, surfaced to the proposer as the
            ``Reject``'s ``summary`` when present (CP-06-004). Absent when the
            admission backend supplied none; a decline is never blocked on
            having a reason to give. The closed-case decline writes one
            (CP-05-006, CP-05-008). The admission call-out point does not yet:
            it signals refusal by returning FAILURE and BT-18-002 defines
            blackboard outputs only for the SUCCESS case, so a refusal has no
            sanctioned channel for a payload. Tracked in #3446.
        reject_activity_id: URI of the ``Reject`` this service queued for the
            proposer, set by the emit in the transaction that writes the
            record.  ``None`` only until that emit runs.

    A stored record that still carries the retired ``vendor_uri`` key is
    refused on load (#4128); the store must be reset.

    Spec: CP-05-002, CP-05-004.
    """

    type_: Literal["CaseProposalDeclineRecord"] = Field(  # type: ignore[assignment]
        default="CaseProposalDeclineRecord",
        validation_alias="type",
        serialization_alias="type",
    )
    proposal_id: UriString = Field(
        ..., description="URI of the CaseProposal that was declined"
    )
    case_actor_id: UriString = Field(
        ..., description="URI of the case actor service that declined it"
    )
    proposer_uri: UriString = Field(
        ..., description="URI of the proposing actor owed the Reject"
    )
    reason: NonEmptyString | None = Field(
        default=None,
        description=(
            "Optional reason, carried to the proposer as the Reject's summary"
        ),
    )
    reject_activity_id: UriString | None = Field(
        default=None,
        description=(
            "URI of the Reject queued for the proposer; None only until the"
            " emit that commits with the record runs"
        ),
    )

    retired_stored_fields: ClassVar[Mapping[str, RetiredStoredField]] = {
        "vendor_uri": RetiredStoredField("proposer_uri", "#4128"),
    }

    @classmethod
    def build_id(cls, proposal_id: str) -> str:
        """Return the stable DataLayer ID for *proposal_id*."""
        slug = urllib.parse.quote(proposal_id, safe="")
        return f"case-proposal-declined/{slug}"

    @model_validator(mode="before")
    @classmethod
    def _set_id(cls, data: Any) -> Any:
        """Compute ``id_`` deterministically from ``proposal_id``."""
        if isinstance(data, dict):
            proposal_id = data.get("proposal_id")
            if proposal_id is not None:
                data = with_record_id(data, cls.build_id(proposal_id))
        return data


__all__ = ["CaseProposalDeclineRecord"]
