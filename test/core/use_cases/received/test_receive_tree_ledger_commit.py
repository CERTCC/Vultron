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

"""Canonical-signature receive trees commit exactly when they should (CLP-10-013).

``Add(CaseParticipant)``, ``Reject(Offer)`` and ``TentativeReject(Offer)`` are
canonical payload signatures, so the CASE_MANAGER ledgers each one it receives
and every other receiver skips the commit.  A receiver that refuses the
activity commits nothing (CLP-10-009).  ``Announce(VulnerabilityCase)`` is the
documented exemption: its tree has no commit stage.
"""

from typing import cast

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.behaviors.case.announce_case_received_tree import (
    create_announce_vulnerability_case_received_tree,
)
from vultron.core.models.case_actor import CaseActor
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.dimensions import RmDimension
from vultron.core.models.events import MessageSemantics
from vultron.core.models.events.actor import (
    AnnounceVulnerabilityCaseReceivedEvent,
)
from vultron.core.models.events.case_participant import (
    AddCaseParticipantToCaseReceivedEvent,
)
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.rm import RM
from vultron.core.use_cases.received.case_participant import (
    AddCaseParticipantToCaseReceivedUseCase,
)
from vultron.core.use_cases.received.report import (
    CloseReportReceivedUseCase,
    InvalidateReportReceivedUseCase,
)
from vultron.enums.roles import CVDRole
from vultron.semantic_registry import extract_event
from vultron.wire.as2.factories import (
    add_participant_to_case_activity,
    announce_vulnerability_case_activity,
    rm_close_report_activity,
    rm_invalidate_report_activity,
    rm_submit_report_activity,
)
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

MANAGER_ID = "https://example.org/actors/manager-4304"
VENDOR_ID = "https://example.org/actors/vendor-4304"
FINDER_ID = "https://example.org/actors/finder-4304"
CASE_ID = "https://example.org/cases/c-4304"
REPORT_ID = "https://example.org/reports/r-4304"
NEWCOMER_ID = "https://example.org/actors/newcomer-4304"


def _participant(
    actor_id: str, rm: RM, *roles: CVDRole, tag: str
) -> CaseParticipant:
    return CaseParticipant(
        id_=f"{CASE_ID}/participants/{tag}",
        attributed_to=actor_id,
        context=CASE_ID,
        case_roles=list(roles),
        participant_statuses=[
            ParticipantStatus(
                rm=RmDimension(state=rm),
                context=CASE_ID,
                attributed_to=actor_id,
            )
        ],
    )


def _store(
    owner_id: str, rm: RM = RM.RECEIVED, finder_known: bool = True
) -> SqliteDataLayer:
    """*owner_id*'s replica: MANAGER_ID holds CASE_MANAGER, VENDOR_ID is a peer.

    Every owner gets the same case, so a role gate always has a roster to
    resolve the CASE_MANAGER from; only who executes differs.  FINDER_ID, the
    sender of the report verdicts, is a participant at RM *rm* unless
    *finder_known* is false.
    """
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=owner_id)
    dl.save(as_VulnerabilityReport(id_=REPORT_ID, name="r"))
    dl.save(CaseActor(id_=MANAGER_ID, context=CASE_ID))
    case = as_VulnerabilityCase(
        id_=CASE_ID, name="4304", attributed_to=MANAGER_ID
    )
    case.vulnerability_reports.append(REPORT_ID)
    roster = [
        (MANAGER_ID, (CVDRole.CASE_MANAGER,), "manager"),
        (VENDOR_ID, (), "vendor"),
    ]
    if finder_known:
        roster.append((FINDER_ID, (), "finder"))
    for actor_id, roles, tag in roster:
        participant = _participant(actor_id, rm, *roles, tag=tag)
        dl.save(participant)
        case.case_participants.append(participant.id_)
        case.actor_participant_index[actor_id] = participant.id_
    dl.save(case)
    return dl


def _committed(dl: SqliteDataLayer) -> list[str]:
    return [
        getattr(e, "event_type", "")
        for e in dl.list_objects("CaseLedgerEntry")
    ]


def _ports(dl: SqliteDataLayer) -> dict:
    return {
        "sync_port": SyncActivityAdapter(dl),
        "wire_render_port": As2WireRenderAdapter(),
    }


def _offer():
    return rm_submit_report_activity(
        as_VulnerabilityReport(id_=REPORT_ID, name="r"),
        to=VENDOR_ID,
        actor=FINDER_ID,
    )


@pytest.mark.spec("CLP-10-013")
class TestCloseAndInvalidateReportCommit:
    @pytest.mark.parametrize(
        ("use_case", "build", "semantic"),
        [
            (
                CloseReportReceivedUseCase,
                rm_close_report_activity,
                MessageSemantics.CLOSE_REPORT,
            ),
            (
                InvalidateReportReceivedUseCase,
                rm_invalidate_report_activity,
                MessageSemantics.INVALIDATE_REPORT,
            ),
        ],
        ids=["close", "invalidate"],
    )
    @pytest.mark.parametrize(
        ("receiver", "commits"),
        [(MANAGER_ID, True), (VENDOR_ID, False)],
        ids=["case_manager", "other_receiver"],
    )
    def test_commits_for_case_manager_only(
        self, use_case, build, semantic, receiver, commits
    ):
        dl = _store(receiver)
        event = extract_event(build(_offer(), actor=FINDER_ID))
        event = event.model_copy(update={"receiving_actor_id": receiver})

        result = use_case(dl, event, **_ports(dl)).execute()

        assert result.disposition is HandlerDisposition.APPLIED
        assert _committed(dl).count(semantic.value) == (1 if commits else 0)

    @pytest.mark.parametrize(
        ("use_case", "build", "semantic"),
        [
            (
                CloseReportReceivedUseCase,
                rm_close_report_activity,
                MessageSemantics.CLOSE_REPORT,
            ),
            (
                InvalidateReportReceivedUseCase,
                rm_invalidate_report_activity,
                MessageSemantics.INVALIDATE_REPORT,
            ),
        ],
        ids=["close", "invalidate"],
    )
    def test_no_case_for_the_report_commits_nothing(
        self, use_case, build, semantic
    ):
        """A refused activity leaves no canonical entry (CLP-10-009)."""
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=MANAGER_ID)
        event = extract_event(build(_offer(), actor=FINDER_ID))
        event = event.model_copy(update={"receiving_actor_id": MANAGER_ID})

        result = use_case(dl, event, **_ports(dl)).execute()

        assert result.disposition is HandlerDisposition.REFUSED
        assert _committed(dl) == []

    @pytest.mark.parametrize(
        ("use_case", "build", "finder_known", "sender_rm"),
        [
            (
                CloseReportReceivedUseCase,
                rm_close_report_activity,
                False,
                RM.RECEIVED,
            ),
            (
                InvalidateReportReceivedUseCase,
                rm_invalidate_report_activity,
                False,
                RM.RECEIVED,
            ),
            # Closed is terminal: declaring INVALID afterwards is backward.
            (
                InvalidateReportReceivedUseCase,
                rm_invalidate_report_activity,
                True,
                RM.CLOSED,
            ),
        ],
        ids=[
            "close-sender_not_a_participant",
            "invalidate-sender_not_a_participant",
            "invalidate-backward_declaration",
        ],
    )
    def test_refused_declaration_commits_nothing(
        self, use_case, build, finder_known, sender_rm
    ):
        """The case manager refuses ahead of the commit (CLP-10-009).

        Neither an unknown sender nor a backward RM move leaves a canonical
        entry behind.
        """
        dl = _store(MANAGER_ID, sender_rm, finder_known=finder_known)
        event = extract_event(build(_offer(), actor=FINDER_ID))
        event = event.model_copy(update={"receiving_actor_id": MANAGER_ID})

        result = use_case(dl, event, **_ports(dl)).execute()

        assert result.disposition is HandlerDisposition.REFUSED
        assert _committed(dl) == []

    def test_redelivered_activity_commits_once(self):
        """A repeat of the same activity is skipped and adds no entry."""
        dl = _store(MANAGER_ID)
        event = extract_event(
            rm_close_report_activity(_offer(), actor=FINDER_ID)
        )
        event = event.model_copy(update={"receiving_actor_id": MANAGER_ID})

        first = CloseReportReceivedUseCase(dl, event, **_ports(dl)).execute()
        second = CloseReportReceivedUseCase(dl, event, **_ports(dl)).execute()

        assert first.disposition is HandlerDisposition.APPLIED
        assert second.disposition is HandlerDisposition.SKIPPED
        assert _committed(dl).count("close_report") == 1


@pytest.mark.spec("CLP-10-013")
class TestAddCaseParticipantCommit:
    def _add_event(self, receiver: str):
        newcomer = as_CaseParticipant(
            id_=f"{CASE_ID}/participants/newcomer",
            attributed_to=NEWCOMER_ID,
            context=CASE_ID,
        )
        activity = add_participant_to_case_activity(
            newcomer, target=CASE_ID, actor=VENDOR_ID
        )
        event = extract_event(activity)
        return newcomer, cast(
            AddCaseParticipantToCaseReceivedEvent,
            event.model_copy(update={"receiving_actor_id": receiver}),
        )

    @pytest.mark.parametrize(
        ("receiver", "commits"),
        [(MANAGER_ID, True), (VENDOR_ID, False)],
        ids=["case_manager", "other_receiver"],
    )
    def test_commits_for_case_manager_only(self, receiver, commits):
        dl = _store(receiver)
        newcomer, event = self._add_event(receiver)
        dl.save(
            CaseParticipant(
                id_=newcomer.id_, attributed_to=NEWCOMER_ID, context=CASE_ID
            )
        )

        result = AddCaseParticipantToCaseReceivedUseCase(
            dl, event, **_ports(dl)
        ).execute()

        assert result.disposition is HandlerDisposition.APPLIED
        added = MessageSemantics.ADD_CASE_PARTICIPANT_TO_CASE.value
        assert _committed(dl).count(added) == (1 if commits else 0)

    def test_unknown_participant_commits_nothing(self):
        """The guard refuses ahead of the commit (CLP-10-009)."""
        dl = _store(MANAGER_ID)
        _, event = self._add_event(MANAGER_ID)  # participant never stored

        result = AddCaseParticipantToCaseReceivedUseCase(
            dl, event, **_ports(dl)
        ).execute()

        assert result.disposition is HandlerDisposition.REFUSED
        assert _committed(dl) == []


@pytest.mark.spec("CLP-10-013")
def test_announce_case_tree_has_no_commit_stage():
    """``Announce(VulnerabilityCase)`` is the documented exemption.

    Only the CASE_MANAGER sends it and only a participant replica receives it,
    so the tree carries no commit stage.
    """
    case = as_VulnerabilityCase(id_=CASE_ID, name="4304")
    event = cast(
        AnnounceVulnerabilityCaseReceivedEvent,
        extract_event(
            announce_vulnerability_case_activity(case, actor=MANAGER_ID)
        ),
    )

    tree = create_announce_vulnerability_case_received_tree(
        case_id=CASE_ID, case_obj=case, request=event
    )

    assert "GuardedCommitCaseLedgerEntryBT" not in [
        node.name for node in tree.iterate()
    ]
