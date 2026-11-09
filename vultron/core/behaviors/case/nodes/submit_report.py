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
still ACK or decide on the report (CM-15-001, CM-15-002).  Intake records
the activity only (CLP-10-017), and that record is the Offer the receiver
keeps: nothing stores it under the id its sender chose (DL-06-006).  These
nodes write the core records from the event's copy.
:func:`submit_report_received_effects` builds them in the order the tree
runs them, ahead of the ``auto_create_case`` gate.

They run after the factory's door guards, like every received tree's
effects (CLP-10-010, ADR-0154): a copy not addressed to the receiver,
``cc``-only included, is refused at the addressee door and leaves only a
receipt stub, with no report, no Offer and no offer record (HP-01-005,
HP-10-001, CLP-10-018).

:class:`CheckOfferNamesReceiverInToNode` is not an addressee check.  The door
has already admitted the copy; this node asks the narrower case-creation
question, which reads ``to`` alone (HP-09-001), so a sender's own copy, which
the door admits, keeps what it carried and proposes no case.
"""

import py_trees
from py_trees.common import Status
from py_trees.ports import PortInformation

from vultron.core.behaviors.case.nodes.addressee import (
    named_in_to,
    received_to,
)
from vultron.core.behaviors.case.nodes.store_received_object import (
    StoreReceivedObjectNode,
)
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    DataLayerConditionWithPorts,
)
from vultron.core.models.events.report import SubmitReportReceivedEvent
from vultron.core.models.offer_record import VultronOfferRecord
from vultron.core.models.report_claims import (
    ClaimsReading,
    ReportClaimsRecord,
)
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


class StoreReportClaimsRecordsNode(DataLayerActionWithPorts):
    """Keep what each CSAF document attached to the report claimed.

    Writes one :class:`~vultron.core.models.report_claims.ReportClaimsRecord`
    per reading the wire edge made, apart from the report, which stays as
    received (VM-08-002, CSAF-04-004).  The record is the receiver's own and
    no emitted activity carries it (CSAF-04-005).  Each field the reader
    skipped is logged at INFO with the Offer and its sender (CSAF-04-003).

    A schema-invalid document is recorded like any other: reading a document
    never refuses the Offer, so this node fails only when the DataLayer is
    missing (CSAF-02-006).  Idempotent: a record already held is kept as it
    is, so a resent Offer neither rewrites nor re-logs it.
    """

    def __init__(
        self,
        report_id: str,
        activity_id: str,
        sender_id: str,
        readings: list[ClaimsReading],
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._report_id = report_id
        self._activity_id = activity_id
        self._sender_id = sender_id
        self._readings = list(readings)

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        for reading in self._readings:
            record = ReportClaimsRecord(
                report_id=self._report_id,
                activity_id=self._activity_id,
                reading=reading,
            )
            try:
                self.datalayer.create(record)
            except VultronAlreadyExistsError:
                self.logger.debug(
                    "%s: claims record for document '%s' of report '%s'"
                    " already held",
                    self.name,
                    reading.document_id,
                    self._report_id,
                )
                continue
            self._log_stored(reading)
        return Status.SUCCESS

    def _log_stored(self, reading: ClaimsReading) -> None:
        for skipped in reading.skipped:
            self.logger.info(
                "%s: skipped %s field '%s' of document '%s' in activity '%s'"
                " from actor '%s': %s (CSAF-04-003)",
                self.name,
                reading.document_format,
                skipped.path,
                reading.document_id,
                self._activity_id,
                self._sender_id,
                skipped.reason,
            )
        self.logger.info(
            "%s: stored the %s claims of document '%s' on report '%s' from"
            " activity '%s', actor '%s': %s with %d schema error(s), %d"
            " field(s) skipped",
            self.name,
            reading.document_format,
            reading.document_id,
            self._report_id,
            self._activity_id,
            self._sender_id,
            reading.schema_verdict.value,
            len(reading.schema_errors),
            len(reading.skipped),
        )


class CheckOfferNamesReceiverInToNode(DataLayerConditionWithPorts):
    """Case-creation eligibility: the Offer names the receiver in ``to`` (HP-09-001).

    An ``Offer(VulnerabilityReport)`` makes its receiver eligible to create a
    case from ``to`` alone (HP-09-001), read through the ``to`` half of the
    shared addressee definition,
    :func:`~vultron.core.behaviors.case.nodes.addressee.named_in_to`.  The
    addressee door has already refused every copy not addressed to the
    receiver (HP-01-005), so the one copy that reaches this node and fails it
    is the sender's own: addressed to it, and kept, but proposing no case.

    ``FAILURE`` is that decline, not a refusal: the tree stops before the
    ``auto_create_case`` gate and the handler reports ``SKIPPED``.  A wiring
    fault (a missing DataLayer, actor or received event) also fails, logged
    at ERROR, and :attr:`not_named_in_to` tells the handler which it was, so
    a fault never reads as a decline.

    Reads ``to`` off the received event's activity on the blackboard, the
    same place the addressee door reads it.
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerConditionWithPorts.INPUT_PORTS,
        "activity": PortInformation(data_type=object, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"activity": "/activity"}

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._event: object | None = None
        self.not_named_in_to = False

    def initialise(self) -> None:
        super().initialise()
        self._event = self._try_get_input("activity")

    def update(self) -> Status:
        self.not_named_in_to = False
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None and self.actor_id is not None
        if self._event is None:
            self.feedback_message = (
                "no received event on the blackboard to read the Offer's to"
                " from"
            )
            self.logger.error("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        if named_in_to(
            self.datalayer, self.actor_id, received_to(self._event)
        ):
            return Status.SUCCESS
        self.not_named_in_to = True
        self.feedback_message = (
            f"'{self.actor_id}' is not named in the Offer's to, so it is not"
            " eligible to create a case from it (HP-09-001)"
        )
        self.logger.info(
            "%s: kept the Offer and proposed no case: %s",
            self.name,
            self.feedback_message,
        )
        return Status.FAILURE


def submit_report_received_effects(
    request: SubmitReportReceivedEvent,
) -> list[py_trees.behaviour.Behaviour]:
    """The effect nodes that keep what a received ``Offer(VulnerabilityReport)``
    carried.

    Store the report (intake has recorded the Offer); for an Offer that
    names a report, also write the offer record (CM-15-002), then a claims
    record for each CSAF document the report carries (CSAF-04-004), so a
    failed claims write never holds the offer record back.  The
    factory's door guards have already admitted the Offer (HP-01-005).
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
    # The Offer itself is intake's record, read through its receiver-keyed
    # record; nothing holds it under the id its sender chose (DL-06-006).
    activity = request.activity
    if report_id and activity is not None:
        nodes.append(
            StoreSubmitReportOfferRecordNode(
                offer_id=request.activity_id,
                report_id=report_id,
                offer_actor_id=request.actor_id,
                offer_to=list(activity.to or []),
            )
        )
    if report_id and request.claims_readings:
        nodes.append(
            StoreReportClaimsRecordsNode(
                report_id=report_id,
                activity_id=request.activity_id,
                sender_id=request.actor_id,
                readings=request.claims_readings,
            )
        )
    return nodes


__all__ = [
    "CheckOfferNamesReceiverInToNode",
    "StoreReportClaimsRecordsNode",
    "StoreSubmitReportOfferRecordNode",
    "submit_report_received_effects",
]
