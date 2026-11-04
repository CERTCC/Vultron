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


"""Trigger activity methods for case ownership transfer."""

from collections.abc import Callable
from datetime import datetime
from typing import Any, cast

from vultron.adapters.received_archive import (
    read_held_as_received,
    read_received_as_received,
)
from vultron.core.models._helpers import _as_id
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.wire.as2.factories.case import (
    accept_case_ownership_transfer_activity,
    offer_case_ownership_transfer_activity,
    propose_case_ownership_transfer_activity,
    reject_case_ownership_transfer_activity,
    undo_case_ownership_transfer_activity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Offer,
    as_Reject,
)

from .._base import (
    _addressing,
    _already_sealed,
    _create_and_seal,
)
from ._helpers import (
    _held_actor,
)


class _OwnershipMixin:
    """Trigger activity methods for case ownership transfer."""

    _dl: CaseOutboxPersistence

    def propose_case_ownership_transfer(
        self,
        case_id: str,
        transferee_id: str,
        actor: str,
        content: str | None = None,
        to: list[str] | None = None,
        end_time: datetime | None = None,
    ) -> tuple[str, str]:
        """Create and persist the owner's ``Offer(Offer(VulnerabilityCase))``.

        The proposal goes from ``actor`` to the CASE_MANAGER (*to*), which
        makes the inner Offer itself (ADR-0148, TRIG-11-001).  The inner
        Offer names the case by typed reference (ADR-0165), so its shape is
        the Offer the CASE_MANAGER will make, the transferee as its
        ``target`` and, when given, *end_time* as its deadline (CM-21-016).
        """
        extra: dict[str, Any] = {"actor": actor, "to": to}
        if content is not None:
            extra["content"] = content
        activity = propose_case_ownership_transfer_activity(
            case_id,
            target=_held_actor(self._dl, transferee_id),
            end_time=end_time,
            **extra,
        )
        return _create_and_seal(
            self._dl, activity, "propose_case_ownership_transfer"
        )

    def offer_case_ownership_transfer(
        self,
        case_id: str,
        transferee_id: str,
        actor: str,
        content: str | None = None,
        to: list[str] | None = None,
        attributed_to: str | None = None,
        end_time: datetime | None = None,
        id_: str | None = None,
    ) -> tuple[str, str]:
        """Create and persist an ``Offer(VulnerabilityCase)`` ownership transfer.

        The CASE_MANAGER's Offer to ``transferee_id``, made from the owner's
        proposal (ADR-0148, CM-21-028).  The case travels as its typed
        reference (ADR-0165): the transferee is an active participant that
        holds it (CM-21-021), and the reference's ``type`` tells this from a
        ``SUBMIT_REPORT`` offer.  *end_time*, when given, is the Offer's
        deadline to answer (CM-21-016).  An Offer already built under *id_*
        is the earlier attempt's, and its sealed body is handed back
        (ID-04-004, OX-06-002).
        """
        if (built := _already_sealed(self._dl, id_)) is not None:
            return built
        extra: dict[str, Any] = _addressing(actor, to or [transferee_id], id_)
        if content is not None:
            extra["content"] = content
        if attributed_to is not None:
            extra["attributed_to"] = attributed_to
        if end_time is not None:
            extra["end_time"] = end_time
        # The CASE_MANAGER ledgers the Offer it makes, and a ledger snapshot
        # names its case as ``context`` (CLP-07).
        activity = offer_case_ownership_transfer_activity(
            case=case_id,
            target=_held_actor(self._dl, transferee_id),
            context=case_id,
            **extra,
        )
        return _create_and_seal(
            self._dl, activity, "offer_case_ownership_transfer"
        )

    def accept_case_ownership_transfer(
        self,
        offer_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, str]:
        """Create and persist an ``Accept(Offer(VulnerabilityCase))`` ownership transfer.

        See :meth:`_ownership_answer` (TRIG-11-002).
        """
        return self._ownership_answer(
            accept_case_ownership_transfer_activity,
            "accept_case_ownership_transfer",
            offer_id=offer_id,
            actor=actor,
            to=to,
        )

    def reject_case_ownership_transfer(
        self,
        offer_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, str]:
        """Create and persist a ``Reject(Offer(VulnerabilityCase))`` ownership transfer.

        See :meth:`_ownership_answer` (TRIG-11-005).
        """
        return self._ownership_answer(
            reject_case_ownership_transfer_activity,
            "reject_case_ownership_transfer",
            offer_id=offer_id,
            actor=actor,
            to=to,
        )

    def withdraw_case_ownership_transfer(
        self,
        offer_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, str]:
        """Create and persist the owner's ``Undo`` of its own proposal.

        *offer_id* names the ``Offer(Offer(VulnerabilityCase))`` this actor
        sent, held under its own id (TRIG-11-006, CM-21-015, ADR-0148).  The
        Undo goes to *to*, the CASE_MANAGER; there is no fallback, since the
        proposal's ``actor`` is this actor itself.
        """
        proposal = read_held_as_received(
            self._dl, offer_id, "Offer(Offer(VulnerabilityCase))"
        )
        activity = undo_case_ownership_transfer_activity(
            proposal=cast(as_Offer, proposal), actor=actor, to=to
        )
        return _create_and_seal(
            self._dl, activity, "withdraw_case_ownership_transfer"
        )

    def _ownership_answer(
        self,
        factory: Callable[..., as_Accept | as_Reject],
        label: str,
        offer_id: str,
        actor: str,
        to: list[str] | None,
    ) -> tuple[str, str]:
        """Build, persist and seal a reply to an ownership-transfer Offer.

        The reply is the transferee's answer (Accept or Reject).  Reads the
        offer as this actor received it (:func:`read_received_as_received`):
        the CASE_MANAGER's Offer parsed from the body the transferee's intake
        archived, never a record under the id its sender chose (DL-06-006,
        ADR-0148), so the reply embeds it verbatim (DL-06-004).  Derives
        the ``to:`` field from the offer's ``actor`` when not supplied, and
        persists the reply that *factory* builds from it.
        """
        raw = read_received_as_received(
            self._dl, offer_id, "Offer(VulnerabilityCase)"
        )
        offer = cast(as_Offer, raw)
        if to is None:
            # Last resort, used only when the emit node found no local case
            # or CASE_MANAGER to address.  The Offer's actor is the
            # CASE_MANAGER that made it (CM-21-006, CM-21-010).
            offer_actor_id = _as_id(getattr(offer, "actor", None))
            if offer_actor_id:
                to = [offer_actor_id]
        activity = factory(offer=offer, actor=actor, to=to)
        return _create_and_seal(self._dl, activity, label)
