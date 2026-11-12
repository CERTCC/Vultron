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
"""Factories for the full-case Invite and its RV, RI and RC replies (ADR-0121).

Spec: ``specs/activity-factories.yaml`` AF-01-001 through AF-04-003.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Any, TypeVar

from pydantic import ValidationError

from vultron.core.models.actor import CoreActor
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.ledger_position import LedgerPosition
from vultron.wire.as2.factories._actor import carried_actor
from vultron.wire.as2.factories._construct import build_activity
from vultron.wire.as2.factories._context import (
    with_case_context,
)
from vultron.wire.as2.factories._held import (
    answered_fields,
)
from vultron.wire.as2.factories.errors import VultronActivityConstructionError
from vultron.wire.as2.vocab.activities.case.invite import (
    _RmAcceptFullCaseInviteActivity,
    _RmInviteToFullCaseActivity,
    _RmRejectFullCaseInviteActivity,
    _RmTentativeRejectFullCaseInviteActivity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Invite,
    as_Reject,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor


def rm_invite_to_full_case_activity(
    invitee: as_Actor | CoreActor | str,
    case: VulnerabilityCase | str,
    ledger_tail: LedgerPosition,
    *,
    at: datetime,
    **kwargs,
) -> as_Invite:
    """Build an Invite(Actor)[target=VulnerabilityCase] — the full-case Invite.

    The CASE_MANAGER asks a joined participant to judge the case (CM-11-010,
    VAM-04-011, ADR-0121).  The participant already holds the case from the
    Announce, so the target is the plain case URI (AKM-02-003).  The
    CASE_MANAGER's *ledger_tail*, the floor the participant's reply must
    reach, is the Invite's ``ledgerPosition`` (SYNC-18-001, VAM-04-011).

    Args:
        invitee: The actor being asked: its profile as the sender holds it,
            or its URI, which travels as an actor reference (AKM-05-017).
        case: The case, or its URI.
        ledger_tail: The CASE_MANAGER's ledger position when it issues the
            Invite.
        **kwargs: Optional AS2 fields forwarded to the constructor (``actor``,
            ``to``, ``id_``, ...).  ``context`` defaults to the case URI.

    Returns:
        An ``as_Invite`` whose ``object_`` is the invited actor, whose
        ``target`` is the case URI and whose ``ledgerPosition`` is the position.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    case_id = case if isinstance(case, str) else case.id_
    return build_activity(
        "rm_invite_to_full_case_activity",
        _RmInviteToFullCaseActivity,
        at,
        lambda: {
            "object_": carried_actor(invitee),
            "target": case_id,
            "ledger_position": ledger_tail,
            **with_case_context(kwargs, case_id),
        },
    )


def _as_full_case_invite(invite: as_Invite) -> _RmInviteToFullCaseActivity:
    """Return *invite* as the full-case Invite class the replies embed.

    The counterpart of :func:`_as_case_invite`: an Invite the participant
    holds came through intake as the generic ``as_Invite``, and is validated
    on from its JSON form.

    A read-back rehydrates the Invite's ``target`` into the stored case; the
    reply addresses the case by URI, as the Invite did (AKM-02-003).

    Raises:
        VultronActivityConstructionError: when *invite* is not a full-case
            Invite (no case URI target, or no ``ledgerPosition``).
    """
    if isinstance(invite, _RmInviteToFullCaseActivity):
        return invite
    data = answered_fields(invite)
    target = data.get("target")
    if isinstance(target, dict):
        data["target"] = target.get("id")
    try:
        return _RmInviteToFullCaseActivity.model_validate(data)
    except ValidationError as exc:
        raise VultronActivityConstructionError(
            f"activity '{data.get('id')}' is not a full-case Invite"
        ) from exc


_Reply = TypeVar("_Reply")


def _full_case_reply(
    reply_class: Callable[..., _Reply],
    label: str,
    invite: as_Invite,
    ledger_tail: LedgerPosition,
    kwargs: dict[str, Any],
    *,
    at: datetime,
) -> _Reply:
    return build_activity(
        label,
        reply_class,
        at,
        lambda: {
            "object_": _as_full_case_invite(invite),
            "ledger_position": ledger_tail,
            **kwargs,
        },
    )


def rm_accept_full_case_invite_activity(
    invite: as_Invite,
    ledger_tail: LedgerPosition,
    *,
    at: datetime,
    **kwargs,
) -> as_Accept:
    """Build Accept(full-case Invite) — RV, carrying the replier's position.

    The participant judges the case valid (CM-11-011, VAM-04-012).
    *ledger_tail* is the replier's own ledger position when it decided.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    return _full_case_reply(
        _RmAcceptFullCaseInviteActivity,
        "rm_accept_full_case_invite_activity",
        invite,
        ledger_tail,
        kwargs,
        at=at,
    )


def rm_tentative_reject_full_case_invite_activity(
    invite: as_Invite,
    ledger_tail: LedgerPosition,
    *,
    at: datetime,
    **kwargs,
) -> as_Reject:
    """Build TentativeReject(full-case Invite) — RI, carrying the position.

    The participant judges the case invalid (CM-11-011, VAM-04-013).

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    return _full_case_reply(
        _RmTentativeRejectFullCaseInviteActivity,
        "rm_tentative_reject_full_case_invite_activity",
        invite,
        ledger_tail,
        kwargs,
        at=at,
    )


def rm_reject_full_case_invite_activity(
    invite: as_Invite,
    ledger_tail: LedgerPosition,
    *,
    at: datetime,
    **kwargs,
) -> as_Reject:
    """Build Reject(full-case Invite) — RC, carrying the replier's position.

    The participant closes the case (CM-11-011, VAM-04-014).

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    return _full_case_reply(
        _RmRejectFullCaseInviteActivity,
        "rm_reject_full_case_invite_activity",
        invite,
        ledger_tail,
        kwargs,
        at=at,
    )
