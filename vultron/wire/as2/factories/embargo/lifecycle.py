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
"""Factories for the CASE_MANAGER's embargo lifecycle acts and a participant's exit.

Activate, refuse a proposal, withdraw, announce and remove an embargo.

Spec: ``specs/activity-factories.yaml`` AF-01-001 through AF-04-003.
"""

import logging

from pydantic import ValidationError

from vultron.core.models.embargo_termination import TerminationCause
from vultron.core.states.embargo_register import TerminationReason
from vultron.wire.as2.factories._context import (
    case_target_ref,
)
from vultron.wire.as2.factories.errors import VultronActivityConstructionError
from vultron.wire.as2.vocab.activities.embargo import (
    _ActivateEmbargoActivity,
    _AnnounceEmbargoActivity,
    _RejectEmbargoProposalActivity,
    _RemoveEmbargoFromCaseActivity,
    _WithdrawFromEmbargoActivity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Announce,
    as_Leave,
    as_Reject,
    as_Remove,
)
from vultron.wire.as2.vocab.objects.embargo_event import (
    as_EmbargoEvent,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCaseRef,
)

logger = logging.getLogger(__name__)


def activate_embargo_activity(
    embargo: as_EmbargoEvent,
    target: as_VulnerabilityCaseRef | None = None,
    **kwargs,
) -> as_Accept:
    """Build an Accept(EmbargoEvent)[target=VulnerabilityCase].

    The case owner's activation of a proposed embargo (ADR-0122): the
    receiver activates the embargo's register entry, superseding any entry
    in force, and records the owner's agreement.  Distinct from
    :func:`em_accept_embargo_activity`, the sender's own consent to an
    Invite.  Only the case owner sends it.

    Args:
        embargo: The ``as_EmbargoEvent`` being activated, carried inline.
        target: The ``VulnerabilityCase`` (or its URI) the embargo was
            proposed for.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``, ``context``).

    Returns:
        An ``as_Accept`` whose ``object_`` is the embargo event.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _ActivateEmbargoActivity(
            object_=embargo, target=case_target_ref(target), **kwargs
        )
    except ValidationError as exc:
        logger.warning("activate_embargo_activity: invalid arguments: %s", exc)
        raise VultronActivityConstructionError(
            "activate_embargo_activity: invalid arguments"
        ) from exc


def reject_embargo_proposal_activity(
    embargo: as_EmbargoEvent,
    target: as_VulnerabilityCaseRef | None = None,
    **kwargs,
) -> as_Reject:
    """Build a Reject(EmbargoEvent)[target=VulnerabilityCase].

    The case owner's rejection of a proposed embargo (ADR-0122): the
    receiver rejects the embargo's register entry and writes no consent.
    Distinct from :func:`em_reject_embargo_activity`, the sender's own
    refusal of an Invite.  Only the case owner sends it.

    Args:
        embargo: The ``as_EmbargoEvent`` being rejected, carried inline.
        target: The ``VulnerabilityCase`` (or its URI) the embargo was
            proposed for.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``, ``context``).

    Returns:
        An ``as_Reject`` whose ``object_`` is the embargo event.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _RejectEmbargoProposalActivity(
            object_=embargo, target=case_target_ref(target), **kwargs
        )
    except ValidationError as exc:
        logger.warning(
            "reject_embargo_proposal_activity: invalid arguments: %s", exc
        )
        raise VultronActivityConstructionError(
            "reject_embargo_proposal_activity: invalid arguments"
        ) from exc


def withdraw_from_embargo_activity(
    embargo: as_EmbargoEvent,
    context: as_VulnerabilityCaseRef | None = None,
    **kwargs,
) -> as_Leave:
    """Build a Leave(EmbargoEvent)[context=VulnerabilityCase].

    A signatory's withdrawal from the embargo in force (MSM-07-010,
    ADR-0122): the receiver declines the sender's ``AGREED`` row for the
    active embargo, and every open proposal's row it had agreed to, and
    changes no register entry.  Distinct from
    :func:`em_reject_embargo_activity`, which answers an Invite and never
    withdraws, and from ``Leave(VulnerabilityCase)``, which leaves the case.
    The case owner does not send it.

    Args:
        embargo: The ``as_EmbargoEvent`` in force, carried inline.
        context: The ``VulnerabilityCase`` (or its URI) the embargo is on.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``).

    Returns:
        An ``as_Leave`` whose ``object_`` is the embargo event.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _WithdrawFromEmbargoActivity(
            object_=embargo, context=context, **kwargs
        )
    except ValidationError as exc:
        logger.warning(
            "withdraw_from_embargo_activity: invalid arguments: %s", exc
        )
        raise VultronActivityConstructionError(
            "withdraw_from_embargo_activity: invalid arguments"
        ) from exc


def announce_embargo_activity(
    embargo: as_EmbargoEvent,
    context: as_VulnerabilityCaseRef | None = None,
    **kwargs,
) -> as_Announce:
    """Build an Announce(EmbargoEvent) — announces an active embargo.

    Args:
        embargo: The ``as_EmbargoEvent`` being announced.
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
        return _AnnounceEmbargoActivity(
            object_=embargo, context=context, **kwargs
        )
    except ValidationError as exc:
        logger.warning("announce_embargo_activity: invalid arguments: %s", exc)
        raise VultronActivityConstructionError(
            "announce_embargo_activity: invalid arguments"
        ) from exc


#: The human-readable ``summary`` of a termination ``Remove``, by reason.
#: The protocol reads ``content``, never this (ADR-0122).
_TERMINATION_SUMMARY: dict[TerminationReason, str] = {
    TerminationReason.END_TIME_REACHED: "The embargo reached its end time.",
    TerminationReason.EARLY: "The embargo ended before its end time.",
}


def remove_embargo_from_case_activity(
    embargo: as_EmbargoEvent,
    origin: as_VulnerabilityCaseRef | None = None,
    *,
    reason: TerminationReason,
    cause: TerminationCause | None = None,
    **kwargs,
) -> as_Remove:
    """Build a Remove(EmbargoEvent), the case in ``origin``.

    Ends the embargo in force on a case (ET): the receiver terminates the
    case's ``ACTIVE`` embargo register entry and cancels every open proposal
    with it (MSM-07-006, ADR-0122).  This MUST only be performed by the case
    owner, or by the CASE_MANAGER.

    *reason* is the termination's what, carried as ``content``: exactly
    ``END_TIME_REACHED`` or ``EARLY`` (ADR-0122).  *cause* is its why, when
    the sender names one, carried as ``terminationCause`` (EMB-13-005); an
    ``END_TIME_REACHED`` termination has none.  ``summary`` defaults to a
    human-readable account the protocol does not read; pass ``summary`` to
    override it, as an ``OTHER`` cause does to give its account.

    Note: this activity uses ``origin`` (not ``target``) for the case
    reference, following the ActivityStreams convention for Remove.

    Args:
        embargo: The ``as_EmbargoEvent`` to remove.
        origin: The ``VulnerabilityCase`` (or its URI) from which
            the embargo is removed.
        reason: What ended the embargo; required.
        cause: Why it ended, or ``None`` when the sender names no cause.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``).

    Returns:
        An ``as_Remove`` whose ``object_`` is the embargo event and
        ``origin`` is the case reference.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails,
            including a *cause* on an ``END_TIME_REACHED`` termination.
    """
    try:
        kwargs.setdefault("summary", _TERMINATION_SUMMARY[reason])
        return _RemoveEmbargoFromCaseActivity(
            object_=embargo,
            origin=origin,
            content=reason.value,
            termination_cause=cause,
            **kwargs,
        )
    except ValidationError as exc:
        logger.warning(
            "remove_embargo_from_case_activity: invalid arguments: %s", exc
        )
        raise VultronActivityConstructionError(
            "remove_embargo_from_case_activity: invalid arguments"
        ) from exc
