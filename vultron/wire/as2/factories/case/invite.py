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
"""Factories for the stub Invite to a case and its replies (CM-11-001, CM-17-002).

Spec: ``specs/activity-factories.yaml`` AF-01-001 through AF-04-003.
"""

from typing import Any

from pydantic import ValidationError

from vultron.core.models.actor import CoreActor
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.dimensions import (
    EmDimension,
)
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
from vultron.wire.as2.vocab.objects.case_status import as_CaseStatus
from vultron.wire.as2.vocab.objects.embargo_event import (
    as_EmbargoEvent as WireEmbargoEvent,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
    as_VulnerabilityCaseStub,
)


def _project_case_to_stub(
    case: VulnerabilityCase,
    embargo_obj: Any,
) -> as_VulnerabilityCaseStub:
    """Project a ``VulnerabilityCase`` to a ``as_VulnerabilityCaseStub``.

    While an embargo is in force (``case.embargo_in_force``: EM ``ACTIVE`` or
    ``REVISE``) the stub carries ``case_status`` (with ``em_state``) and
    ``active_embargo`` so the invitee can give informed consent (CM-17-002).
    In ``REVISE`` that is the embargo in force, never the open revision, which
    is relayed after joining (EP-09-011).  ``active_embargo`` is the **full**
    embargo, every term as the inviter holds it, not just its ID and
    ``end_time``: this prototype builds no way for the invitee to ask for the
    embargo by ID (CM-17-011).  Builds a minimal stub when no embargo is in
    force.

    Refuses to build a stub when the case carries no ``stub_summary``
    (CM-17-010, MV-10-001, AC-2 of #4165): the owner must choose a summary
    before emitting a stub Invite so the invitee can evaluate the case.

    Args:
        case: The ``VulnerabilityCase`` to project (``as_VulnerabilityCase``
            is the same class, ARCH-25-003).
        embargo_obj: The fetched ``EmbargoEvent`` (core or wire), or ``None``
            when the case holds its active embargo inline.

    Raises:
        VultronActivityConstructionError: When the case carries no
            ``stub_summary``.  Set ``VulnerabilityCase.stub_summary`` before
            emitting a stub Invite (CM-17-010).  Also when the active
            embargo cannot be embedded whole (CM-17-011); see
            :func:`_stub_embargo`.
    """
    stub_summary = case.stub_summary
    if stub_summary is None:
        raise VultronActivityConstructionError(
            f"_project_case_to_stub: case {case.id_!r} has no "
            "'stub_summary' — set VulnerabilityCase.stub_summary before "
            "emitting a stub Invite (CM-17-010, MV-10-001)"
        )
    case_id = case.id_
    # EM is derived from the case's embargo register (ADR-0122).
    # "In force" is the register's ACTIVE entry, so it holds through a
    # revision (EM REVISE), not only while EM is exactly ACTIVE (CM-17-002).
    if not case.embargo_in_force:
        return as_VulnerabilityCaseStub(case_id=case_id, summary=stub_summary)
    em_state = case.em_state
    active_embargo = case.active_embargo
    embargo = _stub_embargo(active_embargo, embargo_obj, case_id)
    # ``context`` names the case this status belongs to.  It is required on the
    # core class (fail-fast, ARCH-10-001); the deleted wire class allowed it to be
    # absent because the wire branch was deliberately lenient (ARCH-12-002).
    wire_status = as_CaseStatus(
        context=case_id, em=EmDimension(state=em_state)
    )
    return as_VulnerabilityCaseStub(
        case_id=case_id,
        summary=stub_summary,
        active_embargo=embargo,
        case_status=wire_status,
    )


def _stub_embargo(
    active_embargo: str | WireEmbargoEvent | None,
    embargo_obj: object,
    case_id: str,
) -> WireEmbargoEvent:
    """The full embargo an enriched stub embeds (CM-17-002, CM-17-011).

    ``active_embargo`` is id-or-object: a case seeded from a sealed Announce
    carries the ``EmbargoEvent`` inline, a locally built one holds the id.  An
    inline object is its own *embargo_obj* when the caller supplied none.  The
    object is embedded as held, never rebuilt, so the invitee sees the terms
    the inviter holds, its start and name included.

    Raises:
        VultronActivityConstructionError: When the case names no active
            embargo, no embargo object is at hand (only its ID is known), or
            *embargo_obj* is not the case's active embargo.  A stub naming
            the embargo by ID alone would leave the invitee no way to read
            the terms, since the case host serves case objects only to active
            participants (AKM-05-006, CM-17-011), so it is not sent.
    """
    if active_embargo is None:
        raise VultronActivityConstructionError(
            f"_stub_embargo: case {case_id!r} has an embargo in force but"
            " names no active embargo, so the stub has no terms to embed"
            " (CM-17-002, CM-17-011)"
        )
    if isinstance(active_embargo, str):
        active_id = active_embargo
    else:
        active_id = active_embargo.id_
        if embargo_obj is None:
            embargo_obj = active_embargo
    if not isinstance(embargo_obj, WireEmbargoEvent):
        raise VultronActivityConstructionError(
            f"_stub_embargo: case {case_id!r} has active embargo"
            f" {active_id!r} but no EmbargoEvent object to embed in the stub"
            " — the stub carries the full embargo, not its ID (CM-17-002,"
            " CM-17-011)"
        )
    if embargo_obj.id_ != active_id:
        raise VultronActivityConstructionError(
            f"_stub_embargo: embargo {embargo_obj.id_!r} is not case"
            f" {case_id!r}'s active embargo {active_id!r} (CM-17-011)"
        )
    return embargo_obj


def rm_invite_to_case_activity(
    invitee: as_Actor | CoreActor | str,
    target: Any,
    roles: list[str] | None = None,
    embargo_obj: Any = None,
    **kwargs,
) -> as_Invite:
    """Build an Invite(Actor)[target=VulnerabilityCaseStub] — the stub Invite.

    Invites an actor to join a case that already exists.  It is not an RM
    message: it records no RM transition (CM-11-001, ADR-0114).  See
    :func:`vultron.wire.as2.factories.report.rm_submit_report_activity`
    for the scenario where a case does not yet exist.

    Args:
        invitee: The actor being invited: its profile as the sender holds
            it, or its URI, which travels as an actor reference (AKM-05-017).
        target: The case to join — either a ``VulnerabilityCase`` (projected
            to an enriched ``as_VulnerabilityCaseStub`` via
            :func:`_project_case_to_stub`), a pre-built ``as_VulnerabilityCaseStub``,
            or the case URI (wrapped in a bare stub).  The Invite's
            ``context`` defaults to the case URI, never the stub's ID.
        roles: Optional list of intended CVD role strings for the invitee
            (CM-17-003).  When provided the Invite carries the intended
            participant roles so ``CreateInertInviteeParticipantNode``
            can set them on the new inert ``CaseParticipant``.
        embargo_obj: The fetched ``EmbargoEvent`` for the case, used when
            *target* is a ``as_VulnerabilityCase`` with an embargo in force
            (EM ``ACTIVE`` or ``REVISE``) to embed the full embargo in the
            stub (CM-17-002, CM-17-011).
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor`` for the inviting party).

    Returns:
        An ``as_Invite`` whose ``object_`` is the invited actor.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails, the
            case carries no ``stub_summary`` (CM-17-010), or its active
            embargo cannot be embedded whole (CM-17-011).
    """
    if roles is not None:
        kwargs["roles"] = roles

    def fields() -> dict[str, Any]:
        stub = _stub_target(target, embargo_obj)
        return {
            "object_": carried_actor(invitee),
            "target": stub,
            **with_case_context(kwargs, stub),
        }

    return build_activity(
        "rm_invite_to_case_activity", _RmInviteToCaseActivity, fields
    )


def _stub_target(target: Any, embargo_obj: Any) -> Any:
    """The stub an Invite carries for *target*.

    A case is projected to its enriched stub.  A case named by URI alone
    still travels as a stub: the invitee does not hold the case, and the stub
    Invite is told apart by its target's ``type`` (CM-11-013, VAM-04-004).
    Run inside the factory's guarded scope, so a stub that fails validation
    is a construction error.
    """
    if isinstance(target, (VulnerabilityCase, as_VulnerabilityCase)):
        return _project_case_to_stub(target, embargo_obj)
    if isinstance(target, str):
        return as_VulnerabilityCaseStub(case_id=target)
    return target


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
        lambda: {"object_": _as_case_invite(invite), **kwargs},
    )


def rm_reject_invite_to_case_activity(
    invite: as_Invite,
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
        lambda: {"object_": _as_case_invite(invite), **kwargs},
    )
