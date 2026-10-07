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
"""Unit tests for InvalidateReportReceivedUseCase and CloseReportReceivedUseCase:
which store the tree runs in, and whose RM state it writes.

Two rules, deliberately kept apart (``notes/bt-pitfalls.md`` § "The Store Is
Not the Subject"):

- **The store** — BT-17-006: ``execute_with_setup`` MUST be called with the
  *receiving* actor, so the tree reads and writes the receiver's own replica.
  When ``receiving_actor_id`` is absent, the answer is the actor whose store the
  use case was handed — see ``resolve_receiving_actor_id``.  It is *not*
  ``request.actor_id``: falling back to the sender would route every read and
  write into an actor other than the one whose replica is being updated
  (ADR-0073).  The fallback tests therefore parametrize over which actor owns
  the store, so the store is demonstrably where the write lands.
- **The subject** — RSH-08-001, HP-00-001: a received activity is an assertion
  about the *sender's* state, so the RM write is about ``request.actor_id``.
  ``TentativeReject(Offer(Report))`` moves the sender's participant to
  ``INVALID`` and ``Reject(Offer(Report))`` moves it to ``CLOSED``; the
  receiving actor's own participant is unchanged.

These tests once read "the tree runs as the receiver" as "the write is about the
receiver" and pinned the receiver's RM moving (CONCERN-3473, #3812); they now
pin the sender's, and still pin the store.

The trees for these use cases do NOT contain ``GuardedCommitCaseLedgerEntryBT``
(unlike the AckReport and CloseCase trees), so the routing assertion is on RM
state rather than ledger entry presence.
"""

from __future__ import annotations

from typing import cast

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.models.activity import VultronActivity
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.dimensions import RmDimension
from vultron.core.models.events import MessageSemantics
from vultron.core.models.events.report import (
    CloseReportReceivedEvent,
    InvalidateReportReceivedEvent,
)
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.report import VulnerabilityReport
from vultron.core.models.use_case_result import HandlerDisposition
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


def _spy_executing_actor(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record the ``actor_id`` every BT run executes as (BT-17-006)."""
    executed_as: list[str] = []
    original = BTBridge.execute_with_setup

    def _spy(self, tree, actor_id, *args, **kwargs):
        executed_as.append(actor_id)
        return original(self, tree, actor_id, *args, **kwargs)

    monkeypatch.setattr(BTBridge, "execute_with_setup", _spy)
    return executed_as


def _make_dl(
    receiving_rm: RM = RM.RECEIVED,
    sender_rm: RM = RM.RECEIVED,
    actor_id: str = RECEIVING_ACTOR_ID,
) -> SqliteDataLayer:
    """*actor_id*'s store, holding a case linked to a report and two participants.

    Both RECEIVING_ACTOR_ID and SENDER_ACTOR_ID have participants in the case
    so tests can verify which participant's RM state is transitioned.  Both
    live in one store because they are two participants in *one* actor's
    replica of the case, not two actors' worth of state.

    *actor_id* defaults to the receiving actor, which is who a received-side
    use case executes as (ADR-0073): the store a use case is handed is the
    store the BT reads and writes.  The fallback tests override it to show that
    this fact — and not the sender on the request — is what decides.
    """
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=actor_id)

    report = as_VulnerabilityReport(id_=REPORT_ID, name="Routing Guard Report")
    dl.save(report)

    receiving_participant = CaseParticipant(
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
    sender_participant = CaseParticipant(
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
    participant = cast(CaseParticipant, dl.read(participant_id))
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
        object_=VulnerabilityReport(id_=REPORT_ID),
        inner_object=VulnerabilityReport(id_=REPORT_ID),
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
        object_=VulnerabilityReport(id_=REPORT_ID),
        inner_object=VulnerabilityReport(id_=REPORT_ID),
        activity=activity,
        receiving_actor_id=receiving_actor_id,
    )


# ---------------------------------------------------------------------------
# Tests — InvalidateReportReceivedUseCase
# ---------------------------------------------------------------------------


class TestInvalidateReportReceivedSubject:
    """The tree runs as the receiver (BT-17-006); the write is the sender's.

    ``TentativeReject(Offer(Report))`` declares the *sender's* RM state
    (RSH-08-001), so the sender's participant reaches INVALID and the
    receiving actor's participant is unchanged.
    """

    @pytest.mark.spec("RSH-08-001")
    def test_sender_participant_transitions_to_invalid(self):
        """RM.INVALID is recorded for the sender, the activity's subject."""
        dl = _make_dl(receiving_rm=RM.RECEIVED, sender_rm=RM.RECEIVED)

        InvalidateReportReceivedUseCase(
            dl=dl,
            request=_make_invalidate_event(
                receiving_actor_id=RECEIVING_ACTOR_ID
            ),
        ).execute()

        assert _rm_state(dl, SENDER_ACTOR_ID) == RM.INVALID, (
            "the sender's participant must reach RM.INVALID: the activity"
            " declares the sender's state (RSH-08-001)"
        )

    @pytest.mark.spec("RSH-08-001")
    @pytest.mark.spec("BT-17-006")
    def test_receiving_actor_participant_unchanged(self):
        """The receiving actor's own RM does not move on receipt."""
        dl = _make_dl(receiving_rm=RM.RECEIVED, sender_rm=RM.RECEIVED)

        InvalidateReportReceivedUseCase(
            dl=dl,
            request=_make_invalidate_event(
                receiving_actor_id=RECEIVING_ACTOR_ID
            ),
        ).execute()

        assert _rm_state(dl, RECEIVING_ACTOR_ID) == RM.RECEIVED, (
            "the receiving actor is not the mover, so its participant must"
            " stay RM.RECEIVED (RSH-08-001)"
        )

    @pytest.mark.spec("BT-17-006")
    @pytest.mark.parametrize(
        "store_owner_id", [RECEIVING_ACTOR_ID, SENDER_ACTOR_ID]
    )
    def test_fallback_runs_in_the_store_owners_replica(
        self, store_owner_id, monkeypatch
    ):
        """With no receiving_actor_id, the tree runs in the store it was handed.

        Parametrized over both actors so the assertion cannot pass by
        coincidence: whichever actor owns the store, the write lands in *that*
        store's replica, and it is always about the sender.
        """
        dl = _make_dl(
            receiving_rm=RM.RECEIVED,
            sender_rm=RM.RECEIVED,
            actor_id=store_owner_id,
        )

        executed_as = _spy_executing_actor(monkeypatch)

        result = InvalidateReportReceivedUseCase(
            dl=dl,
            request=_make_invalidate_event(receiving_actor_id=None),
        ).execute()

        assert result.disposition == HandlerDisposition.APPLIED, result.reason
        assert executed_as == [store_owner_id], (
            "absent receiving_actor_id, the tree executes as the store's"
            " owner, never as the sender (BT-17-006)"
        )
        assert _rm_state(dl, SENDER_ACTOR_ID) == RM.INVALID, (
            "the store the use case was handed holds the write, whoever owns"
            " it, and the write is the sender's"
        )
        assert _rm_state(dl, RECEIVING_ACTOR_ID) == RM.RECEIVED


# ---------------------------------------------------------------------------
# Tests — CloseReportReceivedUseCase
# ---------------------------------------------------------------------------


class TestCloseReportReceivedSubject:
    """The tree runs as the receiver (BT-17-006); the write is the sender's.

    ``Reject(Offer(Report))`` declares the *sender's* RM state (RSH-08-001), so
    the sender's participant reaches CLOSED and the receiving actor's
    participant is unchanged.
    """

    @pytest.mark.spec("RSH-08-001")
    def test_sender_participant_transitions_to_closed(self):
        """RM.CLOSED is recorded for the sender, the activity's subject."""
        dl = _make_dl(receiving_rm=RM.RECEIVED, sender_rm=RM.INVALID)

        CloseReportReceivedUseCase(
            dl=dl,
            request=_make_close_report_event(
                receiving_actor_id=RECEIVING_ACTOR_ID
            ),
        ).execute()

        assert _rm_state(dl, SENDER_ACTOR_ID) == RM.CLOSED, (
            "the sender's participant must reach RM.CLOSED: the activity"
            " declares the sender's state (RSH-08-001)"
        )

    @pytest.mark.spec("RSH-08-001")
    @pytest.mark.spec("BT-17-006")
    def test_receiving_actor_participant_unchanged(self):
        """The receiving actor's own RM does not move on receipt."""
        dl = _make_dl(receiving_rm=RM.INVALID, sender_rm=RM.INVALID)

        CloseReportReceivedUseCase(
            dl=dl,
            request=_make_close_report_event(
                receiving_actor_id=RECEIVING_ACTOR_ID
            ),
        ).execute()

        assert _rm_state(dl, RECEIVING_ACTOR_ID) == RM.INVALID, (
            "the receiving actor is not the mover, so its participant must"
            " stay RM.INVALID (RSH-08-001)"
        )

    @pytest.mark.spec("BT-17-006")
    @pytest.mark.parametrize(
        "store_owner_id", [RECEIVING_ACTOR_ID, SENDER_ACTOR_ID]
    )
    def test_fallback_runs_in_the_store_owners_replica(
        self, store_owner_id, monkeypatch
    ):
        """With no receiving_actor_id, the tree runs in the store it was handed.

        Parametrized over both actors so the assertion cannot pass by
        coincidence: whichever actor owns the store, the write lands in *that*
        store's replica, and it is always about the sender.
        """
        dl = _make_dl(
            receiving_rm=RM.INVALID,
            sender_rm=RM.INVALID,
            actor_id=store_owner_id,
        )

        executed_as = _spy_executing_actor(monkeypatch)

        result = CloseReportReceivedUseCase(
            dl=dl,
            request=_make_close_report_event(receiving_actor_id=None),
        ).execute()

        assert result.disposition == HandlerDisposition.APPLIED, result.reason
        assert executed_as == [store_owner_id], (
            "absent receiving_actor_id, the tree executes as the store's"
            " owner, never as the sender (BT-17-006)"
        )
        assert _rm_state(dl, SENDER_ACTOR_ID) == RM.CLOSED
        assert _rm_state(dl, RECEIVING_ACTOR_ID) == RM.INVALID


# ---------------------------------------------------------------------------
# Tests — handler disposition (#2255)
# ---------------------------------------------------------------------------


class TestCloseInvalidateDisposition:
    """Close/Invalidate report the outcome, not a blanket APPLIED (#2255)."""

    @pytest.mark.spec("HP-01-003")
    def test_invalidate_is_applied(self):
        result = InvalidateReportReceivedUseCase(
            dl=_make_dl(), request=_make_invalidate_event()
        ).execute()
        assert result.disposition == HandlerDisposition.APPLIED

    @pytest.mark.spec("HP-01-003")
    def test_close_is_applied(self):
        result = CloseReportReceivedUseCase(
            dl=_make_dl(sender_rm=RM.INVALID),
            request=_make_close_report_event(),
        ).execute()
        assert result.disposition == HandlerDisposition.APPLIED

    @pytest.mark.spec("HP-01-003")
    @pytest.mark.spec("RMB-14-004")
    @pytest.mark.spec("RSH-08-001")
    def test_close_from_received_is_applied(self):
        """RECEIVED → CLOSED is an RM transition (ADR-0114), so it applies."""
        dl = _make_dl()
        result = CloseReportReceivedUseCase(
            dl=dl, request=_make_close_report_event()
        ).execute()
        assert result.disposition == HandlerDisposition.APPLIED, result.reason
        assert _rm_state(dl, SENDER_ACTOR_ID) == RM.CLOSED

    @pytest.mark.spec("HP-01-003")
    @pytest.mark.spec("RSH-06-001")
    @pytest.mark.spec("RSH-06-006")
    def test_close_from_valid_is_a_recorded_gap(self):
        """VALID → CLOSED is a non-adjacent forward move, so it is recorded.

        VALID has no close edge (VP-02-004), which binds an actor moving its
        own RM; a *declared* forward jump is accepted under the received-side
        rule, never refused for adjacency (RSH-06-006).
        """
        dl = _make_dl(sender_rm=RM.VALID)
        result = CloseReportReceivedUseCase(
            dl=dl, request=_make_close_report_event()
        ).execute()
        assert result.disposition == HandlerDisposition.APPLIED, result.reason
        assert _rm_state(dl, SENDER_ACTOR_ID) == RM.CLOSED

    @pytest.mark.spec("HP-01-003")
    @pytest.mark.spec("RSH-06-002")
    def test_invalidate_from_accepted_is_refused(self):
        """ACCEPTED → INVALID is a regression: refused, recorded state kept."""
        dl = _make_dl(sender_rm=RM.ACCEPTED)
        result = InvalidateReportReceivedUseCase(
            dl=dl, request=_make_invalidate_event()
        ).execute()
        assert result.disposition == HandlerDisposition.REFUSED
        assert result.reason and "RSH-06-002" in result.reason
        assert _rm_state(dl, SENDER_ACTOR_ID) == RM.ACCEPTED

    @pytest.mark.spec("HP-01-006")
    def test_invalidate_from_a_non_participant_is_refused(self):
        """A sender with no participant record in the case is turned away."""
        dl = _make_dl()
        stranger = "https://example.org/actors/stranger-report-guard"
        event = _make_invalidate_event().model_copy(
            update={"actor_id": stranger}
        )
        result = InvalidateReportReceivedUseCase(
            dl=dl, request=event
        ).execute()
        assert result.disposition == HandlerDisposition.REFUSED
        assert _rm_state(dl, SENDER_ACTOR_ID) == RM.RECEIVED
        assert _rm_state(dl, RECEIVING_ACTOR_ID) == RM.RECEIVED

    @pytest.mark.spec("HP-01-003")
    def test_invalidate_without_local_case_is_refused(self):
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=RECEIVING_ACTOR_ID)
        result = InvalidateReportReceivedUseCase(
            dl=dl, request=_make_invalidate_event()
        ).execute()
        assert result.disposition == HandlerDisposition.REFUSED
        assert result.reason and "InvalidateReportReceivedBT" in result.reason

    @pytest.mark.spec("HP-01-003")
    def test_close_without_local_case_is_refused(self):
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=RECEIVING_ACTOR_ID)
        result = CloseReportReceivedUseCase(
            dl=dl, request=_make_close_report_event()
        ).execute()
        assert result.disposition == HandlerDisposition.REFUSED
