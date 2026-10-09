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

"""Durable marker for a creation-time revision whose relay is still owed.

EP-04-011 says the revision that shortest-wins registers at case creation MUST
be relayed as an ``Invite(EmbargoEvent)``.  The registration persists the
revision (EM ``REVISE``, a ``PROPOSED`` register entry) inside the creation-time
initialization, but who the proposer is and which id the Invite carries exist
only for that one execution.  Initialization runs once per case (EP-04-012), so
a redelivered ``Create(as_CaseProposal)`` never registers it again: had the
relay failed, nothing would send the Invite and the winning party would never
be asked.

This record carries what the relay needs across executions, in the shape of
the ``PendingCreateCaseActivity`` marker (CP-05-005): committed in the same
write that registers the revision (#4142), so no failure leaves a revision
nobody owes (#4156); deleted once the relay is discharged; and found by a later delivery's relay or by the startup retry
runner while it remains.

Spec: ``specs/embargo-policy.yaml`` EP-04-011.
"""

import urllib.parse
from typing import Any, Literal

from pydantic import Field, model_validator

from vultron.core.models.base import CoreRecord, UriString, with_record_id

#: Whose terms lost shortest-wins: the values of
#: ``EmbargoDurationSource.SENDER_PROPOSAL`` (the reporter's) and
#: ``EmbargoDurationSource.ACTOR_DEFAULT`` (the case owner's).  Spelled out
#: here because a core model does not import a core service.
LosingSource = Literal["sender_proposal", "actor_default"]


class PendingCreationTimeRevisionRelay(CoreRecord):
    """A creation-time revision registered but not yet relayed (EP-04-011).

    Attributes:
        case_id: URI of the case; the stable key component for ``build_id()``,
            since creation-time initialization runs once per case (EP-04-012).
        embargo_id: URI of the revision's ``EmbargoEvent``.
        proposal_id: The id the relayed ``Invite`` carries, minted when the
            revision was registered, so a retry sends the same Invite and the
            ledger can tell that it was already sent.
        losing_source: Whose terms lost, and so who the proposer is
            (see :data:`LosingSource`).
        report_id: URI of the report the case was created from; the reporter
            is its author.  Required: a revision with no report could never
            be relayed, so its writer raises instead of recording it.
        case_actor_id: URI of the CASE_MANAGER that owes the relay.
        invite_queued: The receipt that the committed Invite reached the
            outbox.  Delivery empties the outbox, so neither it nor the ledger
            can tell a delivered Invite from one whose queueing failed after
            its commit; a retry that finds the Invite committed queues it
            again unless this is set.

    Spec: EP-04-011.
    """

    type_: Literal["PendingCreationTimeRevisionRelay"] = Field(  # type: ignore[assignment]
        default="PendingCreationTimeRevisionRelay",
        validation_alias="type",
        serialization_alias="type",
    )
    case_id: UriString = Field(..., description="URI of the case")
    embargo_id: UriString = Field(
        ..., description="URI of the revision's EmbargoEvent"
    )
    proposal_id: UriString = Field(
        ..., description="Id the relayed Invite(EmbargoEvent) carries"
    )
    losing_source: LosingSource = Field(
        ..., description="Whose terms lost shortest-wins"
    )
    report_id: UriString = Field(
        ..., description="URI of the report the case came from"
    )
    case_actor_id: UriString = Field(
        ..., description="URI of the CASE_MANAGER that owes the relay"
    )
    invite_queued: bool = Field(
        default=False,
        description="Set once the committed Invite reached the outbox",
    )

    @classmethod
    def build_id(cls, case_id: str) -> str:
        """Return the stable DataLayer ID for *case_id*."""
        slug = urllib.parse.quote(case_id, safe="")
        return f"pending-revision-relay/{slug}"

    @model_validator(mode="before")
    @classmethod
    def _set_id(cls, data: Any) -> Any:
        """Compute ``id_`` deterministically from ``case_id``."""
        if isinstance(data, dict):
            case_id = data.get("case_id")
            if case_id is not None:
                data = with_record_id(data, cls.build_id(case_id))
        return data


__all__ = ["LosingSource", "PendingCreationTimeRevisionRelay"]
