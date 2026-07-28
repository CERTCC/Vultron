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
from typing import Any, cast

from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.wire.as2.factories import (
    create_case_activity,
    rm_defer_case_activity,
    rm_engage_case_activity,
)
from vultron.wire.as2.factories.case import (
    announce_vulnerability_case_activity,
    create_case_proposal_activity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Add
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

from ._base import _DUMP_KWARGS, _to_wire

logger = logging.getLogger(__name__)


class _CasesMixin:
    """Trigger activity methods for as_VulnerabilityCase objects."""

    _dl: CaseOutboxPersistence

    def create_case(
        self,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist a ``Create(as_VulnerabilityCase)`` activity."""
        case = _to_wire(self._dl.read(case_id), as_VulnerabilityCase)
        activity = create_case_activity(case=case, actor=actor, to=to)
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "create_case: activity '%s' already exists — skipping",
                activity.id_,
            )
        return activity.id_, activity.model_dump(**_DUMP_KWARGS)

    def engage_case(
        self,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist an ``Accept(as_VulnerabilityCase)`` engage activity."""
        case = _to_wire(self._dl.read(case_id), as_VulnerabilityCase)
        activity = rm_engage_case_activity(case=case, actor=actor, to=to)
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "engage_case: activity '%s' already exists — skipping",
                activity.id_,
            )
        return activity.id_, activity.model_dump(**_DUMP_KWARGS)

    def defer_case(
        self,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist a ``TentativeReject(as_VulnerabilityCase)`` activity."""
        case = _to_wire(self._dl.read(case_id), as_VulnerabilityCase)
        activity = rm_defer_case_activity(case=case, actor=actor, to=to)
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "defer_case: activity '%s' already exists — skipping",
                activity.id_,
            )
        return activity.id_, activity.model_dump(**_DUMP_KWARGS)

    def close_case(
        self,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist a ``Leave(as_VulnerabilityCase)`` close-case activity."""
        from vultron.wire.as2.factories import rm_close_case_activity

        case = _to_wire(self._dl.read(case_id), as_VulnerabilityCase)
        activity = rm_close_case_activity(case=case, actor=actor, to=to)
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "close_case: activity '%s' already exists — skipping",
                activity.id_,
            )
        return activity.id_, activity.model_dump(**_DUMP_KWARGS)

    def add_object_to_case(
        self,
        actor: str,
        object_id: str,
        case_id: str,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist an ``Add(object, Case)`` activity."""
        case = _to_wire(self._dl.read(case_id), as_VulnerabilityCase)
        obj = cast(Any, self._dl.read(object_id))
        activity = as_Add(actor=actor, object_=obj, target=case)
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "add_object_to_case: activity '%s' already exists — skipping",
                activity.id_,
            )
        return activity.id_, activity.model_dump(**_DUMP_KWARGS)

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
        """
        case = _to_wire(self._dl.read(case_id), as_VulnerabilityCase)
        activity = announce_vulnerability_case_activity(
            case=case,
            actor=actor,
            context=context_id,
            to=to,
        )
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "announce_vulnerability_case: activity '%s' already exists"
                " — skipping",
                activity.id_,
            )
        return activity.id_

    def create_case_proposal(
        self,
        actor: str,
        report_id: str,
        case_actor_id: str,
        summary: str | None = None,
        to: list[str] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist a ``Create(as_CaseProposal)`` activity.

        Reads the ``as_VulnerabilityReport`` identified by ``report_id``,
        constructs an ``as_CaseProposal``, and persists
        ``Create(as_CaseProposal)`` to the DataLayer.

        Per CP-04-001, CP-04-002.
        """
        from vultron.wire.as2.vocab.objects.case_proposal import (
            as_CaseProposal,
        )

        report_obj = self._dl.read(report_id)
        if report_obj is None:
            raise ValueError(
                f"create_case_proposal: report '{report_id}' not found"
                " in DataLayer"
            )
        report = _to_wire(report_obj, as_VulnerabilityReport)
        proposal = as_CaseProposal(
            attributed_to=actor,
            object_=report,
            target=case_actor_id,
            summary=summary,
        )
        # Persist the proposal so the outbox expansion path can find it
        # when the as_Create activity is read back from the DataLayer.
        try:
            self._dl.create(proposal)
        except ValueError:
            logger.debug(
                "create_case_proposal: proposal '%s' already exists"
                " — skipping",
                proposal.id_,
            )
        recipients = to if to is not None else [case_actor_id]
        activity = create_case_proposal_activity(
            actor_id=actor,
            proposal=proposal,
            to=recipients,
        )
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "create_case_proposal: activity '%s' already exists — skipping",
                activity.id_,
            )
        return activity.id_, activity.model_dump(**_DUMP_KWARGS)
