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
"""A report Offer delivered to the Vendor, for the CSAF receive-path tests.

The Offer is built with the factory, delivered through the parser and
extractor as the inbox delivers it, and handled by
``SubmitReportReceivedUseCase`` in the receiver's own store.
"""

import json
from datetime import UTC, datetime
from typing import Any

from pydantic import JsonValue

from test.support.received import received_event
from test.wire.csaf._documents import section, vulnerability_report_document
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.outbox_sealed_body import read_sealed_body_dict
from vultron.core.behaviors.bridge.act_instant import act_instant_in_tree_run
from vultron.core.models.actor import VultronService
from vultron.core.models.attached_document import AttachedDocument
from vultron.core.models.events.report import SubmitReportReceivedEvent
from vultron.core.models.report import (
    ReportAttachment,
    VulnerabilityReport,
)
from vultron.core.models.report_claims import ReportClaimsRecord
from vultron.core.models.use_case_result import HandlerResult
from vultron.core.use_cases.received.report import SubmitReportReceivedUseCase
from vultron.wire.as2.factories.report import rm_submit_report_activity

VENDOR = "https://vendor.example.org/actors/vendor"
FINDER = "https://finder.example.org/actors/finder"
REPORT_ID = "https://finder.example.org/reports/widget"
CSAF_ID = f"{REPORT_ID}/csaf"
OTHER_ID = f"{REPORT_ID}/notes"
RECEIVED_AT = datetime(2026, 11, 1, 12, tzinfo=UTC)


def document(content: str, document_id: str = CSAF_ID) -> AttachedDocument:
    return AttachedDocument(
        id_=document_id, media_type="application/json", content=content
    )


def csaf(data: dict[str, JsonValue]) -> AttachedDocument:
    return document(json.dumps(data))


class Receipt:
    """One delivery of a report Offer to the Vendor, and what it left behind."""

    def __init__(
        self,
        *attachments: ReportAttachment,
        report_id: str = REPORT_ID,
        receiver_name: str | None = None,
    ) -> None:
        self.report_id = report_id
        report = VulnerabilityReport(
            id_=report_id,
            name="Widget overflow",
            content="The widget overflows its buffer.",
            attachment=list(attachments) or None,
        )
        offer = rm_submit_report_activity(report, to=VENDOR, actor=FINDER)
        event = received_event(offer, receiving_actor_id=VENDOR)
        assert isinstance(event, SubmitReportReceivedEvent)
        self.event = event
        self.dl = SqliteDataLayer("sqlite:///:memory:", actor_id=VENDOR)
        self.dl.save(VultronService(id_=VENDOR, name=receiver_name))

    def handle(self) -> HandlerResult:
        # The inbox runs each delivery inside an act (ADR-0176).
        with act_instant_in_tree_run(RECEIVED_AT):
            return SubmitReportReceivedUseCase(
                self.dl,
                self.event,
                trigger_activity=TriggerActivityAdapter(self.dl),
            ).execute()

    def records(self) -> list[ReportClaimsRecord]:
        found = self.dl.list_objects("ReportClaimsRecord")
        assert all(isinstance(r, ReportClaimsRecord) for r in found)
        return [
            r
            for r in found
            if isinstance(r, ReportClaimsRecord)
            and r.report_id == self.report_id
        ]

    def record(self) -> ReportClaimsRecord:
        [only] = self.records()
        return only

    def stored_report(self) -> VulnerabilityReport:
        report = self.dl.read(self.report_id)
        assert isinstance(report, VulnerabilityReport)
        return report

    def sent_bodies(self) -> list[dict[str, Any]]:
        bodies = [
            read_sealed_body_dict(self.dl, activity_id)
            for activity_id in self.dl.outbox_list()
        ]
        assert all(body is not None for body in bodies)
        return [body for body in bodies if body is not None]


def schema_invalid() -> dict[str, JsonValue]:
    data = vulnerability_report_document()
    section(data, "document", "tracking")["status"] = "unknown-status"
    return data
