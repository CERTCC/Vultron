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

"""Embargo-domain trigger activity construction for TriggerActivityAdapter."""

import logging
from typing import Any, cast

from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.wire.as2.factories import (
    announce_embargo_activity,
    em_accept_embargo_activity,
    em_propose_embargo_activity,
    em_reject_embargo_activity,
    remove_embargo_from_case_activity,
)
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

from ._base import _DUMP_KWARGS

logger = logging.getLogger(__name__)


class _EmbargoMixin:
    """Trigger activity methods for embargo negotiation and lifecycle."""

    _dl: CaseOutboxPersistence

    def propose_embargo(
        self,
        embargo_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist an ``Invite(as_EmbargoEvent, Case)`` proposal."""
        embargo = cast(as_EmbargoEvent, self._dl.read(embargo_id))
        activity = em_propose_embargo_activity(
            embargo=embargo, context=case_id, actor=actor, to=to
        )
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "propose_embargo: activity '%s' already exists — skipping",
                activity.id_,
            )
        return activity.id_, activity.model_dump(**_DUMP_KWARGS)

    def accept_embargo(
        self,
        proposal_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist an ``Accept(Invite)`` embargo-accept activity."""
        proposal = cast(Any, self._dl.read(proposal_id))
        activity = em_accept_embargo_activity(
            proposal=proposal, context=case_id, actor=actor, to=to
        )
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "accept_embargo: activity '%s' already exists — skipping",
                activity.id_,
            )
        return activity.id_, activity.model_dump(**_DUMP_KWARGS)

    def reject_embargo(
        self,
        proposal_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist a ``Reject(Invite)`` embargo-reject activity."""
        proposal = cast(Any, self._dl.read(proposal_id))
        activity = em_reject_embargo_activity(
            proposal=proposal, context=case_id, actor=actor, to=to
        )
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "reject_embargo: activity '%s' already exists — skipping",
                activity.id_,
            )
        return activity.id_, activity.model_dump(**_DUMP_KWARGS)

    def announce_embargo(
        self,
        embargo_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist an ``Announce(as_EmbargoEvent)`` activity."""
        embargo = cast(as_EmbargoEvent, self._dl.read(embargo_id))
        activity = announce_embargo_activity(
            embargo=embargo, context=case_id, actor=actor, to=to
        )
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "announce_embargo: activity '%s' already exists — skipping",
                activity.id_,
            )
        return activity.id_, activity.model_dump(**_DUMP_KWARGS)

    def terminate_embargo(
        self,
        embargo_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist a ``Remove(as_EmbargoEvent, origin=case)`` ET activity."""
        embargo = cast(as_EmbargoEvent, self._dl.read(embargo_id))
        activity = remove_embargo_from_case_activity(
            embargo=embargo, origin=case_id, actor=actor, to=to
        )
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "terminate_embargo: activity '%s' already exists — skipping",
                activity.id_,
            )
        return activity.id_, activity.model_dump(**_DUMP_KWARGS)
