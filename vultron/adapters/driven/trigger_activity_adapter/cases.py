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
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Add
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase

from ._base import _DUMP_KWARGS

logger = logging.getLogger(__name__)


class _CasesMixin:
    """Trigger activity methods for VulnerabilityCase objects."""

    _dl: CaseOutboxPersistence

    def create_case(
        self,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist a ``Create(VulnerabilityCase)`` activity."""
        case = cast(VulnerabilityCase, self._dl.read(case_id))
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
        """Create and persist an ``Accept(VulnerabilityCase)`` engage activity."""
        case = cast(VulnerabilityCase, self._dl.read(case_id))
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
        """Create and persist a ``TentativeReject(VulnerabilityCase)`` activity."""
        case = cast(VulnerabilityCase, self._dl.read(case_id))
        activity = rm_defer_case_activity(case=case, actor=actor, to=to)
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "defer_case: activity '%s' already exists — skipping",
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
        case = cast(Any, self._dl.read(case_id))
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
        """Create and persist an ``Announce(VulnerabilityCase)`` activity.

        Reads the full case from the DataLayer, constructs the activity with
        the case inline, and persists it.  Returns the activity ID for outbox
        queueing.

        Per MV-10-003: the case owner sends this after an ``Accept(Invite)``
        is received and the invitee's embargo consent has been verified.
        """
        case = cast(VulnerabilityCase, self._dl.read(case_id))
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
