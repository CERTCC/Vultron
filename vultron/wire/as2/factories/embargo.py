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
"""
Factory functions for outbound Vultron embargo-management activities.

These are the sole public construction API for activities involving
``EmbargoEvent`` objects. Internal activity subclasses are
imported here and MUST NOT be imported by callers.

Spec: ``specs/activity-factories.yaml`` AF-01-001 through AF-04-003.
"""

import logging
from typing import Sequence, cast

from pydantic import ValidationError

from vultron.wire.as2.factories.errors import VultronActivityConstructionError
from vultron.wire.as2.vocab.activities.embargo import (
    ActivateEmbargoActivity,
    AddEmbargoToCaseActivity,
    AnnounceEmbargoActivity,
    ChoosePreferredEmbargoActivity,
    EmAcceptEmbargoActivity,
    EmProposeEmbargoActivity,
    EmRejectEmbargoActivity,
    RemoveEmbargoFromCaseActivity,
)
from vultron.wire.as2.vocab.base.objects.activities.intransitive import (
    as_Question,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Add,
    as_Announce,
    as_Invite,
    as_Reject,
    as_Remove,
)
from vultron.wire.as2.vocab.objects.embargo_event import (
    EmbargoEvent,
    EmbargoEventRef,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    VulnerabilityCaseRef,
)

logger = logging.getLogger(__name__)


def em_propose_embargo_activity(
    embargo: EmbargoEvent,
    context: VulnerabilityCaseRef | None = None,
    **kwargs,
) -> as_Invite:
    """Build an Invite(EmbargoEvent) — the EP/EV message.

    Proposes a new embargo for the case.

    Args:
        embargo: The ``EmbargoEvent`` being proposed.
        context: The ``VulnerabilityCase`` (or its URI) for which the
            embargo is being proposed.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``).

    Returns:
        An ``as_Invite`` whose ``object_`` is the embargo event.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return EmProposeEmbargoActivity(
            object_=embargo, context=context, **kwargs
        )
    except ValidationError as exc:
        logger.warning(
            "em_propose_embargo_activity: invalid arguments: %s", exc
        )
        raise VultronActivityConstructionError(
            "em_propose_embargo_activity: invalid arguments"
        ) from exc


def em_accept_embargo_activity(
    proposal: as_Invite,
    context: VulnerabilityCaseRef | None = None,
    **kwargs,
) -> as_Accept:
    """Build an Accept(EmProposeEmbargoActivity) — the EA/EC message.

    Per ActivityStreams convention the actor accepts the proposal
    activity itself, not the ``EmbargoEvent`` being proposed.
    The ``proposal`` MUST be the value returned by
    :func:`em_propose_embargo_activity`; a plain ``as_Invite`` will
    fail validation.

    Args:
        proposal: The ``EmProposeEmbargoActivity`` being accepted.
        context: The ``VulnerabilityCase`` (or its URI) for which the
            embargo was proposed.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``).

    Returns:
        An ``as_Accept`` whose ``object_`` is the proposal.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return EmAcceptEmbargoActivity(
            object_=cast(EmProposeEmbargoActivity, proposal),
            context=context,
            **kwargs,
        )
    except ValidationError as exc:
        logger.warning(
            "em_accept_embargo_activity: invalid arguments: %s", exc
        )
        raise VultronActivityConstructionError(
            "em_accept_embargo_activity: invalid arguments"
        ) from exc


def em_reject_embargo_activity(
    proposal: as_Invite,
    context: VulnerabilityCaseRef | None = None,
    **kwargs,
) -> as_Reject:
    """Build a Reject(EmProposeEmbargoActivity) — the ER/EJ message.

    Per ActivityStreams convention the actor rejects the proposal
    activity itself, not the ``EmbargoEvent`` being proposed.
    The ``proposal`` MUST be the value returned by
    :func:`em_propose_embargo_activity`; a plain ``as_Invite`` will
    fail validation.

    Args:
        proposal: The ``EmProposeEmbargoActivity`` being rejected.
        context: The ``VulnerabilityCase`` (or its URI) for which the
            embargo was proposed.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``).

    Returns:
        An ``as_Reject`` whose ``object_`` is the proposal.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return EmRejectEmbargoActivity(
            object_=cast(EmProposeEmbargoActivity, proposal),
            context=context,
            **kwargs,
        )
    except ValidationError as exc:
        logger.warning(
            "em_reject_embargo_activity: invalid arguments: %s", exc
        )
        raise VultronActivityConstructionError(
            "em_reject_embargo_activity: invalid arguments"
        ) from exc


def choose_preferred_embargo_activity(
    any_of: Sequence[EmbargoEventRef] | None = None,
    one_of: Sequence[EmbargoEventRef] | None = None,
    **kwargs,
) -> as_Question:
    """Build a Question asking participants to indicate embargo preferences.

    Case participants should respond with
    :func:`em_accept_embargo_activity` or :func:`em_reject_embargo_activity`
    for each proposed embargo. Either ``any_of`` or ``one_of`` SHOULD be
    specified but not both.

    Args:
        any_of: Sequence of ``EmbargoEventRef`` items — participants
            may select any subset.
        one_of: Sequence of ``EmbargoEventRef`` items — participants
            must select exactly one.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``).

    Returns:
        An ``as_Question`` whose ``any_of`` or ``one_of`` lists the
        embargo choices.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return ChoosePreferredEmbargoActivity(
            any_of=any_of, one_of=one_of, **kwargs
        )
    except ValidationError as exc:
        logger.warning(
            "choose_preferred_embargo_activity: invalid arguments: %s", exc
        )
        raise VultronActivityConstructionError(
            "choose_preferred_embargo_activity: invalid arguments"
        ) from exc


def activate_embargo_activity(
    embargo: EmbargoEvent,
    target: VulnerabilityCaseRef | None = None,
    in_reply_to: EmProposeEmbargoActivity | str | None = None,
    **kwargs,
) -> as_Add:
    """Build an Add(EmbargoEvent) — activates the embargo on the case.

    Corresponds to the EA/EC message at the case level.  Use this when
    the case owner is activating an embargo in response to a previous
    :func:`em_propose_embargo_activity`.

    Args:
        embargo: The ``EmbargoEvent`` being activated.
        target: The ``VulnerabilityCase`` (or its URI) for which the
            embargo is activated.
        in_reply_to: The ``EmProposeEmbargoActivity`` (or its URI)
            that proposed this embargo.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``).

    Returns:
        An ``as_Add`` whose ``object_`` is the embargo event.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return ActivateEmbargoActivity(
            object_=embargo,
            target=target,
            in_reply_to=in_reply_to,
            **kwargs,
        )
    except ValidationError as exc:
        logger.warning("activate_embargo_activity: invalid arguments: %s", exc)
        raise VultronActivityConstructionError(
            "activate_embargo_activity: invalid arguments"
        ) from exc


def add_embargo_to_case_activity(
    embargo: EmbargoEvent,
    target: VulnerabilityCaseRef | None = None,
    **kwargs,
) -> as_Add:
    """Build an Add(EmbargoEvent, target=VulnerabilityCase).

    Use when the case owner is adding an embargo without a prior
    proposal.  When activating in response to a prior proposal, prefer
    :func:`activate_embargo_activity` which carries ``in_reply_to``.

    Args:
        embargo: The ``EmbargoEvent`` to add.
        target: The ``VulnerabilityCase`` (or its URI) to which the
            embargo is being added.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``).

    Returns:
        An ``as_Add`` whose ``object_`` is the embargo event.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return AddEmbargoToCaseActivity(
            object_=embargo, target=target, **kwargs
        )
    except ValidationError as exc:
        logger.warning(
            "add_embargo_to_case_activity: invalid arguments: %s", exc
        )
        raise VultronActivityConstructionError(
            "add_embargo_to_case_activity: invalid arguments"
        ) from exc


def announce_embargo_activity(
    embargo: EmbargoEvent,
    context: VulnerabilityCaseRef | None = None,
    **kwargs,
) -> as_Announce:
    """Build an Announce(EmbargoEvent) — announces an active embargo.

    Args:
        embargo: The ``EmbargoEvent`` being announced.
        context: The ``VulnerabilityCase`` (or its URI) for which the
            embargo is active.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``).

    Returns:
        An ``as_Announce`` whose ``object_`` is the embargo event.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return AnnounceEmbargoActivity(
            object_=embargo, context=context, **kwargs
        )
    except ValidationError as exc:
        logger.warning("announce_embargo_activity: invalid arguments: %s", exc)
        raise VultronActivityConstructionError(
            "announce_embargo_activity: invalid arguments"
        ) from exc


def remove_embargo_from_case_activity(
    embargo: EmbargoEvent,
    origin: VulnerabilityCaseRef | None = None,
    **kwargs,
) -> as_Remove:
    """Build a Remove(EmbargoEvent, origin=VulnerabilityCase).

    Removes an ``EmbargoEvent`` from the ``proposedEmbargoes`` of a
    case. This MUST only be performed by the case owner.

    Note: this activity uses ``origin`` (not ``target``) for the case
    reference, following the ActivityStreams convention for Remove.

    Args:
        embargo: The ``EmbargoEvent`` to remove.
        origin: The ``VulnerabilityCase`` (or its URI) from which
            the embargo is removed.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``).

    Returns:
        An ``as_Remove`` whose ``object_`` is the embargo event and
        ``origin`` is the case reference.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return RemoveEmbargoFromCaseActivity(
            object_=embargo, origin=origin, **kwargs
        )
    except ValidationError as exc:
        logger.warning(
            "remove_embargo_from_case_activity: invalid arguments: %s", exc
        )
        raise VultronActivityConstructionError(
            "remove_embargo_from_case_activity: invalid arguments"
        ) from exc
