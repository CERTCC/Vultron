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


"""TriggerReportsPort: the reports part of
:class:`~vultron.core.ports.trigger_activity.TriggerActivityPort`.

VulnerabilityReport submission and report-management answers.
"""

from typing import Protocol


class TriggerReportsPort(Protocol):
    """VulnerabilityReport submission and report-management answers."""

    def submit_report(
        self,
        report_id: str,
        actor: str,
        to: str,
        target: str,
        proposed_embargo_id: str | None = None,
    ) -> tuple[str, str]:
        """Create and persist an ``Offer(VulnerabilityReport)`` activity.

        *proposed_embargo_id* names the Reporter's stored ``EmbargoEvent`` for
        this report (EP-04-004); when given, the Offer carries it as
        ``proposedEmbargo``.

        Returns ``(offer_id, offer_dict)``.
        """
        ...

    def close_report(
        self,
        offer_id: str,
        report_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, str]:
        """Create and persist a ``Reject(Offer)`` Report Closed (RC) activity.

        Returns ``(activity_id, activity_dict)``.
        """
        ...

    def invalidate_report(
        self,
        offer_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, str]:
        """Create and persist a ``TentativeReject(Offer)`` activity.

        Returns ``(activity_id, activity_dict)``.
        """
        ...

    def validate_report(
        self,
        offer_id: str,
        report_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, str]:
        """Create and persist an ``Accept(Offer)`` validate-report activity.

        Returns ``(activity_id, activity_dict)``.
        Per ADR-0021 CLP-10-027: routes the activity to the Case Actor.
        """
        ...

    def ack_report(
        self,
        offer_id: str,
        actor: str,
        to: list[str] | None = None,
        content: str | None = None,
    ) -> tuple[str, str]:
        """Create and persist a ``Read(Offer(VulnerabilityReport))`` ack-report
        activity.

        RK is addressed to the reporter, never to the CASE_MANAGER, and is
        never ledgered (RMB-08-005, RMB-08-007).  ``content`` carries the trigger's
        optional ``note`` (TRIG-03-003).
        Returns ``(activity_id, activity_dict)``.
        """
        ...
