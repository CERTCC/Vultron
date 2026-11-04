#!/usr/bin/env python
# pyright: reportGeneralTypeIssues=false
#  Copyright (c) 2023-2025 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University
"""Case ownership transfer activities: Offer, propose, reply and withdraw."""

from typing import ClassVar

from pydantic import Field

from vultron.primitives import NonEmptyString
from vultron.wire.as2.vocab.activities.case.named_case import NamedCase
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Offer,
    as_Reject,
    as_Undo,
)
from vultron.wire.as2.vocab.base.objects.actors import (
    as_ActorRef,
    as_CarriedActor,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)


class _OfferCaseOwnershipTransferActivity(as_Offer):
    """The actor is offering to transfer ownership of the case to another actor.

    The case travels as its typed reference, an inline object with only its
    ``id`` and ``type`` (ADR-0165): every receiver of an ownership-transfer
    Offer already holds the case (CM-21-021), and the ``type`` is what lets
    the recipient tell it from a ``SUBMIT_REPORT`` Offer during semantic
    pattern matching.  A bare string URI would make the two indistinguishable
    and cause incorrect dispatch.

    object_: the case, by typed reference (not a bare string ID)
    target: the transferee, as the sender holds it or as an actor reference

    Declares ``target`` in :attr:`inline_required_refs` (DL-08-003). The
    transferee is a *peer*: under ADR-0073 its record lives in the store of
    whichever actor knows it, and neither the offerer nor the CASE_MANAGER is
    obliged to hold it. Dehydrated to its id, the stored Offer had nothing to
    read the transferee back from, and the CASE_MANAGER's ledger commit then
    refused the bare ``target`` (CLP-07-018, #4843).
    :func:`~vultron.wire.as2.factories.offer_case_ownership_transfer_activity`
    carries a transferee known only by id as an actor reference, so it
    travels inline (AKM-05-017).
    """

    object_: NamedCase = Field(
        ..., validation_alias="object", serialization_alias="object"
    )
    target: as_CarriedActor | as_ActorRef = None

    inline_required_refs: ClassVar[frozenset[str]] = frozenset({"target"})


class _ProposeCaseOwnershipTransferActivity(as_Offer):
    """The Case Owner proposes an ownership transfer to the CASE_MANAGER.

    Wire format: ``Offer(Offer(VulnerabilityCase))``, its ``context`` the case
    (ADR-0148).  The inner Offer is the template of the one Offer the
    CASE_MANAGER makes to the transferee: its object is the case, its
    ``target`` the transferee and its ``endTime`` the deadline to answer.
    The proposal's shape, an Offer of an Offer, is what tells it apart from
    the CASE_MANAGER's ``Offer(VulnerabilityCase)``, so neither pattern needs
    a sender check (ADR-0039).

    object_: _OfferCaseOwnershipTransferActivity (inline, required)
    context: as_VulnerabilityCase or str URI (required): the case the
        proposal is about, which the inner Offer's object must name

    Declares ``object_`` in :attr:`inline_required_refs`: the inner Offer is
    minted inline and never stored on its own, so its id resolves to nothing
    (DL-08-001).
    """

    object_: _OfferCaseOwnershipTransferActivity = Field(
        ..., validation_alias="object", serialization_alias="object"
    )
    context: as_VulnerabilityCase | NonEmptyString = Field(
        ..., validation_alias="context", serialization_alias="context"
    )

    inline_required_refs: ClassVar[frozenset[str]] = frozenset({"object_"})


class _AcceptCaseOwnershipTransferActivity(as_Accept):
    """The actor is accepting an offer to transfer ownership of the case.

    - object_: the _OfferCaseOwnershipTransferActivity being accepted (inline
      typed object required — bare string IDs are rejected at construction time)
    """

    object_: _OfferCaseOwnershipTransferActivity = Field(
        ..., validation_alias="object", serialization_alias="object"
    )


class _RejectCaseOwnershipTransferActivity(as_Reject):
    """The actor is rejecting an offer to transfer ownership of the case.

    - object_: the _OfferCaseOwnershipTransferActivity being rejected (inline
      typed object required — bare string IDs are rejected at construction time)
    """

    object_: _OfferCaseOwnershipTransferActivity = Field(
        ..., validation_alias="object", serialization_alias="object"
    )


class _UndoCaseOwnershipTransferActivity(as_Undo):
    """The Case Owner is withdrawing its ownership-transfer proposal.

    Sent by the Case Owner that made the proposal, addressed to the
    CASE_MANAGER, which withdraws the Offer it made from it (CM-21-015,
    ADR-0148).

    - object_: the _ProposeCaseOwnershipTransferActivity being withdrawn
      (inline typed object required — bare string IDs are rejected at
      construction time)
    """

    object_: _ProposeCaseOwnershipTransferActivity = Field(
        ..., validation_alias="object", serialization_alias="object"
    )
