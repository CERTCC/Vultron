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

The record is written by the admission decision **before** the
``Reject(as_CaseProposal)`` is queued, and it is what makes a decline safe.
Three properties depend on it:

- **The decision is terminal.** Once the record exists, the accept path refuses
  to run. Without it, any failure while emitting the ``Reject`` — a missing
  wire proposal, an uninjected port, a store error — would let the enclosing
  Selector fall through to the accept flow and create the case, telling the
  proposer "yes" after the service decided "no".
- **Redelivery is idempotent.** A second delivery of the same proposal finds the
  record and does not re-adjudicate, so a retrying proposer is not sent a new
  ``Reject`` each time, and a stateful or stochastic backend cannot accept what
  it previously refused (CP-05-006 applies the same rule to the accept side).
- **A lost ``Reject`` is recoverable.** Because the record is written first, a
  redelivery can see "declined, but nothing was queued" and emit the ``Reject``
  then — the same ordering ``PendingCreateCaseActivity`` uses for the accept
  side's ``Create`` obligation (CP-05-005).

``reject_activity_id`` is what keeps the second and third properties from
contradicting each other. "Has the proposer been told?" cannot be answered from
the outbox, because ``outbox_pop`` removes an activity on delivery while its
stored copy remains: a delivered ``Reject`` therefore looks exactly like one that
was never queued, and re-emitting on that reading mints a fresh ``Reject`` on
*every* subsequent delivery — unbounded store growth and outbound amplification
driven by whoever is replaying the proposal. Recording the id of the ``Reject``
this service actually queued gives the guard a third state ("declined **and**
answered") that neither the store nor the outbox can express on its own.


Spec: ``specs/case-proposal.yaml`` CP-05-002, CP-05-004.
"""

import urllib.parse
from typing import Any, Literal

from pydantic import Field, model_validator

from vultron.core.models.base import (
    NonEmptyString,
    UriString,
    VultronObject,
)


class CaseProposalDeclineRecord(VultronObject):
    """Durable record that this service declined a ``CaseProposal``.

    Attributes:
        proposal_id: URI of the ``as_CaseProposal`` that was declined. Used as
            the stable key component for ``build_id()``.
        case_actor_id: URI of the case actor service that made the decision.
        vendor_uri: URI of the proposing actor owed the ``Reject``.
        reason: Optional human-readable reason, surfaced to the proposer as the
            ``Reject``'s ``summary`` when present (CP-06-004). Absent when the
            admission backend supplied none; a decline is never blocked on
            having a reason to give. **Nothing writes this yet** — a call-out
            point signals refusal by returning FAILURE and BT-18-002 defines
            blackboard outputs only for the SUCCESS case, so a refusal has no
            sanctioned channel for a payload. Tracked in #3446; the read path
            below is built and tested so the field is usable the moment that
            channel exists.
        reject_activity_id: URI of the ``Reject`` this service queued for the
            proposer, set once the emit succeeds. ``None`` means the decision
            was recorded but the proposer has not been told, which is the state
            a redelivery recovers. See the module docstring for why the outbox
            cannot answer this.

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
    vendor_uri: UriString = Field(
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
            "URI of the Reject queued for the proposer; None means the decline"
            " was recorded but the proposer has not been told"
        ),
    )

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
                data = dict(data)
                data["id"] = cls.build_id(proposal_id)
        return data


__all__ = ["CaseProposalDeclineRecord"]
