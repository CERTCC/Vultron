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
``as_VulnerabilityCase`` objects. Internal activity subclasses are
imported here and MUST NOT be imported by callers.

Spec: ``specs/activity-factories.yaml`` AF-01-001 through AF-04-003.
"""

import json
import logging
from typing import Any, cast

from pydantic import ValidationError

from vultron.core.models.actor import CoreActor
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.dimensions import (
    EmDimension,
)
from vultron.core.states.em import EM
from vultron.enums.object_types import VultronObjectType
from vultron.enums.roles import CVDRole
from vultron.wire.as2.enums import as_TransitiveActivityType
from vultron.wire.as2.factories._context import (
    case_target_ref,
    case_uri_of,
    with_case_context,
)
from vultron.wire.as2.factories.errors import VultronActivityConstructionError
from vultron.wire.as2.vocab.activities.case import (
    _AcceptCaseOwnershipTransferActivity,
    _AcceptCaseParticipantRoleActivity,
    _AddNoteToCaseActivity,
    _AddReportToCaseActivity,
    _AddStatusToCaseActivity,
    _AnnounceVulnerabilityCaseActivity,
    _CreateCaseActivity,
    _CreateCaseStatusActivity,
    _OfferCaseOwnershipTransferActivity,
    _OfferCaseParticipantRoleActivity,
    _RejectCaseOwnershipTransferActivity,
    _RejectCaseParticipantRoleActivity,
    _RmAcceptInviteToCaseActivity,
    _RmCloseCaseActivity,
    _RmDeferCaseActivity,
    _RmEngageCaseActivity,
    _RmInviteToCaseActivity,
    _RmRejectCloseCaseActivity,
    _RmRejectInviteToCaseActivity,
    _UpdateCaseActivity,
)
from vultron.wire.as2.vocab.base.objects.activities.intransitive import (
    as_Question,
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
from vultron.wire.as2.vocab.objects.case_participant_role import (
    as_CaseParticipantRole,
)
from vultron.wire.as2.vocab.objects.case_proposal import as_CaseProposal
from vultron.wire.as2.vocab.objects.case_status import as_CaseStatus
from vultron.wire.as2.vocab.objects.embargo_event import (
    as_EmbargoEvent as WireEmbargoEvent,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
    as_VulnerabilityCaseRef,
    as_VulnerabilityCaseStub,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

logger = logging.getLogger(__name__)


def _project_case_to_stub(
    case: Any,
    embargo_obj: Any,
) -> as_VulnerabilityCaseStub:
    """Project a ``as_VulnerabilityCase`` (core or wire) to a ``as_VulnerabilityCaseStub``.

    When ``em_state == EM.ACTIVE`` and *embargo_obj* is provided, the stub
    carries ``active_embargo`` (ID + ``end_time``) and ``case_status``
    (with ``em_state``) so the invitee can give informed consent (CM-17-002).
    Falls back to a minimal stub when the case has no active embargo.

    Args:
        case: A core or wire ``as_VulnerabilityCase`` to project.
        embargo_obj: The fetched ``EmbargoEvent`` (core or wire), or ``None``.
    """
    case_id = case.id_
    try:
        current_status = case.current_status
    except (ValueError, AttributeError):
        return as_VulnerabilityCaseStub(case_id=case_id)
    # Support both core CaseStatus (.em.state) and wire as_CaseStatus (.em_state)
    if hasattr(current_status, "em") and hasattr(current_status.em, "state"):
        em_state = current_status.em.state
    else:
        em_state = getattr(current_status, "em_state", None)
    active_embargo = getattr(case, "active_embargo", None)
    if em_state != EM.ACTIVE or active_embargo is None:
        return as_VulnerabilityCaseStub(case_id=case_id)
    embargo_ref = _stub_embargo_ref(active_embargo, embargo_obj, case_id)
    if embargo_ref is None:
        return as_VulnerabilityCaseStub(case_id=case_id)
    # ``context`` names the case this status belongs to.  It is required on the
    # core class (fail-fast, ARCH-10-001); the deleted wire class allowed it to be
    # absent because the wire branch was deliberately lenient (ARCH-12-002).
    wire_status = as_CaseStatus(
        context=case_id, em=EmDimension(state=em_state)
    )
    return as_VulnerabilityCaseStub(
        case_id=case_id,
        active_embargo=embargo_ref,
        case_status=wire_status,
    )


def _stub_embargo_ref(
    active_embargo: Any,
    embargo_obj: Any,
    case_id: str,
) -> WireEmbargoEvent | str | None:
    """The ``active_embargo`` an enriched stub carries (CM-17-002).

    ``active_embargo`` is id-or-object: a case seeded from a sealed Announce
    carries the ``EmbargoEvent`` inline, a locally built one holds the id.  The
    stub names the embargo by id either way, and an inline object is its own
    *embargo_obj* when the caller supplied none.  Returns the id alone when no
    end time is known, and ``None`` when there is no usable id at all.
    """
    if isinstance(active_embargo, str):
        active_embargo_uri: Any = active_embargo
    else:
        active_embargo_uri = getattr(active_embargo, "id_", None)
        if embargo_obj is None:
            embargo_obj = active_embargo
    if not isinstance(active_embargo_uri, str) or not active_embargo_uri:
        return None
    end_time = getattr(embargo_obj, "end_time", None)
    if end_time is None:
        return active_embargo_uri
    try:
        return WireEmbargoEvent(
            id_=active_embargo_uri, end_time=end_time, context=case_id
        )
    except ValidationError as exc:
        logger.warning(
            "_project_case_to_stub: could not build WireEmbargoEvent"
            " for %r — falling back to bare URI: %s",
            active_embargo_uri,
            exc,
        )
        return active_embargo_uri


def add_report_to_case_activity(
    report: as_VulnerabilityReport,
    target: as_VulnerabilityCaseRef | None = None,
    **kwargs,
) -> as_Add:
    """Build an Add(as_VulnerabilityReport, target=as_VulnerabilityCase).

    Args:
        report: The ``as_VulnerabilityReport`` to add to the case.
        target: The ``as_VulnerabilityCase`` (or its URI) to which the
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
            object_=report, target=case_target_ref(target), **kwargs
        )
    except ValidationError as exc:
        logger.warning(
            "add_report_to_case_activity: invalid arguments: %s", exc
        )
        raise VultronActivityConstructionError(
            "add_report_to_case_activity: invalid arguments"
        ) from exc


def add_status_to_case_activity(
    status: as_CaseStatus,
    target: as_VulnerabilityCaseRef | None = None,
    **kwargs,
) -> as_Add:
    """Build an Add(as_CaseStatus, target=as_VulnerabilityCase).

    Args:
        status: The ``as_CaseStatus`` to add.
        target: The ``as_VulnerabilityCase`` (or its URI) to which the
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
            object_=status, target=case_target_ref(target), **kwargs
        )
    except ValidationError as exc:
        logger.warning(
            "add_status_to_case_activity: invalid arguments: %s", exc
        )
        raise VultronActivityConstructionError(
            "add_status_to_case_activity: invalid arguments"
        ) from exc


def create_case_activity(
    case: as_VulnerabilityCase,
    **kwargs,
) -> as_Create:
    """Build a Create(as_VulnerabilityCase).

    Args:
        case: The ``as_VulnerabilityCase`` being created.
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
    status: as_CaseStatus,
    **kwargs,
) -> as_Create:
    """Build a Create(as_CaseStatus).

    Args:
        status: The ``as_CaseStatus`` being created.
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
    target: as_VulnerabilityCaseRef | None = None,
    **kwargs,
) -> as_Add:
    """Build an Add(Note, target=as_VulnerabilityCase).

    Args:
        note: The ``as_Note`` to add to the case.
        target: The ``as_VulnerabilityCase`` (or its URI) to which the
            note is being added.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``).

    Returns:
        An ``as_Add`` whose ``object_`` is the note.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _AddNoteToCaseActivity(
            object_=note, target=case_target_ref(target), **kwargs
        )
    except ValidationError as exc:
        logger.warning("add_note_to_case_activity: invalid arguments: %s", exc)
        raise VultronActivityConstructionError(
            "add_note_to_case_activity: invalid arguments"
        ) from exc


def update_case_activity(
    case: as_VulnerabilityCase,
    **kwargs,
) -> as_Update:
    """Build an Update(as_VulnerabilityCase).

    Args:
        case: The updated ``as_VulnerabilityCase``.
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
    case: as_VulnerabilityCase,
    **kwargs,
) -> as_Join:
    """Build a Join(as_VulnerabilityCase) — the RA message.

    Signals that the actor is now actively working on the case
    (``RM.ACCEPTED`` state).

    Args:
        case: The ``as_VulnerabilityCase`` being engaged.
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
    case: as_VulnerabilityCase,
    **kwargs,
) -> as_Ignore:
    """Build an Ignore(as_VulnerabilityCase) — the RD message.

    Signals that the actor is deferring work on the case
    (``RM.DEFERRED`` state).

    Args:
        case: The ``as_VulnerabilityCase`` being deferred.
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
    case: as_VulnerabilityCase,
    **kwargs,
) -> as_Leave:
    """Build a Leave(as_VulnerabilityCase) — the RC message.

    Signals permanent closure / departure from the case.

    Args:
        case: The ``as_VulnerabilityCase`` being closed.
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


def offer_case_participant_role_activity(
    role: CVDRole,
    target_actor: as_Actor,
    case: as_VulnerabilityCase | str,
    **kwargs,
) -> as_Offer:
    """Build Offer(CaseParticipantRole, target=Actor, context=VulnerabilityCase).

    This is the canonical role-delegation wire format introduced in ADR-0039.
    It replaces the deprecated ``offer_case_manager_role_activity`` format
    (``Offer(VulnerabilityCase, target=CaseParticipant)``) which was structurally
    ambiguous with ownership-transfer offers.

    The ``as_CaseParticipantRole`` object carries the specific ``CVDRole`` being
    offered, making the activity self-describing.  The ``target`` is the Actor
    receiving the role; the case is carried in ``context``.

    Args:
        role: The ``CVDRole`` to offer.  Becomes the ``role`` field on the
            ``as_CaseParticipantRole`` object.
        target_actor: The ``as_Actor`` that will receive the role offer.
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
            target=target_actor,
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


def offer_case_ownership_transfer_activity(
    case: as_VulnerabilityCase,
    target: as_ActorRef | None = None,
    **kwargs,
) -> as_Offer:
    """Build an Offer(as_VulnerabilityCase, target=Actor) — ownership transfer.

    The case MUST be passed as an inline ``as_VulnerabilityCase`` object, not
    a bare string ID, so the recipient can distinguish this activity from
    a ``SUBMIT_REPORT`` Offer during semantic pattern matching.

    Args:
        case: The ``as_VulnerabilityCase`` whose ownership is being offered.
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
    invitee: as_Actor | str,
    target: Any,
    roles: list[str] | None = None,
    embargo_obj: Any = None,
    **kwargs,
) -> as_Invite:
    """Build an Invite(Actor, target=VulnerabilityCaseStub) — the RS message.

    Invites an actor to join a case that already exists.  See
    :func:`vultron.wire.as2.factories.report.rm_submit_report_activity`
    for the scenario where a case does not yet exist.

    Args:
        invitee: The ``as_Actor`` (or actor URI) being invited.
        target: The case to join — either a ``as_VulnerabilityCase`` (core or wire;
            projected to an enriched ``as_VulnerabilityCaseStub`` via
            :func:`_project_case_to_stub`), a pre-built ``as_VulnerabilityCaseStub``,
            or the case URI (wrapped in a bare stub).  The Invite's
            ``context`` defaults to the case URI, never the stub's ID.
        roles: Optional list of intended CVD role strings for the invitee
            (CM-17-003).  When provided the Invite carries the intended
            participant roles so ``CreateInviteeParticipantNode``
            can set them on the new ``CaseParticipant``.
        embargo_obj: The fetched ``EmbargoEvent`` for the case, used when
            *target* is a ``as_VulnerabilityCase`` and ``em_state == EM.ACTIVE``
            to include ``end_time`` in the stub (CM-17-002).
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor`` for the inviting party).

    Returns:
        An ``as_Invite`` whose ``object_`` is the invited actor.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    if isinstance(target, (VulnerabilityCase, as_VulnerabilityCase)):
        target = _project_case_to_stub(target, embargo_obj)
    elif isinstance(target, str):
        # A case named by URI alone still travels as a stub: the invitee does
        # not hold the case, and the stub Invite is told apart by its target's
        # ``type`` (CM-11-013, VAM-04-004).
        target = as_VulnerabilityCaseStub(case_id=target)
    if isinstance(invitee, str):
        invitee = as_Actor(id_=invitee)
    if roles is not None:
        kwargs["roles"] = roles
    try:
        return _RmInviteToCaseActivity(
            object_=invitee,
            target=target,
            **with_case_context(kwargs, target),
        )
    except ValidationError as exc:
        logger.warning(
            "rm_invite_to_case_activity: invalid arguments: %s", exc
        )
        raise VultronActivityConstructionError(
            "rm_invite_to_case_activity: invalid arguments"
        ) from exc


def validate_held_case_invite(data: dict[str, Any]) -> as_Invite:
    """Validate a held Invite's JSON form into ``as_Invite``, stub and all.

    ``as_Invite.target`` is a generic ``as_Object`` slot, which keeps none of
    a stub's own fields, so a target whose ``type`` is ``VulnerabilityCaseStub``
    is validated as the stub itself (CM-11-013).  Any other target is kept as
    the generic slot holds it, for :func:`_as_case_invite` to refuse.

    Raises:
        pydantic.ValidationError: when *data* is not an Invite, or its stub
            does not validate (for example, it has no ``caseId``).
    """
    invite = as_Invite.model_validate(data)
    stub = data.get("target")
    if (
        isinstance(stub, dict)
        and stub.get("type") == VultronObjectType.VULNERABILITY_CASE_STUB.value
    ):
        invite = invite.model_copy(
            update={"target": as_VulnerabilityCaseStub.model_validate(stub)}
        )
    return invite


def _as_case_invite(invite: as_Invite) -> _RmInviteToCaseActivity:
    """Return *invite* as the case-Invite class the reply activities embed.

    An Invite the invitee holds came through intake, which archives the
    activity as the event carried it (CLP-10-017, ADR-0111) — not as this
    class.  The caller validates that record into ``as_Invite`` at its edge
    (ADR-0032); this function validates it on into the case-Invite class from
    its JSON form.  Neither class checks the input's ``type`` (both set their
    own), so it is checked here first.

    Raises:
        VultronActivityConstructionError: when *invite* is not an Invite, or
            does not validate as a case Invite.
    """
    if isinstance(invite, _RmInviteToCaseActivity):
        return invite
    data = json.loads(
        invite.model_dump_json(by_alias=True, serialize_as_any=True)
    )
    if data.get("type") != as_TransitiveActivityType.INVITE.value:
        raise VultronActivityConstructionError(
            f"activity '{data.get('id')}' is not a case Invite:"
            f" its type is {data.get('type')!r}"
        )
    try:
        return _RmInviteToCaseActivity.model_validate(data)
    except ValidationError as exc:
        raise VultronActivityConstructionError(
            f"activity '{data.get('id')}' is not a case Invite"
        ) from exc


def rm_accept_invite_to_case_activity(
    invite: as_Invite,
    **kwargs,
) -> as_Accept:
    """Build an Accept(_RmInviteToCaseActivity) — the RV message.

    Accepts a case invitation.  The internal class automatically sets
    ``in_reply_to`` to the invite's ``id_`` if not provided.
    The ``invite`` is the value :func:`rm_invite_to_case_activity`
    returned, or a received Invite the caller has validated into
    ``as_Invite``; it is validated on into the case-Invite class, and
    anything that is not a case Invite fails.

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
            object_=_as_case_invite(invite),
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
    The ``invite`` is the value :func:`rm_invite_to_case_activity`
    returned, or a received Invite the caller has validated into
    ``as_Invite``; it is validated on into the case-Invite class, and
    anything that is not a case Invite fails.

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
            object_=_as_case_invite(invite),
            **kwargs,
        )
    except ValidationError as exc:
        logger.warning(
            "rm_reject_invite_to_case_activity: invalid arguments: %s", exc
        )
        raise VultronActivityConstructionError(
            "rm_reject_invite_to_case_activity: invalid arguments"
        ) from exc


def reject_close_case_activity(
    leave: as_Leave,
    **kwargs,
) -> as_Reject:
    """Build a Reject(_RmCloseCaseActivity) — declines an owner close (CM-23-011).

    Per ActivityStreams convention the Case Actor rejects the
    ``Leave(VulnerabilityCase)`` activity itself.  The ``leave`` MUST be the
    value returned by :func:`rm_close_case_activity`; a plain ``as_Leave``
    will fail validation.

    Args:
        leave: The ``_RmCloseCaseActivity`` (the Leave) being declined.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``, ``in_reply_to``).

    Returns:
        An ``as_Reject`` whose ``object_`` is the leave.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _RmRejectCloseCaseActivity(
            object_=cast(_RmCloseCaseActivity, leave),
            **kwargs,
        )
    except ValidationError as exc:
        logger.warning(
            "reject_close_case_activity: invalid arguments: %s", exc
        )
        raise VultronActivityConstructionError(
            "reject_close_case_activity: invalid arguments"
        ) from exc


def announce_vulnerability_case_activity(
    case: as_VulnerabilityCase,
    **kwargs,
) -> as_Announce:
    """Build an Announce(as_VulnerabilityCase) — sent by the case owner.

    Sent after an ``Accept(Invite)`` is received and the invitee's
    embargo consent has been verified.  The full case object is sent
    inline so the recipient can seed their local DataLayer.

    Args:
        case: The complete ``as_VulnerabilityCase`` being announced.
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


def bootstrap_replay_question_activity(
    actor: str,
    to: list[str],
    case_id: str,
    **kwargs,
) -> as_Question:
    """Build a Question requesting replay of the bootstrap Create(as_VulnerabilityCase).

    Sent by the receiving actor to the (suspected) case creator when the
    pre-bootstrap inbox queue expires without a valid bootstrap arriving
    (CBT-03-004).

    Args:
        actor: URI of the actor sending the Question (the one waiting for
            bootstrap).
        to: URIs of the actors that should resend the bootstrap (the case
            creator / original report receiver).  A list, like every other
            factory's ``to``: delivery validates it as ``list[str]``.
        case_id: URI of the case whose bootstrap is being requested.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``name``).

    Returns:
        An ``as_Question`` whose ``context`` is the case URI.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return as_Question(
            actor=actor,
            to=to,
            context=case_id,
            name=kwargs.pop(
                "name",
                f"Please resend bootstrap Create(as_VulnerabilityCase) for {case_id}",
            ),
            **kwargs,
        )
    except ValidationError as exc:
        logger.warning(
            "bootstrap_replay_question_activity: invalid arguments: %s", exc
        )
        raise VultronActivityConstructionError(
            "bootstrap_replay_question_activity: invalid arguments"
        ) from exc


def create_case_proposal_activity(
    actor: CoreActor | as_Actor,
    proposal: as_CaseProposal,
    to: list[str],
    **kwargs,
) -> as_Create:
    """Build a ``Create(as_CaseProposal)`` sent by the vendor actor.

    The vendor actor sends this to the case-actor service to initiate the
    case initialization protocol (CP-04-001).  The ``as_CaseProposal``
    is embedded inline so the case-actor service has full context without
    an additional round-trip, and so is the sender's own actor profile: it
    carries the embargo policy that is the CASE_OWNER's actor default, and
    the CASE_MANAGER reads that default from nowhere else (CP-01-010).

    Args:
        actor: The sending actor's full profile, with its ``embargo_policy``
            when it has published one.  Its ``id`` must be the proposal's
            ``attributed_to``.
        proposal: The ``as_CaseProposal`` being created (embedded inline as
            ``object_``).
        to: List of recipient URIs (typically the case-actor service URI).
        **kwargs: Optional AS2 fields forwarded to the constructor.

    Returns:
        An ``as_Create`` whose ``object_`` is the ``as_CaseProposal``.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails, or
            *actor* is not the proposal's ``attributed_to``.
    """
    if actor.id_ != proposal.attributed_to:
        raise VultronActivityConstructionError(
            f"create_case_proposal_activity: actor {actor.id_!r} is not the"
            f" proposal's attributed_to {proposal.attributed_to!r}"
            " (CP-01-010)"
        )
    try:
        return as_Create(
            actor=actor,
            object_=proposal,
            to=to,
            **kwargs,
        )
    except ValidationError as exc:
        logger.warning(
            "create_case_proposal_activity: invalid arguments: %s", exc
        )
        raise VultronActivityConstructionError(
            "create_case_proposal_activity: invalid arguments"
        ) from exc


def accept_case_proposal_activity(
    actor_id: str,
    proposal: as_CaseProposal,
    to: list[str],
    **kwargs,
) -> as_Accept:
    """Build an ``Accept(as_CaseProposal)`` sent by the case-actor service.

    The case-actor service sends this to acknowledge that it will create a
    ``as_VulnerabilityCase`` from the vendor's proposal.  A separate
    ``Create(as_VulnerabilityCase)`` follows (CP-05-003).

    Args:
        actor_id: URI of the case-actor service that is accepting the proposal.
        proposal: The ``as_CaseProposal`` being accepted (embedded inline as
            ``object_``).
        to: List of recipient URIs (typically the vendor actor URI).
        **kwargs: Optional AS2 fields forwarded to the constructor.

    Returns:
        An ``as_Accept`` whose ``object_`` is the ``as_CaseProposal``.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return as_Accept(
            actor=actor_id,
            object_=proposal,
            to=to,
            **kwargs,
        )
    except ValidationError as exc:
        logger.warning(
            "accept_case_proposal_activity: invalid arguments: %s", exc
        )
        raise VultronActivityConstructionError(
            "accept_case_proposal_activity: invalid arguments"
        ) from exc


def reject_case_proposal_activity(
    actor_id: str,
    proposal: as_CaseProposal,
    to: list[str],
    **kwargs,
) -> as_Reject:
    """Build a ``Reject(as_CaseProposal)`` sent by the case-actor service.

    The case-actor service sends this when it declines the vendor's proposal
    (CP-05-004).  The ``as_CaseProposal`` is embedded inline so the vendor
    has full proposal context without an additional round-trip.

    Args:
        actor_id: URI of the case-actor service that is rejecting the proposal.
        proposal: The ``as_CaseProposal`` being rejected (embedded inline as
            ``object_``).
        to: List of recipient URIs (typically the vendor actor URI).
        **kwargs: Optional AS2 fields forwarded to the constructor.

    Returns:
        An ``as_Reject`` whose ``object_`` is the ``as_CaseProposal``.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return as_Reject(
            actor=actor_id,
            object_=proposal,
            to=to,
            **kwargs,
        )
    except ValidationError as exc:
        logger.warning(
            "reject_case_proposal_activity: invalid arguments: %s", exc
        )
        raise VultronActivityConstructionError(
            "reject_case_proposal_activity: invalid arguments"
        ) from exc
