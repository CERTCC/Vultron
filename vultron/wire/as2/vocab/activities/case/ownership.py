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
"""Case ownership transfer activities: Offer, reply and withdraw."""

from typing import ClassVar

from pydantic import Field

from vultron.wire.as2.vocab.activities.base import RepliesToObject
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


class _OfferCaseOwnershipTransferActivity(as_Offer):
    """The actor is offering to transfer ownership of the case to another actor.

    One wire shape, two senders (ADR-0199): the Case Owner's own Offer, sent
    to the CASE_MANAGER, and the Offer the CASE_MANAGER makes from it, sent
    to the transferee with ``attributedTo`` the Owner and ``inReplyTo`` the
    Owner's Offer (CM-21-028).  The receiver's path tells them apart.

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


class _AcceptCaseOwnershipTransferActivity(RepliesToObject, as_Accept):
    """The actor is accepting an offer to transfer ownership of the case.

    - object_: the _OfferCaseOwnershipTransferActivity being accepted (inline
      typed object required — bare string IDs are rejected at construction time)
    """

    object_: _OfferCaseOwnershipTransferActivity = Field(
        ..., validation_alias="object", serialization_alias="object"
    )


class _RejectCaseOwnershipTransferActivity(RepliesToObject, as_Reject):
    """The actor is rejecting an offer to transfer ownership of the case.

    - object_: the _OfferCaseOwnershipTransferActivity being rejected (inline
      typed object required — bare string IDs are rejected at construction time)
    """

    object_: _OfferCaseOwnershipTransferActivity = Field(
        ..., validation_alias="object", serialization_alias="object"
    )


class _UndoCaseOwnershipTransferActivity(as_Undo):
    """The Case Owner is withdrawing its own ownership-transfer Offer.

    Sent by the Case Owner that made the Offer, addressed to the
    CASE_MANAGER, which withdraws the Offer it made from it (CM-21-015,
    ADR-0199).

    - object_: the Owner's own _OfferCaseOwnershipTransferActivity being
      withdrawn (inline typed object required — bare string IDs are
      rejected at construction time)
    """

    object_: _OfferCaseOwnershipTransferActivity = Field(
        ..., validation_alias="object", serialization_alias="object"
    )
