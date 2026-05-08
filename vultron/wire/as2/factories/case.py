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
Factory functions for outbound Vultron case-management activities.

These are the sole public construction API for activities involving
``VulnerabilityCase`` objects. Internal activity subclasses are
imported here and MUST NOT be imported by callers.

Spec: ``specs/activity-factories.yaml`` AF-01-001 through AF-04-003.
"""

import logging
from typing import cast

from pydantic import ValidationError

from vultron.wire.as2.factories.errors import VultronActivityConstructionError
from vultron.wire.as2.vocab.activities.case import (
    _AcceptCaseManagerRoleActivity,
    _AcceptCaseOwnershipTransferActivity,
    _AddNoteToCaseActivity,
    _AddReportToCaseActivity,
    _AddStatusToCaseActivity,
    _AnnounceVulnerabilityCaseActivity,
    _CreateCaseActivity,
    _CreateCaseStatusActivity,
    _OfferCaseManagerRoleActivity,
    _OfferCaseOwnershipTransferActivity,
    _RejectCaseManagerRoleActivity,
    _RejectCaseOwnershipTransferActivity,
    _RmAcceptInviteToCaseActivity,
    _RmCloseCaseActivity,
    _RmDeferCaseActivity,
    _RmEngageCaseActivity,
    _RmInviteToCaseActivity,
    _RmRejectInviteToCaseActivity,
    _UpdateCaseActivity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Add,
    as_Announce,
    as_Create,
    as_Ignore,
    as_Invite,
    as_Join,
    as_Leave,
    as_Offer,
    as_Reject,
    as_Update,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor, as_ActorRef
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.case_participant import CaseParticipantRef
from vultron.wire.as2.vocab.objects.case_status import CaseStatus
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    VulnerabilityCase,
    VulnerabilityCaseRef,
    VulnerabilityCaseStub,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    VulnerabilityReport,
)

logger = logging.getLogger(__name__)


def add_report_to_case_activity(
    report: VulnerabilityReport,
    target: VulnerabilityCaseRef | None = None,
    **kwargs,
) -> as_Add:
    """Build an Add(VulnerabilityReport, target=VulnerabilityCase).

    Args:
        report: The ``VulnerabilityReport`` to add to the case.
        target: The ``VulnerabilityCase`` (or its URI) to which the
            report is being added.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``).

    Returns:
        An ``as_Add`` whose ``object_`` is the report and
        ``target`` is the case reference.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _AddReportToCaseActivity(
            object_=report, target=target, **kwargs
        )
    except ValidationError as exc:
        logger.warning(
            "add_report_to_case_activity: invalid arguments: %s", exc
        )
        raise VultronActivityConstructionError(
            "add_report_to_case_activity: invalid arguments"
        ) from exc


def add_status_to_case_activity(
    status: CaseStatus,
    target: VulnerabilityCaseRef | None = None,
    **kwargs,
) -> as_Add:
    """Build an Add(CaseStatus, target=VulnerabilityCase).

    Args:
        status: The ``CaseStatus`` to add.
        target: The ``VulnerabilityCase`` (or its URI) to which the
            status is being added.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``).

    Returns:
        An ``as_Add`` whose ``object_`` is the status.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _AddStatusToCaseActivity(
            object_=status, target=target, **kwargs
        )
    except ValidationError as exc:
        logger.warning(
            "add_status_to_case_activity: invalid arguments: %s", exc
        )
        raise VultronActivityConstructionError(
            "add_status_to_case_activity: invalid arguments"
        ) from exc


def create_case_activity(
    case: VulnerabilityCase,
    **kwargs,
) -> as_Create:
    """Build a Create(VulnerabilityCase).

    Args:
        case: The ``VulnerabilityCase`` being created.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``).

    Returns:
        An ``as_Create`` whose ``object_`` is the case.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _CreateCaseActivity(object_=case, **kwargs)
    except ValidationError as exc:
        logger.warning("create_case_activity: invalid arguments: %s", exc)
        raise VultronActivityConstructionError(
            "create_case_activity: invalid arguments"
        ) from exc


def create_case_status_activity(
    status: CaseStatus,
    **kwargs,
) -> as_Create:
    """Build a Create(CaseStatus).

    Args:
        status: The ``CaseStatus`` being created.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``).

    Returns:
        An ``as_Create`` whose ``object_`` is the status.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _CreateCaseStatusActivity(object_=status, **kwargs)
    except ValidationError as exc:
        logger.warning(
            "create_case_status_activity: invalid arguments: %s", exc
        )
        raise VultronActivityConstructionError(
            "create_case_status_activity: invalid arguments"
        ) from exc


def add_note_to_case_activity(
    note: as_Note,
    target: VulnerabilityCaseRef | None = None,
    **kwargs,
) -> as_Add:
    """Build an Add(Note, target=VulnerabilityCase).

    Args:
        note: The ``as_Note`` to add to the case.
        target: The ``VulnerabilityCase`` (or its URI) to which the
            note is being added.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``).

    Returns:
        An ``as_Add`` whose ``object_`` is the note.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _AddNoteToCaseActivity(object_=note, target=target, **kwargs)
    except ValidationError as exc:
        logger.warning("add_note_to_case_activity: invalid arguments: %s", exc)
        raise VultronActivityConstructionError(
            "add_note_to_case_activity: invalid arguments"
        ) from exc


def update_case_activity(
    case: VulnerabilityCase,
    **kwargs,
) -> as_Update:
    """Build an Update(VulnerabilityCase).

    Args:
        case: The updated ``VulnerabilityCase``.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``).

    Returns:
        An ``as_Update`` whose ``object_`` is the case.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _UpdateCaseActivity(object_=case, **kwargs)
    except ValidationError as exc:
        logger.warning("update_case_activity: invalid arguments: %s", exc)
        raise VultronActivityConstructionError(
            "update_case_activity: invalid arguments"
        ) from exc


def rm_engage_case_activity(
    case: VulnerabilityCase,
    **kwargs,
) -> as_Join:
    """Build a Join(VulnerabilityCase) — the RA message.

    Signals that the actor is now actively working on the case
    (``RM.ACCEPTED`` state).

    Args:
        case: The ``VulnerabilityCase`` being engaged.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``).

    Returns:
        An ``as_Join`` whose ``object_`` is the case.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _RmEngageCaseActivity(object_=case, **kwargs)
    except ValidationError as exc:
        logger.warning("rm_engage_case_activity: invalid arguments: %s", exc)
        raise VultronActivityConstructionError(
            "rm_engage_case_activity: invalid arguments"
        ) from exc


def rm_defer_case_activity(
    case: VulnerabilityCase,
    **kwargs,
) -> as_Ignore:
    """Build an Ignore(VulnerabilityCase) — the RD message.

    Signals that the actor is deferring work on the case
    (``RM.DEFERRED`` state).

    Args:
        case: The ``VulnerabilityCase`` being deferred.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``).

    Returns:
        An ``as_Ignore`` whose ``object_`` is the case.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _RmDeferCaseActivity(object_=case, **kwargs)
    except ValidationError as exc:
        logger.warning("rm_defer_case_activity: invalid arguments: %s", exc)
        raise VultronActivityConstructionError(
            "rm_defer_case_activity: invalid arguments"
        ) from exc


def rm_close_case_activity(
    case: VulnerabilityCase,
    **kwargs,
) -> as_Leave:
    """Build a Leave(VulnerabilityCase) — the RC message.

    Signals permanent closure / departure from the case.

    Args:
        case: The ``VulnerabilityCase`` being closed.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``).

    Returns:
        An ``as_Leave`` whose ``object_`` is the case.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _RmCloseCaseActivity(object_=case, **kwargs)
    except ValidationError as exc:
        logger.warning("rm_close_case_activity: invalid arguments: %s", exc)
        raise VultronActivityConstructionError(
            "rm_close_case_activity: invalid arguments"
        ) from exc


def offer_case_manager_role_activity(
    case: VulnerabilityCase,
    target: CaseParticipantRef | None = None,
    **kwargs,
) -> as_Offer:
    """Build an Offer(VulnerabilityCase, target=CaseParticipant) — CASE_MANAGER delegation.

    Distinct from :func:`offer_case_ownership_transfer_activity`: the offering
    actor retains ``CASE_OWNER``; only operational management authority is
    delegated to the Case Actor participant.

    The case MUST be passed as an inline ``VulnerabilityCase`` object and the
    target MUST be the ``CaseParticipant`` record for the Case Actor so that
    pattern matching can distinguish this activity from a case-ownership
    transfer (see DEMOMA-08-002, DEMOMA-08-003).

    Args:
        case: The ``VulnerabilityCase`` for which management is being delegated.
        target: The ``CaseParticipant`` record of the Case Actor being delegated
            the CASE_MANAGER role.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``).

    Returns:
        An ``as_Offer`` whose ``object_`` is the case and ``target`` is the
        Case Actor participant.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _OfferCaseManagerRoleActivity(
            object_=case, target=target, **kwargs
        )
    except ValidationError as exc:
        logger.warning(
            "offer_case_manager_role_activity: invalid arguments: %s",
            exc,
        )
        raise VultronActivityConstructionError(
            "offer_case_manager_role_activity: invalid arguments"
        ) from exc


def accept_case_manager_role_activity(
    offer: as_Offer,
    **kwargs,
) -> as_Accept:
    """Build an Accept(_OfferCaseManagerRoleActivity).

    The ``offer`` MUST be an ``_OfferCaseManagerRoleActivity`` (i.e., the
    value returned by :func:`offer_case_manager_role_activity`).  A plain
    ``as_Offer`` will fail Pydantic validation and raise
    :exc:`VultronActivityConstructionError`.

    Args:
        offer: The ``_OfferCaseManagerRoleActivity`` being accepted.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``).

    Returns:
        An ``as_Accept`` whose ``object_`` is the offer.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _AcceptCaseManagerRoleActivity(
            object_=cast(_OfferCaseManagerRoleActivity, offer),
            **kwargs,
        )
    except ValidationError as exc:
        logger.warning(
            "accept_case_manager_role_activity: invalid arguments: %s",
            exc,
        )
        raise VultronActivityConstructionError(
            "accept_case_manager_role_activity: invalid arguments"
        ) from exc


def reject_case_manager_role_activity(
    offer: as_Offer,
    **kwargs,
) -> as_Reject:
    """Build a Reject(_OfferCaseManagerRoleActivity).

    The ``offer`` MUST be an ``_OfferCaseManagerRoleActivity`` (i.e., the
    value returned by :func:`offer_case_manager_role_activity`).  A plain
    ``as_Offer`` will fail Pydantic validation and raise
    :exc:`VultronActivityConstructionError`.

    Args:
        offer: The ``_OfferCaseManagerRoleActivity`` being rejected.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``).

    Returns:
        An ``as_Reject`` whose ``object_`` is the offer.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _RejectCaseManagerRoleActivity(
            object_=cast(_OfferCaseManagerRoleActivity, offer),
            **kwargs,
        )
    except ValidationError as exc:
        logger.warning(
            "reject_case_manager_role_activity: invalid arguments: %s",
            exc,
        )
        raise VultronActivityConstructionError(
            "reject_case_manager_role_activity: invalid arguments"
        ) from exc


def offer_case_ownership_transfer_activity(
    case: VulnerabilityCase,
    target: as_ActorRef | None = None,
    **kwargs,
) -> as_Offer:
    """Build an Offer(VulnerabilityCase, target=Actor) — ownership transfer.

    The case MUST be passed as an inline ``VulnerabilityCase`` object, not
    a bare string ID, so the recipient can distinguish this activity from
    a ``SUBMIT_REPORT`` Offer during semantic pattern matching.

    Args:
        case: The ``VulnerabilityCase`` whose ownership is being offered.
        target: The actor (or actor URI) to whom ownership is offered.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``).

    Returns:
        An ``as_Offer`` whose ``object_`` is the case.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _OfferCaseOwnershipTransferActivity(
            object_=case, target=target, **kwargs
        )
    except ValidationError as exc:
        logger.warning(
            "offer_case_ownership_transfer_activity: invalid arguments: %s",
            exc,
        )
        raise VultronActivityConstructionError(
            "offer_case_ownership_transfer_activity: invalid arguments"
        ) from exc


def accept_case_ownership_transfer_activity(
    offer: as_Offer,
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
    try:
        return _AcceptCaseOwnershipTransferActivity(
            object_=cast(_OfferCaseOwnershipTransferActivity, offer),
            **kwargs,
        )
    except ValidationError as exc:
        logger.warning(
            "accept_case_ownership_transfer_activity: invalid arguments: %s",
            exc,
        )
        raise VultronActivityConstructionError(
            "accept_case_ownership_transfer_activity: invalid arguments"
        ) from exc


def reject_case_ownership_transfer_activity(
    offer: as_Offer,
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
    try:
        return _RejectCaseOwnershipTransferActivity(
            object_=cast(_OfferCaseOwnershipTransferActivity, offer),
            **kwargs,
        )
    except ValidationError as exc:
        logger.warning(
            "reject_case_ownership_transfer_activity: invalid arguments: %s",
            exc,
        )
        raise VultronActivityConstructionError(
            "reject_case_ownership_transfer_activity: invalid arguments"
        ) from exc


def rm_invite_to_case_activity(
    invitee: as_Actor,
    target: VulnerabilityCaseStub | str | None = None,
    **kwargs,
) -> as_Invite:
    """Build an Invite(Actor, target=VulnerabilityCase) — the RS message.

    Invites an actor to join a case that already exists.  See
    :func:`vultron.wire.as2.factories.report.rm_submit_report_activity`
    for the scenario where a case does not yet exist.

    Args:
        invitee: The ``as_Actor`` (or actor URI) being invited.
        target: The ``VulnerabilityCase`` (or its URI) to join.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor`` for the inviting party).

    Returns:
        An ``as_Invite`` whose ``object_`` is the invited actor.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _RmInviteToCaseActivity(
            object_=invitee, target=target, **kwargs
        )
    except ValidationError as exc:
        logger.warning(
            "rm_invite_to_case_activity: invalid arguments: %s", exc
        )
        raise VultronActivityConstructionError(
            "rm_invite_to_case_activity: invalid arguments"
        ) from exc


def rm_accept_invite_to_case_activity(
    invite: as_Invite,
    **kwargs,
) -> as_Accept:
    """Build an Accept(_RmInviteToCaseActivity) — the RV message.

    Accepts a case invitation.  The internal class automatically sets
    ``in_reply_to`` to the invite's ``id_`` if not provided.
    The ``invite`` MUST be the value returned by
    :func:`rm_invite_to_case_activity`; a plain ``as_Invite`` that does
    not carry a ``VulnerabilityCase`` target will fail validation.

    Args:
        invite: The ``_RmInviteToCaseActivity`` being accepted.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``in_reply_to``).

    Returns:
        An ``as_Accept`` whose ``object_`` is the invite.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _RmAcceptInviteToCaseActivity(
            object_=cast(_RmInviteToCaseActivity, invite),
            **kwargs,
        )
    except ValidationError as exc:
        logger.warning(
            "rm_accept_invite_to_case_activity: invalid arguments: %s", exc
        )
        raise VultronActivityConstructionError(
            "rm_accept_invite_to_case_activity: invalid arguments"
        ) from exc


def rm_reject_invite_to_case_activity(
    invite: as_Invite,
    **kwargs,
) -> as_Reject:
    """Build a Reject(_RmInviteToCaseActivity) — the RI message.

    Rejects a case invitation.  The internal class automatically sets
    ``in_reply_to`` to the invite's ``id_`` if not provided.
    The ``invite`` MUST be the value returned by
    :func:`rm_invite_to_case_activity`; a plain ``as_Invite`` will fail
    validation.

    Args:
        invite: The ``_RmInviteToCaseActivity`` being rejected.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``in_reply_to``).

    Returns:
        An ``as_Reject`` whose ``object_`` is the invite.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _RmRejectInviteToCaseActivity(
            object_=cast(_RmInviteToCaseActivity, invite),
            **kwargs,
        )
    except ValidationError as exc:
        logger.warning(
            "rm_reject_invite_to_case_activity: invalid arguments: %s", exc
        )
        raise VultronActivityConstructionError(
            "rm_reject_invite_to_case_activity: invalid arguments"
        ) from exc


def announce_vulnerability_case_activity(
    case: VulnerabilityCase,
    **kwargs,
) -> as_Announce:
    """Build an Announce(VulnerabilityCase) — sent by the case owner.

    Sent after an ``Accept(Invite)`` is received and the invitee's
    embargo consent has been verified.  The full case object is sent
    inline so the recipient can seed their local DataLayer.

    Args:
        case: The complete ``VulnerabilityCase`` being announced.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``).

    Returns:
        An ``as_Announce`` whose ``object_`` is the case.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _AnnounceVulnerabilityCaseActivity(object_=case, **kwargs)
    except ValidationError as exc:
        logger.warning(
            "announce_vulnerability_case_activity: invalid arguments: %s", exc
        )
        raise VultronActivityConstructionError(
            "announce_vulnerability_case_activity: invalid arguments"
        ) from exc
