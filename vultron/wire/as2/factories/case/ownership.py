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
"""Factories for case ownership transfer: Offer, replies and withdrawal.

Spec: ``specs/activity-factories.yaml`` AF-01-001 through AF-04-003.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Any, TypeVar

from vultron.core.models.actor import CoreActor
from vultron.wire.as2.factories._actor import carried_actor
from vultron.wire.as2.factories._construct import build_activity
from vultron.wire.as2.factories._held import (
    as_answered,
)
from vultron.wire.as2.factories.case._named import _named_case
from vultron.wire.as2.vocab.activities.case.ownership import (
    _AcceptCaseOwnershipTransferActivity,
    _OfferCaseOwnershipTransferActivity,
    _RejectCaseOwnershipTransferActivity,
    _UndoCaseOwnershipTransferActivity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Offer,
    as_Reject,
    as_Undo,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor, as_ActorRef
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)


def _carried_target(
    target: as_ActorRef | CoreActor | None,
) -> as_ActorRef | CoreActor | None:
    """The transferee as the Offer carries it: held, or an actor reference."""
    if isinstance(target, (str, as_Actor, CoreActor)):
        return carried_actor(target)
    return target


def offer_case_ownership_transfer_activity(
    case: as_VulnerabilityCase | str,
    target: as_ActorRef | CoreActor | None = None,
    *,
    at: datetime,
    **kwargs,
) -> as_Offer:
    """Build an Offer(VulnerabilityCase) of case ownership, ``target`` the transferee.

    One shape, two senders (ADR-0199): the Case Owner's own Offer, sent to
    the CASE_MANAGER, and the Offer the CASE_MANAGER makes from it, sent to
    the transferee (CM-21-028).  The case travels as its typed reference,
    never a copy (ADR-0165): the CASE_MANAGER and the active participant the
    case is offered to both hold it (CM-21-021).  Its ``type`` is what
    tells this activity from a ``SUBMIT_REPORT`` Offer during semantic
    pattern matching, so it is never a bare string ID.

    The transferee travels and is stored inline (DL-08-003): the CASE_MANAGER
    need not hold the transferee's profile, and its ledger snapshot must
    carry the transferee inline (CLP-07-006).  A held profile travels as held;
    a bare actor URI travels as an actor reference (AKM-05-017).

    Args:
        case: The case whose ownership is being offered, as the sender
            holds it or by its URI.  Only its id travels.
        target: The actor (or actor URI) to whom ownership is offered.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``).

    Returns:
        An ``as_Offer`` whose ``object_`` is the case's typed reference.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    return build_activity(
        "offer_case_ownership_transfer_activity",
        _OfferCaseOwnershipTransferActivity,
        at,
        lambda: {
            "object_": _named_case(case),
            "target": _carried_target(target),
            **kwargs,
        },
    )


_OwnershipReply = TypeVar("_OwnershipReply")


def _ownership_offer_reply(
    reply_class: Callable[..., _OwnershipReply],
    label: str,
    offer: as_Offer,
    kwargs: dict[str, Any],
    *,
    at: datetime,
) -> _OwnershipReply:
    """Build *reply_class* around an ownership-transfer *offer*.

    Shared by the transferee's Accept and Reject and the offerer's Undo.
    *offer* may be the Offer as a receiver parsed it from its archived body,
    which the reply then embeds verbatim (:func:`as_answered`).

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails, as it
            does for a plain ``as_Offer`` that is not an
            ``_OfferCaseOwnershipTransferActivity``.
    """
    return build_activity(
        label,
        reply_class,
        at,
        lambda: {
            "object_": as_answered(_OfferCaseOwnershipTransferActivity, offer),
            **kwargs,
        },
    )


def accept_case_ownership_transfer_activity(
    offer: as_Offer,
    *,
    at: datetime,
    **kwargs,
) -> as_Accept:
    """Build an Accept(_OfferCaseOwnershipTransferActivity).

    The ``offer`` MUST be an ``_OfferCaseOwnershipTransferActivity``
    (i.e., the value returned by
    :func:`offer_case_ownership_transfer_activity`).  A plain
    ``as_Offer`` will fail Pydantic validation and raise
    :exc:`VultronActivityConstructionError`.

    Args:
        offer: The ``_OfferCaseOwnershipTransferActivity`` being accepted.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``).

    Returns:
        An ``as_Accept`` whose ``object_`` is the offer.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    return _ownership_offer_reply(
        _AcceptCaseOwnershipTransferActivity,
        "accept_case_ownership_transfer_activity",
        offer,
        kwargs,
        at=at,
    )


def reject_case_ownership_transfer_activity(
    offer: as_Offer,
    *,
    at: datetime,
    **kwargs,
) -> as_Reject:
    """Build a Reject(_OfferCaseOwnershipTransferActivity).

    The ``offer`` MUST be an ``_OfferCaseOwnershipTransferActivity``
    (i.e., the value returned by
    :func:`offer_case_ownership_transfer_activity`).  A plain
    ``as_Offer`` will fail Pydantic validation and raise
    :exc:`VultronActivityConstructionError`.

    Args:
        offer: The ``_OfferCaseOwnershipTransferActivity`` being rejected.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``).

    Returns:
        An ``as_Reject`` whose ``object_`` is the offer.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    return _ownership_offer_reply(
        _RejectCaseOwnershipTransferActivity,
        "reject_case_ownership_transfer_activity",
        offer,
        kwargs,
        at=at,
    )


def undo_case_ownership_transfer_activity(
    offer: as_Offer,
    *,
    at: datetime,
    **kwargs,
) -> as_Undo:
    """Build an Undo(_OfferCaseOwnershipTransferActivity): a withdrawal.

    The Case Owner withdraws its own Offer while the Offer the CASE_MANAGER
    made from it is open, addressing the Undo to the CASE_MANAGER
    (CM-21-015, ADR-0199).  The ``offer`` MUST be an
    ``_OfferCaseOwnershipTransferActivity`` (i.e., the value returned by
    :func:`offer_case_ownership_transfer_activity`), or the Offer as the
    owner's store hands it back.  Anything else fails Pydantic validation
    and raises :exc:`VultronActivityConstructionError`.

    Args:
        offer: The Owner's own ``_OfferCaseOwnershipTransferActivity``
            withdrawn.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``).

    Returns:
        An ``as_Undo`` whose ``object_`` is the Owner's Offer.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    label = "undo_case_ownership_transfer_activity"
    return build_activity(
        label,
        _UndoCaseOwnershipTransferActivity,
        at,
        lambda: {
            "object_": as_answered(_OfferCaseOwnershipTransferActivity, offer),
            **kwargs,
        },
    )
