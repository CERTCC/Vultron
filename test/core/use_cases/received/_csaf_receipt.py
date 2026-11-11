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

from test.support.act_clock import clock_at
from test.support.act_runner import run_in_act
from test.support.objects import make
from test.support.received import received_event
from test.wire.csaf._documents import section, vulnerability_report_document
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.adapters.outbox_sealed_body import read_sealed_body_dict
from vultron.core.behaviors.case.case_actor_identity import case_actor_identity
from vultron.core.models.actor import VultronService
from vultron.core.models.attached_document import AttachedDocument
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.events.case_proposal import (
    CreateCaseProposalReceivedEvent,
)
from vultron.core.models.events.report import SubmitReportReceivedEvent
from vultron.core.models.report import (
    ReportAttachment,
    VulnerabilityReport,
)
from vultron.core.models.report_claims import ReportClaimsRecord
from vultron.core.models.use_case_result import HandlerResult
from vultron.core.use_cases.received.case_proposal import (
    CreateCaseProposalReceivedUseCase,
)
from vultron.core.use_cases.received.report import SubmitReportReceivedUseCase
from vultron.wire.as2.factories.report import rm_submit_report_activity
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

VENDOR = "https://vendor.example.org/actors/vendor"
FINDER = "https://finder.example.org/actors/finder"
REPORT_ID = "https://finder.example.org/reports/widget"
CSAF_ID = f"{REPORT_ID}/csaf"
OTHER_ID = f"{REPORT_ID}/notes"
RECEIVED_AT = datetime(2026, 11, 1, 12, tzinfo=UTC)


def document(content: str, document_id: str = CSAF_ID) -> AttachedDocument:
    return make(
        AttachedDocument,
        id_=document_id,
        media_type="application/json",
        content=content,
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
        receiver_id: str = VENDOR,
        report_name: str | None = "Widget overflow",
        report_summary: str | None = None,
        proposed_embargo_end: datetime | None = None,
    ) -> None:
        self.report_id = report_id
        report = make(
            VulnerabilityReport,
            id_=report_id,
            name=report_name,
            summary=report_summary,
            content="The widget overflows its buffer.",
            attachment=list(attachments) or None,
        )
        proposed = (
            make(
                as_EmbargoEvent,
                id_=f"{report_id}/proposed-embargo",
                start_time=RECEIVED_AT,
                end_time=proposed_embargo_end,
                context=report_id,
            )
            if proposed_embargo_end is not None
            else None
        )
        offer = rm_submit_report_activity(
            report, to=receiver_id, actor=FINDER, proposed_embargo=proposed
        )
        event = received_event(offer, receiving_actor_id=receiver_id)
        assert isinstance(event, SubmitReportReceivedEvent)
        self.event = event
        self.dl = SqliteDataLayer("sqlite:///:memory:", actor_id=receiver_id)
        self.dl.save(make(VultronService, id_=receiver_id, name=receiver_name))

    def handle(self, at: datetime = RECEIVED_AT) -> HandlerResult:
        """Handle the Offer inside an act at *at*, as the inbox does
        (ADR-0176)."""
        with clock_at(at):
            return run_in_act(
                SubmitReportReceivedUseCase(
                    self.dl,
                    self.event,
                    trigger_activity=TriggerActivityAdapter(self.dl),
                ),
                at=at,
            )

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

    def proposal_body(self) -> dict[str, Any]:
        """The ``Create(CaseProposal)`` this receipt sent, as sealed."""
        [body] = [
            b
            for b in self.sent_bodies()
            if b["type"] == "Create"
            and isinstance(b.get("object"), dict)
            and b["object"].get("type") == "CaseProposal"
        ]
        return body


def schema_invalid() -> dict[str, JsonValue]:
    data = vulnerability_report_document()
    section(data, "document", "tracking")["status"] = "unknown-status"
    return data


class CaseManager:
    """A separate CASE_MANAGER, in its own store, that a proposal reaches."""

    def __init__(self) -> None:
        case_actor_id = case_actor_identity()
        assert case_actor_id is not None, "the CaseActor URL is configured"
        self.actor_id = case_actor_id
        self.dl = SqliteDataLayer("sqlite:///:memory:", actor_id=case_actor_id)
        self.dl.save(make(VultronService, id_=case_actor_id))

    def receive(
        self, body: dict[str, Any], at: datetime = RECEIVED_AT
    ) -> HandlerResult:
        """Deliver the sealed *body* and handle it, inside an act at *at*."""
        return self.receive_activity(parse_activity(body), at=at)

    def receive_activity(
        self, activity: as_Activity, at: datetime = RECEIVED_AT
    ) -> HandlerResult:
        """Deliver *activity* and handle it, inside an act at *at*."""
        event = received_event(
            activity, at=self.dl, receiving_actor_id=self.actor_id
        )
        assert isinstance(event, CreateCaseProposalReceivedEvent)
        with clock_at(at):
            return run_in_act(
                CreateCaseProposalReceivedUseCase(
                    self.dl,
                    event,
                    sync_port=SyncActivityAdapter(self.dl),
                    trigger_activity=TriggerActivityAdapter(self.dl),
                    wire_render_port=As2WireRenderAdapter(),
                ),
                at=at,
            )

    def cases(self) -> list[VulnerabilityCase]:
        return [
            c
            for c in self.dl.list_objects("VulnerabilityCase")
            if isinstance(c, VulnerabilityCase)
        ]

    def case(self) -> VulnerabilityCase:
        [case] = self.cases()
        return case

    def records(self) -> list[ReportClaimsRecord]:
        return [
            r
            for r in self.dl.list_objects("ReportClaimsRecord")
            if isinstance(r, ReportClaimsRecord)
        ]
