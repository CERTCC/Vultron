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


"""Trigger activity methods for case and full-case invitations and their answers."""

import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.ledger_position import LedgerPosition
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.errors import (
    VultronAlreadyExistsError,
    VultronValidationError,
)
from vultron.wire.as2.factories import (
    rm_accept_full_case_invite_activity,
    rm_accept_invite_to_case_activity,
    rm_invite_to_case_activity,
    rm_invite_to_full_case_activity,
    rm_reject_full_case_invite_activity,
    rm_tentative_reject_full_case_invite_activity,
)
from vultron.wire.as2.factories.case import (
    rm_reject_invite_to_case_activity,
)

from .._base import (
    _addressing,
    _create_and_seal,
    _seal,
    _stamped,
)
from ._helpers import (
    _active_embargo_of,
    _held_actor,
    _stored_case_invite,
)

logger = logging.getLogger(__name__)


class _InvitesMixin:
    """Trigger activity methods for case and full-case invitations and their answers."""

    _dl: CaseOutboxPersistence

    def invite_actor_to_case(
        self,
        invitee_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
        id_: str | None = None,
        attributed_to: str | None = None,
        roles: list[str] | None = None,
        target: VulnerabilityCase | None = None,
        rsvp_deadline: datetime | None = None,
        in_reply_to: str | None = None,
        *,
        at: datetime,
    ) -> tuple[str, str]:
        """Create and persist an ``Invite(Actor)[target=VulnerabilityCaseStub]`` activity.

        ``actor`` MUST be the CASE_MANAGER's ID (PCR-08-007); ``attributed_to``
        MAY carry the case owner's ID for attribution.  The Invite carries no
        ``cc`` (CM-17-015, ADR-0109).

        ``roles`` carries the intended CVD roles for the invitee (CM-17-003).
        ``target`` may be a core ``as_VulnerabilityCase`` (projected to an enriched
        stub by the factory), a pre-built ``as_VulnerabilityCaseStub``, or a bare
        URI string.  When ``None``, the case is read from the DataLayer by
        ``case_id`` and passed to the factory with any active embargo entity for
        CM-17-002 enrichment.
        """
        extra = _addressing(actor, to, id_)
        if attributed_to is not None:
            extra["attributed_to"] = attributed_to
        if rsvp_deadline is not None:
            extra["end_time"] = rsvp_deadline
        if in_reply_to is not None:
            extra["in_reply_to"] = in_reply_to

        # Read case and embargo from DataLayer; factory handles projection.
        resolved: Any = target
        if resolved is None:
            resolved = self._dl.read(case_id)
            if not isinstance(resolved, VulnerabilityCase):
                resolved = case_id

        embargo_obj = (
            _active_embargo_of(self._dl, resolved)
            if isinstance(resolved, VulnerabilityCase)
            else None
        )

        activity = rm_invite_to_case_activity(
            invitee=_held_actor(self._dl, invitee_id),
            target=resolved,
            roles=roles,
            embargo_obj=embargo_obj,
            **extra,
            at=at,
        )
        # One transaction: the sender sequence the stamp allocates is used
        # only when the body carrying it is sealed (SYNC-21-003).
        with self._dl.transaction():
            activity = _stamped(self._dl, activity)
            try:
                self._dl.create(activity)
            except VultronAlreadyExistsError:
                # A retry of the emit for the same request rebuilds the
                # Invite under its derived id (OX-06-002): expected, not a
                # fault.
                logger.info(
                    "invite_actor_to_case: activity '%s' already exists"
                    " — skipping",
                    activity.id_,
                )
            return _seal(self._dl, activity)

    def accept_case_invite(
        self,
        invite_id: str,
        actor: str,
        *,
        at: datetime,
    ) -> tuple[str, str]:
        """Create and persist an ``Accept(Invite)`` activity.

        The ``to:`` field is derived from ``invite.actor`` (the original
        sender of the invitation) so that OX-08-001 is satisfied and the
        Accept is routable via the outbox handler.  ``_as_id`` is used to
        extract the URI whether the stored actor field is a plain string or a
        hydrated AS2 object; a ``VultronValidationError`` is raised if the
        invite carries no routable actor reference.
        """
        invite = _stored_case_invite(self._dl, invite_id)
        invite_actor_id = _as_id(getattr(invite, "actor", None))
        if not invite_actor_id:
            raise VultronValidationError(
                f"accept_case_invite: invite '{invite_id}' has no routable"
                " actor field; cannot derive Accept recipient"
            )
        activity = rm_accept_invite_to_case_activity(
            invite=invite, actor=actor, to=[invite_actor_id], at=at
        )
        return _create_and_seal(self._dl, activity, "accept_case_invite")

    def reject_case_invite(
        self,
        invite_id: str,
        actor: str,
        *,
        at: datetime,
    ) -> tuple[str, str]:
        """Create and persist a ``Reject(Invite)`` activity.

        The ``to:`` field is derived from ``invite.actor`` (the original
        sender of the invitation) so that the Reject is routable via the
        outbox handler.  Mirrors ``accept_case_invite`` but uses
        ``rm_reject_invite_to_case_activity``.
        """
        invite = _stored_case_invite(self._dl, invite_id)
        invite_actor_id = _as_id(getattr(invite, "actor", None))
        if not invite_actor_id:
            raise VultronValidationError(
                f"reject_case_invite: invite '{invite_id}' has no routable"
                " actor field; cannot derive Reject recipient"
            )
        activity = rm_reject_invite_to_case_activity(
            invite=invite, actor=actor, to=[invite_actor_id], at=at
        )
        return _create_and_seal(self._dl, activity, "reject_case_invite")

    def invite_actor_to_full_case(
        self,
        invitee_id: str,
        case_id: str,
        actor: str,
        ledger_log_index: int,
        ledger_entry_hash: str,
        to: list[str] | None = None,
        id_: str | None = None,
        *,
        at: datetime,
    ) -> tuple[str, str]:
        """Create and persist the full-case
        ``Invite(Actor)[target=VulnerabilityCase]``.
        """
        extra = _addressing(actor, to, id_)
        activity = rm_invite_to_full_case_activity(
            invitee=_held_actor(self._dl, invitee_id),
            case=case_id,
            ledger_tail=LedgerPosition(
                log_index=ledger_log_index, entry_hash=ledger_entry_hash
            ),
            **extra,
            at=at,
        )
        return _create_and_seal(
            self._dl, activity, "invite_actor_to_full_case"
        )

    def _full_case_reply(
        self,
        builder: Callable[..., Any],
        label: str,
        invite_id: str,
        actor: str,
        position: LedgerPosition,
        *,
        at: datetime,
    ) -> tuple[str, str]:
        """Persist the reply *builder* makes to the stored full-case Invite."""
        invite = _stored_case_invite(self._dl, invite_id)
        invite_actor_id = _as_id(getattr(invite, "actor", None))
        if not invite_actor_id:
            raise VultronValidationError(
                f"{label}: invite '{invite_id}' has no routable actor field;"
                " cannot derive the reply's recipient"
            )
        activity = builder(
            invite=invite,
            ledger_tail=position,
            actor=actor,
            to=[invite_actor_id],
            at=at,
        )
        return _create_and_seal(self._dl, activity, label)

    def accept_full_case_invite(
        self,
        invite_id: str,
        actor: str,
        ledger_log_index: int,
        ledger_entry_hash: str,
        *,
        at: datetime,
    ) -> tuple[str, str]:
        """Create and persist ``Accept(full-case Invite)`` — RV."""
        return self._full_case_reply(
            rm_accept_full_case_invite_activity,
            "accept_full_case_invite",
            invite_id,
            actor,
            LedgerPosition(
                log_index=ledger_log_index, entry_hash=ledger_entry_hash
            ),
            at=at,
        )

    def tentative_reject_full_case_invite(
        self,
        invite_id: str,
        actor: str,
        ledger_log_index: int,
        ledger_entry_hash: str,
        *,
        at: datetime,
    ) -> tuple[str, str]:
        """Create and persist ``TentativeReject(full-case Invite)`` — RI."""
        return self._full_case_reply(
            rm_tentative_reject_full_case_invite_activity,
            "tentative_reject_full_case_invite",
            invite_id,
            actor,
            LedgerPosition(
                log_index=ledger_log_index, entry_hash=ledger_entry_hash
            ),
            at=at,
        )

    def reject_full_case_invite(
        self,
        invite_id: str,
        actor: str,
        ledger_log_index: int,
        ledger_entry_hash: str,
        *,
        at: datetime,
    ) -> tuple[str, str]:
        """Create and persist ``Reject(full-case Invite)`` — RC."""
        return self._full_case_reply(
            rm_reject_full_case_invite_activity,
            "reject_full_case_invite",
            invite_id,
            actor,
            LedgerPosition(
                log_index=ledger_log_index, entry_hash=ledger_entry_hash
            ),
            at=at,
        )
