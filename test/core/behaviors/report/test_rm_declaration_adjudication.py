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

"""The activity-typed RM handlers apply the RM rule of Add(ParticipantStatus).

Report valid / invalid / closed and engage / defer each declare one RM state
for their sender.  The CASE_MANAGER adjudicates that declaration exactly as it
adjudicates the ``rmState`` of an ``Add(ParticipantStatus)``: a forward move is
recorded, a non-adjacent one included and flagged with the RSH-06-004 note; a
backward one is refused and the recorded state kept (RSH-06-006).

Every case comes from the table in ``test/support/rm_declaration.py`` that
``test/core/behaviors/status/test_partial_accept_participant_status.py`` runs
the ``Add(ParticipantStatus)`` path against, so the two paths are asserted
against the same rows (#3813 AC-4).

The handlers run as the CASE_MANAGER, in its store; the subject of every write
is the sender (RSH-08-001).
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from itertools import pairwise
from typing import Any, cast

import pytest

from test.support.embargo_register import activate
from test.support.rm_declaration import (
    ACTOR_ID,
    CASE_ID,
    CASE_MANAGER_ID,
    CM_PARTICIPANT_ID,
    PARTICIPANT_ID,
    REPORT_ID,
    STRANGER_ID,
    RMDeclarationCase,
    assert_anomaly_flagged_and_noted,
    cases_declaring,
    current_status,
    queued_notes,
    recorded_rm,
    seed_case,
    status_count,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.status.add_participant_status_tree import (
    add_participant_status_tree,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.dimensions import RmDimension
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.cs import CS_pxa, CS_vf
from vultron.core.states.rm import RM, RMDeclaration
from vultron.core.use_cases.received.case.engage_defer import (
    DeferCaseReceivedUseCase,
    EngageCaseReceivedUseCase,
)
from vultron.core.use_cases.received.report import (
    CloseReportReceivedUseCase,
    InvalidateReportReceivedUseCase,
    ValidateReportReceivedUseCase,
)
from vultron.wire.as2.factories import (
    add_status_to_participant_activity,
    rm_close_report_activity,
    rm_defer_case_activity,
    rm_engage_case_activity,
    rm_invalidate_report_activity,
    rm_submit_report_activity,
    rm_validate_report_activity,
)
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.case_status import as_ParticipantStatus
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)


def _offer() -> Any:
    return rm_submit_report_activity(
        as_VulnerabilityReport(id_=REPORT_ID, name="Shared RM table report"),
        to=ACTOR_ID,
        actor="https://example.org/actors/finder",
    )


def _case_ref() -> as_VulnerabilityCase:
    return as_VulnerabilityCase(id_=CASE_ID, name="Issue 2235 Case")


@dataclass(frozen=True)
class _Handler:
    """One activity-typed RM handler: the RM it declares and how to send it."""

    declared: RM
    use_case: type
    build: Callable[[str], Any]


_HANDLERS: dict[RM, _Handler] = {
    RM.VALID: _Handler(
        RM.VALID,
        ValidateReportReceivedUseCase,
        lambda actor: rm_validate_report_activity(_offer(), actor=actor),
    ),
    RM.INVALID: _Handler(
        RM.INVALID,
        InvalidateReportReceivedUseCase,
        lambda actor: rm_invalidate_report_activity(_offer(), actor=actor),
    ),
    RM.CLOSED: _Handler(
        RM.CLOSED,
        CloseReportReceivedUseCase,
        lambda actor: rm_close_report_activity(_offer(), actor=actor),
    ),
    RM.ACCEPTED: _Handler(
        RM.ACCEPTED,
        EngageCaseReceivedUseCase,
        lambda actor: rm_engage_case_activity(_case_ref(), actor=actor),
    ),
    RM.DEFERRED: _Handler(
        RM.DEFERRED,
        DeferCaseReceivedUseCase,
        lambda actor: rm_defer_case_activity(_case_ref(), actor=actor),
    ),
}


def _seed(dl: SqliteDataLayer, current: RM) -> None:
    """The CASE_MANAGER's replica, with the sender recorded at *current*."""
    seed_case(dl, current_status(current, CS_vf.Vf, CS_pxa.pxa), None)
    # DUR-07-004: the validate path needs an embargo on the case.
    case = cast(VulnerabilityCase, dl.read(CASE_ID))
    activate(case, f"{CASE_ID}/embargoes/shared-table")
    dl.save(case)


def _deliver(
    dl: SqliteDataLayer, declared: RM, make_payload, sender: str = ACTOR_ID
) -> Any:
    handler = _HANDLERS[declared]
    event = make_payload(handler.build(sender))
    return handler.use_case(
        dl,
        event,
        trigger_activity=TriggerActivityAdapter(dl),
        sync_port=SyncActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
    ).execute()


@pytest.mark.executes_as(CASE_MANAGER_ID)
class TestActivityTypedHandlersApplyTheSharedRule:
    """Each handler, against every row of the shared table that it declares."""

    @pytest.mark.spec("RSH-06-001")
    @pytest.mark.spec("RSH-06-002")
    @pytest.mark.spec("RSH-06-006")
    @pytest.mark.spec("RSH-08-001")
    @pytest.mark.parametrize("case", cases_declaring(*_HANDLERS))
    def test_records_what_the_rule_accepts(
        self, case: RMDeclarationCase, store_for, make_payload
    ):
        dl = store_for(CASE_MANAGER_ID)
        _seed(dl, case.current)
        before = status_count(dl)

        result = _deliver(dl, case.declared, make_payload)

        assert recorded_rm(dl) == case.expected_rm
        if case.verdict is RMDeclaration.CONFIRMATION:
            assert status_count(dl) == before, (
                "a confirmation is recorded once (RSH-08-002)"
            )
            # Engage still runs the CASE_MANAGER's broadcast, and validate
            # skips only on its report-link latch (absent in this store), so
            # neither is a pure no-op; the rest report the restatement as
            # skipped.
            if case.declared in (RM.ACCEPTED, RM.VALID):
                assert result.disposition is HandlerDisposition.APPLIED, (
                    result.reason
                )
            else:
                assert result.disposition is HandlerDisposition.SKIPPED, (
                    result.reason
                )
        elif case.accepted:
            assert result.disposition is HandlerDisposition.APPLIED, (
                result.reason
            )
            assert status_count(dl) == before + 1, "one move, one record"
        else:
            assert result.disposition is HandlerDisposition.REFUSED
            assert status_count(dl) == before, "a refusal writes nothing"

    @pytest.mark.spec("RSH-06-003")
    @pytest.mark.spec("RSH-06-004")
    @pytest.mark.spec("RSH-06-005")
    @pytest.mark.parametrize("case", cases_declaring(*_HANDLERS))
    def test_flags_and_notes_the_same_anomalies(
        self, case: RMDeclarationCase, store_for, make_payload, caplog
    ):
        dl = store_for(CASE_MANAGER_ID)
        _seed(dl, case.current)

        with caplog.at_level(logging.WARNING):
            _deliver(dl, case.declared, make_payload)

        # Same as the Add(ParticipantStatus) path.
        assert_anomaly_flagged_and_noted(case, dl, caplog.records)


@pytest.mark.executes_as(CASE_MANAGER_ID)
class TestSenderMustBeAParticipant:
    """Every activity-typed RM handler refuses a non-participant (HP-01-006)."""

    @pytest.mark.spec("HP-01-006")
    @pytest.mark.parametrize(
        "declared", list(_HANDLERS), ids=lambda rm: rm.name
    )
    def test_non_participant_sender_is_refused(
        self, declared: RM, store_for, make_payload
    ):
        dl = store_for(CASE_MANAGER_ID)
        _seed(dl, RM.RECEIVED)
        before = status_count(dl)
        manager_before = status_count(dl, CM_PARTICIPANT_ID)

        result = _deliver(dl, declared, make_payload, sender=STRANGER_ID)

        assert result.disposition is HandlerDisposition.REFUSED
        assert status_count(dl) == before
        # Not the receiver's either: the receiver is not the mover (RSH-08-001).
        assert status_count(dl, CM_PARTICIPANT_ID) == manager_before


def _run_status_declaration(dl: SqliteDataLayer, rm: RM, make_payload) -> Any:
    """Deliver ``Add(ParticipantStatus)`` declaring *rm* for the sender."""
    status = as_ParticipantStatus(
        id_=f"{PARTICIPANT_ID}/statuses/declared-{rm.name.lower()}",
        context=CASE_ID,
        attributed_to=ACTOR_ID,
        rm=RmDimension(state=rm),
    )
    dl.create(status)
    activity = add_status_to_participant_activity(
        status=status,
        target=as_CaseParticipant(
            id_=PARTICIPANT_ID, context=CASE_ID, attributed_to=ACTOR_ID
        ),
        actor=ACTOR_ID,
        context=_case_ref(),
    )
    event = make_payload(activity)
    bridge = BTBridge(
        datalayer=dl,
        trigger_activity=TriggerActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
        sync_port=SyncActivityAdapter(dl),
    )
    return bridge.execute_with_setup(
        tree=add_participant_status_tree(request=event, case_id=CASE_ID),
        actor_id=CASE_MANAGER_ID,
        activity=event,
    )


def _rm_history(dl: SqliteDataLayer) -> list[RM]:
    participant = cast(CaseParticipant, dl.read(PARTICIPANT_ID))
    return [s.rm.state for s in participant.participant_statuses]


def _transitions(history: list[RM]) -> list[tuple[RM, RM]]:
    return [(a, b) for a, b in pairwise(history) if a != b]


@pytest.mark.executes_as(CASE_MANAGER_ID)
class TestActAndDeclarationAreOneMove:
    """An act and its matching status declaration are one move (RSH-08-002)."""

    @pytest.mark.spec("RSH-08-002")
    def test_act_then_declaration_is_a_confirmation(
        self, store_for, make_payload, caplog
    ):
        dl = store_for(CASE_MANAGER_ID)
        _seed(dl, RM.RECEIVED)
        seeded = len(_rm_history(dl)) - 1

        with caplog.at_level(logging.WARNING):
            act = _deliver(dl, RM.INVALID, make_payload)
            declaration = _run_status_declaration(dl, RM.INVALID, make_payload)

        assert act.disposition is HandlerDisposition.APPLIED, act.reason
        assert declaration.status.name == "SUCCESS"
        assert _transitions(_rm_history(dl)[seeded:]) == [
            (RM.RECEIVED, RM.INVALID)
        ]
        assert queued_notes(dl) == []
        assert not [r for r in caplog.records if "RM " in r.getMessage()]

    @pytest.mark.spec("RSH-08-002")
    def test_declaration_then_act_is_a_confirmation(
        self, store_for, make_payload, caplog
    ):
        dl = store_for(CASE_MANAGER_ID)
        _seed(dl, RM.RECEIVED)
        seeded = len(_rm_history(dl)) - 1

        _run_status_declaration(dl, RM.INVALID, make_payload)
        before = status_count(dl)
        with caplog.at_level(logging.WARNING):
            act = _deliver(dl, RM.INVALID, make_payload)

        assert act.disposition is HandlerDisposition.SKIPPED, act.reason
        assert status_count(dl) == before, "a confirmation is recorded once"
        assert _transitions(_rm_history(dl)[seeded:]) == [
            (RM.RECEIVED, RM.INVALID)
        ]
        assert queued_notes(dl) == []
        assert not [
            r for r in caplog.records if "declared by" in r.getMessage()
        ]


@pytest.mark.executes_as(CASE_MANAGER_ID)
class TestAnomalyFlagDoesNotLeakAcrossRuns:
    """A gap flagged by one run posts no note in a later run (RSH-06-004).

    ``BB_RM_ANOMALY`` lives on py_trees' process-global blackboard, so the
    guard must clear it on every tick; otherwise a later confirmation would
    re-post the earlier run's clarification note.
    """

    @pytest.mark.spec("RSH-06-004")
    @pytest.mark.spec("RSH-08-002")
    def test_confirmation_after_a_gap_posts_no_note(
        self, store_for, make_payload
    ):
        dl = store_for(CASE_MANAGER_ID)
        _seed(dl, RM.VALID)
        _deliver(dl, RM.CLOSED, make_payload)
        assert len(queued_notes(dl)) == 1, "precondition: one gap note"

        # The sender is now recorded CLOSED: a restated CLOSED confirms.
        result = _deliver(dl, RM.CLOSED, make_payload)

        assert result.disposition is HandlerDisposition.SKIPPED, result.reason
        assert len(queued_notes(dl)) == 1, "the confirmation posts no note"
