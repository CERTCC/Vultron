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

"""Case-domain trigger activity construction for TriggerActivityAdapter."""

import logging
from typing import Any

from pydantic import ValidationError

from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.errors import (
    VultronActivityConstructionError,
    VultronAlreadyExistsError,
    VultronNotFoundError,
)
from vultron.wire.as2.factories import (
    create_case_activity,
    rm_defer_case_activity,
    rm_engage_case_activity,
)
from vultron.wire.as2.factories.case import (
    announce_vulnerability_case_activity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Add
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

from ._base import _case_for_wire, _seal, _to_wire, _to_wire_object

logger = logging.getLogger(__name__)


class _CasesMixin:
    """Trigger activity methods for as_VulnerabilityCase objects."""

    _dl: CaseOutboxPersistence

    def create_case(
        self,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, str]:
        """Create and persist a ``Create(as_VulnerabilityCase)`` activity."""
        case = _case_for_wire(self._dl, case_id)
        activity = create_case_activity(case=case, actor=actor, to=to)
        try:
            self._dl.create(activity)
        except VultronAlreadyExistsError:
            logger.warning(
                "create_case: activity '%s' already exists — skipping",
                activity.id_,
            )
        return _seal(self._dl, activity)

    def engage_case(
        self,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, str]:
        """Create and persist an ``Accept(as_VulnerabilityCase)`` engage activity."""
        case = _case_for_wire(self._dl, case_id)
        activity = rm_engage_case_activity(case=case, actor=actor, to=to)
        try:
            self._dl.create(activity)
        except VultronAlreadyExistsError:
            logger.warning(
                "engage_case: activity '%s' already exists — skipping",
                activity.id_,
            )
        return _seal(self._dl, activity)

    def defer_case(
        self,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, str]:
        """Create and persist a ``TentativeReject(as_VulnerabilityCase)`` activity."""
        case = _case_for_wire(self._dl, case_id)
        activity = rm_defer_case_activity(case=case, actor=actor, to=to)
        try:
            self._dl.create(activity)
        except VultronAlreadyExistsError:
            logger.warning(
                "defer_case: activity '%s' already exists — skipping",
                activity.id_,
            )
        return _seal(self._dl, activity)

    def close_case(
        self,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, str]:
        """Create and persist a ``Leave(as_VulnerabilityCase)`` close-case activity."""
        from vultron.wire.as2.factories import rm_close_case_activity

        case = _case_for_wire(self._dl, case_id)
        activity = rm_close_case_activity(case=case, actor=actor, to=to)
        try:
            self._dl.create(activity)
        except VultronAlreadyExistsError:
            logger.warning(
                "close_case: activity '%s' already exists — skipping",
                activity.id_,
            )
        return _seal(self._dl, activity)

    def reject_close_case(
        self,
        case_id: str,
        actor: str,
        close_sender: str,
        in_reply_to: str | None = None,
    ) -> tuple[str, str]:
        """Create and persist a ``Reject(Leave(VulnerabilityCase))`` activity.

        Declines an owner's close while an embargo is active (CM-23-011).
        The declined Leave is reconstructed from the case attributed to the
        ``close_sender`` (the Case Owner), then wrapped in an ``as:Reject``
        sent by ``actor`` (the Case Actor) back to the owner.  The inbound
        Leave is not yet persisted when this runs (``StoreActivityNode`` runs
        later in the tree), so the decline is threaded to it via
        ``in_reply_to`` rather than read back from the DataLayer.
        """
        from vultron.wire.as2.factories import (
            reject_close_case_activity,
            rm_close_case_activity,
        )

        case = _case_for_wire(self._dl, case_id)
        leave = rm_close_case_activity(case=case, actor=close_sender)
        kwargs: dict[str, Any] = {"actor": actor, "to": [close_sender]}
        if in_reply_to is not None:
            kwargs["in_reply_to"] = in_reply_to
        activity = reject_close_case_activity(leave=leave, **kwargs)
        try:
            self._dl.create(activity)
        except VultronAlreadyExistsError:
            logger.warning(
                "reject_close_case: activity '%s' already exists — skipping",
                activity.id_,
            )
        return _seal(self._dl, activity)

    def add_object_to_case(
        self,
        actor: str,
        object_id: str,
        case_id: str,
    ) -> tuple[str, str]:
        """Create and persist an ``Add(object, Case)`` activity.

        The object may be of any stored type; :func:`_to_wire_object` resolves
        it to the object the activity carries.

        Raises:
            VultronNotFoundError: when *object_id* is not in the DataLayer.
            VultronActivityConstructionError: when the object has no wire
                representation or the ``Add`` cannot be constructed with it.
        """
        # The case is addressed by its URI: every recipient of an Add to a
        # case already holds the case (AKM-02-002), and the sealed body is
        # delivered as built (VM-08-003), so a full case here would go on the
        # wire whole.  ``context`` names the case for the ledger (CLP-07-007).
        if self._dl.read(case_id) is None:
            raise VultronNotFoundError("VulnerabilityCase", case_id)
        obj = _to_wire_object(self._dl.read(object_id), object_id)
        try:
            activity = as_Add(
                actor=actor, object_=obj, target=case_id, context=case_id
            )
        except ValidationError as exc:
            raise VultronActivityConstructionError(
                f"add_object_to_case: object '{object_id}' of type"
                f" {type(obj).__name__!r} cannot be carried in an Add activity"
            ) from exc
        try:
            self._dl.create(activity)
        except VultronAlreadyExistsError:
            logger.warning(
                "add_object_to_case: activity '%s' already exists — skipping",
                activity.id_,
            )
        return _seal(self._dl, activity)

    def announce_vulnerability_case(
        self,
        case_id: str,
        actor: str,
        context_id: str,
        to: list[str],
    ) -> str:
        """Create and persist an ``Announce(as_VulnerabilityCase)`` activity.

        Reads the full case from the DataLayer, constructs the activity with
        the case inline, and persists it.  Returns the activity ID for outbox
        queueing.

        Per MV-10-003: the case owner sends this after an ``Accept(Invite)``
        is received and the invitee's embargo consent has been verified.

        Per CBT-01-007: all nested domain objects are embedded as full inline
        objects — bare URI string references MUST NOT be used.  Each report
        listed in ``case.vulnerability_reports`` is read from the DataLayer
        and embedded as a full ``as_VulnerabilityReport`` object so that
        receiving handlers (``SeedAnnouncedCaseNode``) can store the objects
        by iterating the embedded collection.
        """
        case = _case_for_wire(self._dl, case_id)
        embedded_reports: list[Any] = []
        for report_ref in case.vulnerability_reports:
            report_id = (
                report_ref
                if isinstance(report_ref, str)
                else getattr(report_ref, "id_", str(report_ref))
            )
            # ``_to_wire`` raises ``VultronNotFoundError`` for a report the
            # store does not hold: an Announce that cannot embed every report
            # it names (CBT-01-007) is not sent at all, since the sealed body
            # would carry a reference the recipient cannot resolve.
            embedded_reports.append(
                _to_wire(self._dl.read(report_id), as_VulnerabilityReport)
            )
        object.__setattr__(case, "vulnerability_reports", embedded_reports)
        activity = announce_vulnerability_case_activity(
            case=case,
            actor=actor,
            context=context_id,
            to=to,
        )
        try:
            self._dl.create(activity)
        except VultronAlreadyExistsError:
            logger.warning(
                "announce_vulnerability_case: activity '%s' already exists"
                " — skipping",
                activity.id_,
            )
        return _seal(self._dl, activity)[0]
