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

"""Report-domain trigger activity construction for TriggerActivityAdapter."""

import logging
from typing import Any, cast

from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.wire.as2.factories import (
    rm_close_report_activity,
    rm_invalidate_report_activity,
    rm_submit_report_activity,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    VulnerabilityReport,
)

from ._base import _DUMP_KWARGS

logger = logging.getLogger(__name__)


class _ReportsMixin:
    """Trigger activity methods for VulnerabilityReport objects."""

    _dl: CaseOutboxPersistence

    def submit_report(
        self,
        report_id: str,
        actor: str,
        to: str,
        target: str,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist an ``Offer(VulnerabilityReport)`` activity."""
        report = cast(VulnerabilityReport, self._dl.read(report_id))
        activity = rm_submit_report_activity(
            report=report, to=to, actor=actor, target=target
        )
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "submit_report: activity '%s' already exists — skipping",
                activity.id_,
            )
        return activity.id_, activity.model_dump(**_DUMP_KWARGS)

    def close_report(
        self,
        offer_id: str,
        report_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist a ``Reject(Offer)`` close-report activity."""
        offer = cast(Any, self._dl.read(offer_id))
        activity = rm_close_report_activity(offer=offer, actor=actor, to=to)
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "close_report: activity '%s' already exists — skipping",
                activity.id_,
            )
        return activity.id_, activity.model_dump(**_DUMP_KWARGS)

    def invalidate_report(
        self,
        offer_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create and persist a ``TentativeReject(Offer)`` activity."""
        offer = cast(Any, self._dl.read(offer_id))
        activity = rm_invalidate_report_activity(
            offer=offer, actor=actor, to=to
        )
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "invalidate_report: activity '%s' already exists — skipping",
                activity.id_,
            )
        return activity.id_, activity.model_dump(**_DUMP_KWARGS)
