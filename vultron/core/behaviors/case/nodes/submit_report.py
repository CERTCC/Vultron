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

"""Effect and guard nodes for a received ``Offer(VulnerabilityReport)``.

A receiver keeps the report, the Offer and the offer record whatever it later
decides about the Offer, so a receiver that opts out of case creation can
still ACK or decide on the report (CM-15-001, CM-15-002).  Intake archives
the activity only (CLP-10-017); these nodes write the core records from the
event's copy.  :func:`submit_report_received_effects` builds them in the
order the tree runs them, ahead of the ``auto_create_case`` gate.

The records are deliberately written *before* the addressing guard: a
misaddressed Offer is refused (HP-01-005), but the receiver still holds what
it was sent (CLP-10-018).
"""

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.case.nodes.store_received_object import (
    StoreReceivedObjectNode,
)
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    DataLayerConditionWithPorts,
)
from vultron.core.models.events.report import SubmitReportReceivedEvent
from vultron.core.models.offer_record import VultronOfferRecord
from vultron.core.predicates.addressing import is_addressed_to
from vultron.errors import VultronAlreadyExistsError


class StoreSubmitReportOfferRecordNode(DataLayerActionWithPorts):
    """Keep the domain facts of the inbound Offer as a ``VultronOfferRecord``.

    Per ADR-0035 DL-06-002 the receiver's trigger-side validate, invalidate
    and close paths look the offer up here instead of re-reading the stored
    wire Offer.  Idempotent: an existing record is left as it is.
    """

    def __init__(
        self,
        offer_id: str,
        report_id: str,
        offer_actor_id: str,
        offer_to: list[str],
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._offer_id = offer_id
        self._report_id = report_id
        self._offer_actor_id = offer_actor_id
        self._offer_to = offer_to

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        record = VultronOfferRecord(
            offer_id=self._offer_id,
            report_id=self._report_id,
            offer_actor_id=self._offer_actor_id,
            offer_to=self._offer_to,
        )
        try:
            self.datalayer.create(record)
        except VultronAlreadyExistsError:
            self.logger.debug(
                "VultronOfferRecord for offer '%s' already exists",
                self._offer_id,
            )
            return Status.SUCCESS
        self.logger.info(
            "Stored VultronOfferRecord for offer '%s'", self._offer_id
        )
        return Status.SUCCESS


class CheckOfferAddressedToReceiverNode(DataLayerConditionWithPorts):
    """Only a ``to`` recipient acts on an ``Offer(Report)`` (HP-09-001/002).

    ``FAILURE`` with the reason as feedback when the executing actor is only
    in ``cc`` or in neither list: the sender addressed the wrong party, which
    the receiver refuses (HP-01-005) rather than reporting a processed no-op.
    :attr:`misaddressed` tells the handler that was the reason, as opposed to a
    wiring fault (a missing DataLayer or actor), which it raises on.
    """

    def __init__(
        self,
        to: list[str],
        cc: list[str],
        report_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._to = to
        self._cc = cc
        self._report_id = report_id
        self.misaddressed = False

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.actor_id is not None
        self.misaddressed = False
        if is_addressed_to(self.actor_id, self._to):
            return Status.SUCCESS
        self.misaddressed = True
        if is_addressed_to(self.actor_id, self._cc):
            self.logger.warning(
                "cc addressing not supported for Offer(Report) — discarding"
                " activity for report '%s'",
                self._report_id,
            )
            self.feedback_message = (
                "receiving actor is only in cc; cc addressing not supported"
            )
            return Status.FAILURE
        self.logger.warning(
            "receiving actor '%s' in neither to nor cc — discarding activity"
            " for report '%s'",
            self.actor_id,
            self._report_id,
        )
        self.feedback_message = (
            "receiving actor is not a recipient of the Offer"
        )
        return Status.FAILURE


def submit_report_received_effects(
    request: SubmitReportReceivedEvent,
) -> list[py_trees.behaviour.Behaviour]:
    """The effect nodes that keep what a received ``Offer(Report)`` carried.

    Store the report and the Offer activity; for an Offer that names a report,
    also write the offer record and check that the receiver is a ``to``
    recipient.  An Offer that names no report is kept and goes no further.
    """
    report_id = request.report_id
    nodes: list[py_trees.behaviour.Behaviour] = []
    if request.report is not None:
        nodes.append(
            StoreReceivedObjectNode(
                request.report.type_,
                report_id,
                request.report,
                "VulnerabilityReport",
                request.activity_id,
                name="StoreReceivedReport",
            )
        )
    activity = request.activity
    if activity is not None:
        nodes.append(
            StoreReceivedObjectNode(
                activity.type_,
                request.activity_id,
                activity,
                "SubmitReport activity",
                request.activity_id,
                name="StoreReceivedOffer",
            )
        )
    if not report_id:
        return nodes
    if activity is not None:
        nodes.append(
            StoreSubmitReportOfferRecordNode(
                offer_id=request.activity_id,
                report_id=report_id,
                offer_actor_id=request.actor_id,
                offer_to=list(activity.to or []),
            )
        )
    nodes.append(
        CheckOfferAddressedToReceiverNode(
            to=list(activity.to or []) if activity else [],
            cc=list(activity.cc or []) if activity else [],
            report_id=report_id,
        )
    )
    return nodes


__all__ = [
    "CheckOfferAddressedToReceiverNode",
    "StoreSubmitReportOfferRecordNode",
    "submit_report_received_effects",
]
