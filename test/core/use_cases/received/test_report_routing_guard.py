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
"""Unit tests for InvalidateReportReceivedUseCase and CloseReportReceivedUseCase
BT execution under the receiving actor's identity (BT-17-006).

Pins the BT-17-006 requirement: ``execute_with_setup`` MUST be called with
``actor_id=request.receiving_actor_id`` so the RM-transition BT updates the
RECEIVING actor's participant, not the sender's.  Before the fix both use cases
passed ``request.actor_id`` (the sender) instead.

The trees for these use cases do NOT contain ``GuardedCommitCaseLedgerEntryBT``
(unlike the AckReport and CloseCase trees), so the routing assertion is on RM
state rather than ledger entry presence.
"""

from __future__ import annotations

from typing import cast

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.activity import VultronActivity
from vultron.core.models.dimensions import RmDimension
from vultron.core.models.events import MessageSemantics
from vultron.core.models.events.report import (
    CloseReportReceivedEvent,
    InvalidateReportReceivedEvent,
)
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.participant import VultronParticipant
from vultron.core.models.report import VultronReport
from vultron.core.states.rm import RM
from vultron.core.use_cases.received.report import (
    CloseReportReceivedUseCase,
    InvalidateReportReceivedUseCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RECEIVING_ACTOR_ID = "https://example.org/actors/receiving-report-guard"
SENDER_ACTOR_ID = "https://example.org/actors/sender-report-guard"
REPORT_ID = "https://example.org/reports/r-routing-guard-test"
CASE_ID = "https://example.org/cases/c-routing-guard-test"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_blackboard():
    import py_trees

    py_trees.blackboard.Blackboard.storage.clear()
    yield
    py_trees.blackboard.Blackboard.storage.clear()


def _make_dl(
    receiving_rm: RM = RM.RECEIVED,
    sender_rm: RM = RM.RECEIVED,
) -> SqliteDataLayer:
    """DataLayer with a case linked to a report and two participants.

    Both RECEIVING_ACTOR_ID and SENDER_ACTOR_ID have participants in the case
    so tests can verify which participant's RM state is transitioned.
    """
    dl = SqliteDataLayer("sqlite:///:memory:")

    report = as_VulnerabilityReport(id_=REPORT_ID, name="Routing Guard Report")
    dl.save(report)

    receiving_participant = VultronParticipant(
        id_="https://example.org/participants/p-receiving-guard",
        attributed_to=RECEIVING_ACTOR_ID,
        context=CASE_ID,
        participant_statuses=[
            ParticipantStatus(
                rm=RmDimension(state=receiving_rm),
                context=CASE_ID,
                attributed_to=RECEIVING_ACTOR_ID,
            )
        ],
    )
    sender_participant = VultronParticipant(
        id_="https://example.org/participants/p-sender-guard",
        attributed_to=SENDER_ACTOR_ID,
        context=CASE_ID,
        participant_statuses=[
            ParticipantStatus(
                rm=RmDimension(state=sender_rm),
                context=CASE_ID,
                attributed_to=SENDER_ACTOR_ID,
            )
        ],
    )

    case = as_VulnerabilityCase(
        id_=CASE_ID,
        name="Report Routing Guard Test Case",
    )
    case.vulnerability_reports.append(REPORT_ID)
    case.case_participants.append(receiving_participant.id_)
    case.case_participants.append(sender_participant.id_)
    case.actor_participant_index[RECEIVING_ACTOR_ID] = (
        receiving_participant.id_
    )
    case.actor_participant_index[SENDER_ACTOR_ID] = sender_participant.id_

    dl.save(receiving_participant)
    dl.save(sender_participant)
    dl.save(case)

    return dl


def _rm_state(dl: SqliteDataLayer, actor_id: str) -> RM | None:
    """Return the current RM state for actor_id's participant in the test case."""
    case = cast(as_VulnerabilityCase, dl.read(CASE_ID))
    participant_id = case.actor_participant_index.get(actor_id)
    if not participant_id:
        return None
    participant = cast(VultronParticipant, dl.read(participant_id))
    if not participant.participant_statuses:
        return None
    return participant.participant_statuses[-1].rm.state


def _make_invalidate_event(
    receiving_actor_id: str | None = RECEIVING_ACTOR_ID,
) -> InvalidateReportReceivedEvent:
    activity = VultronActivity(
        id_="https://example.org/activities/invalidate-guard",
        type_="TentativeReject",
        actor=SENDER_ACTOR_ID,
        object_=REPORT_ID,
    )
    return InvalidateReportReceivedEvent(
        semantic_type=MessageSemantics.INVALIDATE_REPORT,
        activity_id=activity.id_,
        actor_id=SENDER_ACTOR_ID,
        object_=VultronReport(id_=REPORT_ID),
        inner_object=VultronReport(id_=REPORT_ID),
        activity=activity,
        receiving_actor_id=receiving_actor_id,
    )


def _make_close_report_event(
    receiving_actor_id: str | None = RECEIVING_ACTOR_ID,
) -> CloseReportReceivedEvent:
    activity = VultronActivity(
        id_="https://example.org/activities/close-report-guard",
        type_="Reject",
        actor=SENDER_ACTOR_ID,
        object_=REPORT_ID,
    )
    return CloseReportReceivedEvent(
        semantic_type=MessageSemantics.CLOSE_REPORT,
        activity_id=activity.id_,
        actor_id=SENDER_ACTOR_ID,
        object_=VultronReport(id_=REPORT_ID),
        inner_object=VultronReport(id_=REPORT_ID),
        activity=activity,
        receiving_actor_id=receiving_actor_id,
    )


# ---------------------------------------------------------------------------
# Tests — InvalidateReportReceivedUseCase
# ---------------------------------------------------------------------------


class TestInvalidateReportReceivedActorId:
    """BT-17-006: execute_with_setup runs under receiving_actor_id, not actor_id.

    The RM-INVALID transition targets the RECEIVING actor's CaseParticipant.
    Before the fix, actor_id (sender) was passed instead.
    """

    def test_receiving_actor_participant_transitions_to_invalid(self):
        """RM.INVALID transition targets the receiving actor's participant."""
        dl = _make_dl(receiving_rm=RM.RECEIVED, sender_rm=RM.RECEIVED)

        InvalidateReportReceivedUseCase(
            dl=dl,
            request=_make_invalidate_event(
                receiving_actor_id=RECEIVING_ACTOR_ID
            ),
        ).execute()

        assert (
            _rm_state(dl, RECEIVING_ACTOR_ID) == RM.INVALID
        ), "Receiving actor's participant must transition to RM.INVALID"

    def test_sender_participant_unchanged_when_receiving_actor_differs(self):
        """Sender's participant RM state is not touched (BT-17-006 regression)."""
        dl = _make_dl(receiving_rm=RM.RECEIVED, sender_rm=RM.RECEIVED)

        InvalidateReportReceivedUseCase(
            dl=dl,
            request=_make_invalidate_event(
                receiving_actor_id=RECEIVING_ACTOR_ID
            ),
        ).execute()

        assert _rm_state(dl, SENDER_ACTOR_ID) == RM.RECEIVED, (
            "Sender's participant must remain RM.RECEIVED; only the receiving"
            " actor's participant should be transitioned (BT-17-006)"
        )

    def test_fallback_to_actor_id_when_receiving_actor_id_is_none(self):
        """Falls back to actor_id (sender) when receiving_actor_id is None."""
        dl = _make_dl(receiving_rm=RM.RECEIVED, sender_rm=RM.RECEIVED)

        InvalidateReportReceivedUseCase(
            dl=dl,
            request=_make_invalidate_event(receiving_actor_id=None),
        ).execute()

        assert _rm_state(dl, SENDER_ACTOR_ID) == RM.INVALID, (
            "Fallback: sender's participant must transition when"
            " receiving_actor_id is None and actor_id is the fallback"
        )


# ---------------------------------------------------------------------------
# Tests — CloseReportReceivedUseCase
# ---------------------------------------------------------------------------


class TestCloseReportReceivedActorId:
    """BT-17-006: execute_with_setup runs under receiving_actor_id, not actor_id.

    The RM-CLOSED transition targets the RECEIVING actor's CaseParticipant.
    Before the fix, actor_id (sender) was passed instead.
    """

    def test_receiving_actor_participant_transitions_to_closed(self):
        """RM.CLOSED transition targets the receiving actor's participant."""
        # RM.CLOSED is only reachable from RM.INVALID, ACCEPTED, or DEFERRED
        dl = _make_dl(receiving_rm=RM.INVALID, sender_rm=RM.RECEIVED)

        CloseReportReceivedUseCase(
            dl=dl,
            request=_make_close_report_event(
                receiving_actor_id=RECEIVING_ACTOR_ID
            ),
        ).execute()

        assert (
            _rm_state(dl, RECEIVING_ACTOR_ID) == RM.CLOSED
        ), "Receiving actor's participant must transition to RM.CLOSED"

    def test_sender_participant_unchanged_when_receiving_actor_differs(self):
        """Sender's participant RM state is not touched (BT-17-006 regression)."""
        dl = _make_dl(receiving_rm=RM.INVALID, sender_rm=RM.RECEIVED)

        CloseReportReceivedUseCase(
            dl=dl,
            request=_make_close_report_event(
                receiving_actor_id=RECEIVING_ACTOR_ID
            ),
        ).execute()

        assert _rm_state(dl, SENDER_ACTOR_ID) == RM.RECEIVED, (
            "Sender's participant must remain RM.RECEIVED; only the receiving"
            " actor's participant should be transitioned (BT-17-006)"
        )

    def test_fallback_to_actor_id_when_receiving_actor_id_is_none(self):
        """Falls back to actor_id (sender) when receiving_actor_id is None."""
        # Sender needs RM.INVALID so RM.CLOSED transition is valid
        dl = _make_dl(receiving_rm=RM.RECEIVED, sender_rm=RM.INVALID)

        CloseReportReceivedUseCase(
            dl=dl,
            request=_make_close_report_event(receiving_actor_id=None),
        ).execute()

        assert _rm_state(dl, SENDER_ACTOR_ID) == RM.CLOSED, (
            "Fallback: sender's participant must transition when"
            " receiving_actor_id is None and actor_id is the fallback"
        )
