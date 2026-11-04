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
"""Factories for case participant role delegation (ADR-0039).

Spec: ``specs/activity-factories.yaml`` AF-01-001 through AF-04-003.
"""

import logging
from typing import cast

from pydantic import ValidationError

from vultron.core.models.actor import CoreActor
from vultron.enums.roles import CVDRole
from vultron.wire.as2.factories._actor import carried_actor
from vultron.wire.as2.factories._context import (
    case_uri_of,
    with_case_context,
)
from vultron.wire.as2.factories.errors import VultronActivityConstructionError
from vultron.wire.as2.vocab.activities.case.roles import (
    _AcceptCaseParticipantRoleActivity,
    _OfferCaseParticipantRoleActivity,
    _RejectCaseParticipantRoleActivity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Offer,
    as_Reject,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.case_participant_role import (
    as_CaseParticipantRole,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

logger = logging.getLogger(__name__)


def offer_case_participant_role_activity(
    role: CVDRole,
    target_actor: as_Actor | CoreActor | str,
    case: as_VulnerabilityCase | str,
    **kwargs,
) -> as_Offer:
    """Build Offer(CaseParticipantRole)[context=VulnerabilityCase].

    This is the canonical role-delegation wire format introduced in ADR-0039.
    It replaces the deprecated ``offer_case_manager_role_activity`` format
    (``Offer(VulnerabilityCase)[target=CaseParticipant]``) which was structurally
    ambiguous with ownership-transfer offers.

    The ``as_CaseParticipantRole`` object carries the specific ``CVDRole`` being
    offered, making the activity self-describing.  The ``target`` is the Actor
    receiving the role; the case is carried in ``context``.

    Args:
        role: The ``CVDRole`` to offer.  Becomes the ``role`` field on the
            ``as_CaseParticipantRole`` object.
        target_actor: The actor that will receive the role offer: its profile
            as the sender holds it, or its URI, which travels as an actor
            reference (AKM-05-017).
        case: The ``as_VulnerabilityCase`` (or its URI) the role is scoped
            to.  Only its URI goes on the wire as ``context``: the recipient
            is a participant and already holds the case (AKM-02-002), and the
            blob is delivered and recorded as built (VM-08-003), so a full
            case here would travel whole.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``).

    Returns:
        An ``as_Offer`` whose ``object_`` is an ``as_CaseParticipantRole``,
        ``target`` is the target Actor, and ``context`` is the case URI.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        role_obj = as_CaseParticipantRole(role=role)
        return _OfferCaseParticipantRoleActivity(
            object_=role_obj,
            target=carried_actor(target_actor),
            context=case_uri_of(case) or case,
            **kwargs,
        )
    except ValidationError as exc:
        logger.warning(
            "offer_case_participant_role_activity: invalid arguments: %s",
            exc,
        )
        raise VultronActivityConstructionError(
            "offer_case_participant_role_activity: invalid arguments"
        ) from exc


def accept_case_participant_role_activity(
    offer: as_Offer,
    **kwargs,
) -> as_Accept:
    """Build an Accept(_OfferCaseParticipantRoleActivity) (ADR-0039).

    The ``offer`` MUST be an ``_OfferCaseParticipantRoleActivity`` (i.e., the
    value returned by :func:`offer_case_participant_role_activity`).

    Args:
        offer: The ``_OfferCaseParticipantRoleActivity`` being accepted.
        **kwargs: Optional AS2 fields (e.g. ``actor``).

    Returns:
        An ``as_Accept`` whose ``object_`` is the offer.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _AcceptCaseParticipantRoleActivity(
            object_=cast(_OfferCaseParticipantRoleActivity, offer),
            **with_case_context(kwargs, getattr(offer, "context", None)),
        )
    except ValidationError as exc:
        logger.warning(
            "accept_case_participant_role_activity: invalid arguments: %s",
            exc,
        )
        raise VultronActivityConstructionError(
            "accept_case_participant_role_activity: invalid arguments"
        ) from exc


def reject_case_participant_role_activity(
    offer: as_Offer,
    **kwargs,
) -> as_Reject:
    """Build a Reject(_OfferCaseParticipantRoleActivity) (ADR-0039).

    The ``offer`` MUST be an ``_OfferCaseParticipantRoleActivity`` (i.e., the
    value returned by :func:`offer_case_participant_role_activity`).

    Args:
        offer: The ``_OfferCaseParticipantRoleActivity`` being rejected.
        **kwargs: Optional AS2 fields (e.g. ``actor``).

    Returns:
        An ``as_Reject`` whose ``object_`` is the offer.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _RejectCaseParticipantRoleActivity(
            object_=cast(_OfferCaseParticipantRoleActivity, offer),
            **with_case_context(kwargs, getattr(offer, "context", None)),
        )
    except ValidationError as exc:
        logger.warning(
            "reject_case_participant_role_activity: invalid arguments: %s",
            exc,
        )
        raise VultronActivityConstructionError(
            "reject_case_participant_role_activity: invalid arguments"
        ) from exc
