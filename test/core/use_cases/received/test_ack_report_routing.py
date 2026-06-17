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
"""Unit tests for AckReportReceivedUseCase CaseActor ledger routing.

Pins the pre-flight guard (CLP-10-003): only the CaseActor writes a
``ack_report`` ledger entry; other actors skip it silently.
"""

from __future__ import annotations

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.models.activity import VultronActivity
from vultron.core.models.case_actor import VultronCaseActor
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.events.report import AckReportReceivedEvent
from vultron.core.models.report import VultronReport
from vultron.core.states.roles import CVDRole
from vultron.core.use_cases.received.report import AckReportReceivedUseCase
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Offer
from vultron.wire.as2.vocab.objects.case_participant import CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    VulnerabilityReport,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CASE_ACTOR_ID = "https://example.org/actors/case-actor-ack"
VENDOR_ID = "https://example.org/actors/vendor-ack"
FINDER_ID = "https://example.org/actors/finder-ack"
REPORT_ID = "https://example.org/reports/r-ack-test"
OFFER_ID = "https://example.org/activities/offer-ack"
CASE_ID = "https://example.org/cases/c-ack-test"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_blackboard():
    import py_trees

    py_trees.blackboard.Blackboard.storage.clear()
    yield
    py_trees.blackboard.Blackboard.storage.clear()


def _make_dl() -> SqliteDataLayer:
    return SqliteDataLayer("sqlite:///:memory:")


def _make_case_actor_dl() -> SqliteDataLayer:
    """DataLayer as seen by the CaseActor: case + CASE_MANAGER participant."""
    dl = _make_dl()

    ca_svc = VultronCaseActor(id_=CASE_ACTOR_ID, context=CASE_ID)
    dl.save(ca_svc)

    case = VulnerabilityCase(id_=CASE_ID, name="AckReport Routing Test")
    case.vulnerability_reports.append(REPORT_ID)

    cm_participant = CaseParticipant(
        attributed_to=CASE_ACTOR_ID,
        context=CASE_ID,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    dl.create(cm_participant)
    case.case_participants.append(cm_participant.id_)
    case.actor_participant_index[CASE_ACTOR_ID] = cm_participant.id_
    dl.save(case)

    # Persist the offer so the emit node can read it.
    report_obj = VulnerabilityReport(id_=REPORT_ID, name="Test Vuln Report")
    dl.save(report_obj)
    offer = as_Offer(actor=FINDER_ID, object_=report_obj.id_, target=VENDOR_ID)
    offer = as_Offer(id_=OFFER_ID, actor=FINDER_ID, object_=report_obj.id_)
    dl.create(offer)

    return dl


def _make_ack_event(
    receiving_actor_id: str | None = CASE_ACTOR_ID,
) -> AckReportReceivedEvent:
    """Construct an AckReportReceivedEvent (Read(Offer(Report)))."""
    report_obj = VultronReport(id_=REPORT_ID)
    offer_obj = VultronActivity(
        id_=OFFER_ID,
        type_="Offer",
        actor=FINDER_ID,
        object_=report_obj,
        context=CASE_ID,
    )
    read_activity = VultronActivity(
        id_="https://example.org/activities/read-ack",
        type_="Read",
        actor=VENDOR_ID,
        object_=offer_obj,
        context=CASE_ID,
    )
    return AckReportReceivedEvent(
        semantic_type=MessageSemantics.ACK_REPORT,
        activity_id=read_activity.id_,
        actor_id=VENDOR_ID,
        object_=offer_obj,
        inner_object=report_obj,
        activity=read_activity,
        receiving_actor_id=receiving_actor_id,
    )


def _ledger_event_types(dl: SqliteDataLayer) -> list[str]:
    return [
        getattr(e, "event_type", "")
        for e in dl.list_objects("CaseLedgerEntry")
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAckReportLedgerRouting:
    """CaseActor-guarded commit tests for AckReportReceivedUseCase."""

    def test_caseactor_commits_ack_report_ledger_entry(self):
        """Guarded commit fires when receiving_actor_id == case_actor_id.

        Per CLP-10-002: the CaseActor MUST commit a canonical ledger entry
        when it receives an AckReport activity.
        """
        dl = _make_case_actor_dl()
        AckReportReceivedUseCase(
            dl=dl,
            request=_make_ack_event(receiving_actor_id=CASE_ACTOR_ID),
            sync_port=SyncActivityAdapter(dl),
            trigger_activity=TriggerActivityAdapter(dl),
        ).execute()

        event_types = _ledger_event_types(dl)
        assert "ack_report" in event_types, (
            "Expected a CaseLedgerEntry with event_type='ack_report';"
            f" found: {event_types}"
        )

    def test_non_caseactor_does_not_commit_ledger_entry(self):
        """Guarded commit does NOT fire when receiving_actor_id != case_actor_id.

        Per CLP-10-003: non-CaseActor receiving actors must skip the commit.
        """
        dl = _make_case_actor_dl()
        AckReportReceivedUseCase(
            dl=dl,
            request=_make_ack_event(receiving_actor_id=VENDOR_ID),
            sync_port=SyncActivityAdapter(dl),
            trigger_activity=TriggerActivityAdapter(dl),
        ).execute()

        event_types = _ledger_event_types(dl)
        assert "ack_report" not in event_types, (
            "Non-CaseActor receiving actor must NOT write an ack_report"
            f" ledger entry; found: {event_types}"
        )

    def test_no_receiving_actor_id_skips_commit(self):
        """Guarded commit does NOT fire when receiving_actor_id is None."""
        dl = _make_case_actor_dl()
        AckReportReceivedUseCase(
            dl=dl,
            request=_make_ack_event(receiving_actor_id=None),
            sync_port=SyncActivityAdapter(dl),
            trigger_activity=TriggerActivityAdapter(dl),
        ).execute()

        event_types = _ledger_event_types(dl)
        assert "ack_report" not in event_types, (
            "Missing receiving_actor_id must NOT write an ack_report"
            f" ledger entry; found: {event_types}"
        )
