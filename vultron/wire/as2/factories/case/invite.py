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
"""Factories for the stub Invite to a case and its replies (CM-11-001, CM-17-010).

Spec: ``specs/activity-factories.yaml`` AF-01-001 through AF-04-003.
"""

from datetime import datetime
from typing import Any

from pydantic import ValidationError

from vultron.core.models.actor import CoreActor
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_preview_profile import INVITATION_PROFILE
from vultron.core.models.enums import VultronObjectType as VO_type
from vultron.wire.as2.enums import as_TransitiveActivityType
from vultron.wire.as2.factories._actor import carried_actor
from vultron.wire.as2.factories._construct import build_activity
from vultron.wire.as2.factories._context import (
    with_case_context,
)
from vultron.wire.as2.factories._held import (
    embedded_as_received,
    validated_as,
)
from vultron.wire.as2.factories.errors import VultronActivityConstructionError
from vultron.wire.as2.typed_reference import as_TypedReference
from vultron.wire.as2.vocab.activities.case.invite import (
    _RmAcceptInviteToCaseActivity,
    _RmInviteToCaseActivity,
    _RmRejectInviteToCaseActivity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Invite,
    as_Reject,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.case_preview import as_CasePreview


def rm_invite_to_case_activity(
    invitee: as_Actor | CoreActor | str,
    case: VulnerabilityCase,
    roles: list[str] | None = None,
    *,
    at: datetime,
    **kwargs,
) -> as_Invite:
    """Build an Invite(<case>)[target=<invitee>] — the stub Invite.

    Invites an actor to join a case that already exists.  It is not an RM
    message: it records no RM transition (CM-11-001, ADR-0114).  See
    :func:`vultron.wire.as2.factories.report.rm_submit_report_activity`
    for the scenario where a case does not yet exist.

    The ``object`` is the typed reference naming the case by its ``id``,
    carrying the case's preview, the case stub (CM-11-013, ADR-0205).  The
    preview is cut from *case* by
    :data:`~vultron.core.models.case_preview_profile.INVITATION_PROFILE`
    (:meth:`~vultron.core.models.case_preview.CasePreview.from_case`,
    CM-17-010, ADR-0217): the owner's ``stub_summary``, the case name and
    times, the Case Owner, the current status, each vul item's ``ids`` and,
    while an embargo is in force (EM ``ACTIVE`` or ``REVISE``), the in-force
    embargo whole, with its status, never the open revision
    (CM-17-011, EP-09-011).  Every other value the case holds is marked
    ``Redacted``.  The invitee is the ``target``.

    Args:
        invitee: The actor being invited: its profile as the sender holds
            it, or its URI, which travels as an actor reference (AKM-05-017).
        case: The case to join.  A case named by URI alone is refused: the
            preview is built from the case, and an Invite without one would
            leave the invitee nothing to decide on (CM-17-010).  The Invite's
            ``context`` defaults to the case URI.
        roles: Optional list of intended CVD role strings for the invitee
            (CM-17-003).  When provided the Invite carries the intended
            participant roles so the seating node
            can set them on the new inert ``CaseParticipant``.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor`` for the inviting party).

    Returns:
        An ``as_Invite`` whose ``object_`` is the previewed case reference
        and whose ``target`` is the invited actor.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails,
            *case* is not a ``VulnerabilityCase``, the case carries no
            ``stub_summary`` (CM-17-010).
    """
    if not isinstance(case, VulnerabilityCase):
        raise VultronActivityConstructionError(
            "rm_invite_to_case_activity: the stub Invite needs the case to"
            f" build its preview from, not {type(case).__name__}"
            f" {case!r} (CM-17-010, ADR-0205)"
        )
    if roles is not None:
        kwargs["roles"] = roles

    def fields() -> dict[str, Any]:
        return {
            "object_": as_TypedReference(
                type_=VO_type.VULNERABILITY_CASE.value,
                id_=case.id_,
                preview=as_CasePreview.from_case(case, INVITATION_PROFILE),
            ),
            "target": carried_actor(invitee),
            **with_case_context(kwargs, case.id_),
        }

    return build_activity(
        "rm_invite_to_case_activity", _RmInviteToCaseActivity, at, fields
    )


def _as_case_invite(invite: as_Invite) -> _RmInviteToCaseActivity:
    """Return *invite* as the case-Invite class the reply activities embed.

    An Invite the invitee holds came through intake, which archives the body
    that arrived (CLP-10-017, ADR-0149); the caller parses it into
    ``as_Invite`` at its edge (ADR-0032).  This function validates it on into
    the case-Invite class from its JSON form, and the copy embeds the
    received body verbatim (:func:`embedded_as_received`).  Neither class
    checks the input's ``type`` (both set their own), so it is checked here
    first.

    Raises:
        VultronActivityConstructionError: when *invite* is not an Invite, or
            does not validate as a case Invite.
    """
    if isinstance(invite, _RmInviteToCaseActivity):
        return embedded_as_received(invite, invite)
    if invite.type_ != as_TransitiveActivityType.INVITE.value:
        raise VultronActivityConstructionError(
            f"activity '{invite.id_}' is not a case Invite:"
            f" its type is {invite.type_!r}"
        )
    try:
        case_invite = validated_as(_RmInviteToCaseActivity, invite)
    except ValidationError as exc:
        raise VultronActivityConstructionError(
            f"activity '{invite.id_}' is not a case Invite"
        ) from exc
    # The reply embeds the Invite as its sender sent it (DL-06-004).
    return embedded_as_received(case_invite, invite)


def rm_accept_invite_to_case_activity(
    invite: as_Invite,
    *,
    at: datetime,
    **kwargs,
) -> as_Accept:
    """Build an Accept(_RmInviteToCaseActivity) — join the case.

    Accepts the stub Invite.  This is joining, not an RM message: the
    participant stays at ``RM.RECEIVED`` (CM-11-001).  The RV message is
    :func:`rm_accept_full_case_invite_activity`.  The internal class automatically sets
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
    return build_activity(
        "rm_accept_invite_to_case_activity",
        _RmAcceptInviteToCaseActivity,
        at,
        lambda: {"object_": _as_case_invite(invite), **kwargs},
    )


def rm_reject_invite_to_case_activity(
    invite: as_Invite,
    *,
    at: datetime,
    **kwargs,
) -> as_Reject:
    """Build a Reject(_RmInviteToCaseActivity) — a hard no to joining (RC).

    Rejects the stub Invite, which closes the participant's RM state
    (``RM.RECEIVED`` to ``RM.CLOSED``, CM-11-007).  The RI message is
    :func:`rm_tentative_reject_full_case_invite_activity`; a stub Invite has
    no tentative reject.  The internal class automatically sets
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
    return build_activity(
        "rm_reject_invite_to_case_activity",
        _RmRejectInviteToCaseActivity,
        at,
        lambda: {"object_": _as_case_invite(invite), **kwargs},
    )
