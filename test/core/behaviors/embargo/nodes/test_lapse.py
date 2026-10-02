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

"""Invite-lapse leaves (``nodes/lapse.py``, CM-28-014).

The evaluation, condition and apply leaves are exercised as the CASE_MANAGER
would run them; the replay leaf as a replica applying a committed lapse entry.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from py_trees.common import Status

from test.core.behaviors.bt_harness import BTTestScenario
from test.core.behaviors.sync.nodes.conftest import (
    _make_event,
    _to_persistable_entry,
)
from vultron.core.behaviors.embargo.nodes.lapse import (
    DECLINES_KEY,
    IS_LAPSED_KEY,
    ApplyInviteLapseFromLedgerNode,
    EvaluateInviteLapseNode,
    InviteLapseDeclinesNode,
    RecordInviteLapseNode,
)
from vultron.core.behaviors.sync.nodes.event_conditions import (
    INVITE_LAPSED_EVENT_TYPE,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.objects.vulnerability_case import (  # noqa: F401
    as_VulnerabilityCase,
)

CASE_ID = "https://example.org/cases/lapse-nodes"
MANAGER = "https://example.org/actors/lapse-nodes-manager"
INVITEE = "https://example.org/actors/lapse-nodes-invitee"
NOW = datetime.now(tz=UTC)


def _seed(
    scenario: BTTestScenario,
    pec: PEC = PEC.INVITED,
    deadline: datetime | None = None,
) -> str:
    manager = CaseParticipant(
        id_=f"{CASE_ID}/participants/manager",
        attributed_to=MANAGER,
        context=CASE_ID,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    invitee = CaseParticipant(
        id_=f"{CASE_ID}/participants/invitee",
        attributed_to=INVITEE,
        context=CASE_ID,
        embargo_consent_state=pec,
        invite_rsvp_deadline=deadline,
    )
    case = VulnerabilityCase(
        id_=CASE_ID,
        attributed_to=MANAGER,
        case_participants=[manager.id_, invitee.id_],
        actor_participant_index={
            MANAGER: manager.id_,
            INVITEE: invitee.id_,
        },
    )
    case.append_case_status(em_state=EM.ACTIVE)
    scenario.seed(manager, invitee, case)
    return invitee.id_


def _pec(scenario: BTTestScenario, participant_id: str) -> PEC:
    record = scenario.dl.read(participant_id)
    assert isinstance(record, CaseParticipant)
    return PEC(record.embargo_consent_state)


class TestEvaluateInviteLapseNode:
    def _evaluate(
        self, scenario: BTTestScenario, case_id: str = CASE_ID
    ) -> tuple[Any, dict[str, Any]]:
        out: dict[str, Any] = {}
        node = EvaluateInviteLapseNode(
            case_id=case_id, invitee_id=INVITEE, now=NOW, result_out=out
        )
        return scenario.run(node), out

    @pytest.mark.executes_as(MANAGER)
    @pytest.mark.spec("CM-28-014")
    def test_a_passed_deadline_reports_a_due_lapse_and_writes_nothing(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """The guard only reads: the DECLINE waits for the commit (CLP-10-006)."""
        participant_id = _seed(bt_scenario, deadline=NOW - timedelta(hours=1))
        result, out = self._evaluate(bt_scenario)
        bt_scenario.assert_success(result)
        assert out == {IS_LAPSED_KEY: True, DECLINES_KEY: True}
        assert _pec(bt_scenario, participant_id) is PEC.INVITED

    @pytest.mark.executes_as(MANAGER)
    def test_a_lapsed_invitee_already_declined_is_lapsed_but_not_declined_again(
        self, bt_scenario: BTTestScenario
    ) -> None:
        participant_id = _seed(
            bt_scenario, pec=PEC.DECLINED, deadline=NOW - timedelta(hours=1)
        )
        result, out = self._evaluate(bt_scenario)
        bt_scenario.assert_success(result)
        assert out == {IS_LAPSED_KEY: True, DECLINES_KEY: False}
        assert _pec(bt_scenario, participant_id) is PEC.DECLINED

    @pytest.mark.executes_as(MANAGER)
    def test_no_deadline_is_no_lapse(
        self, bt_scenario: BTTestScenario
    ) -> None:
        participant_id = _seed(bt_scenario, deadline=None)
        result, out = self._evaluate(bt_scenario)
        bt_scenario.assert_success(result)
        assert out == {IS_LAPSED_KEY: False, DECLINES_KEY: False}
        assert _pec(bt_scenario, participant_id) is PEC.INVITED

    @pytest.mark.executes_as(MANAGER)
    def test_a_missing_case_fails_and_reports_no_lapse(
        self, bt_scenario: BTTestScenario
    ) -> None:
        result, out = self._evaluate(
            bt_scenario, case_id="https://example.org/cases/none"
        )
        assert result.status == Status.FAILURE
        assert out == {IS_LAPSED_KEY: False, DECLINES_KEY: False}


class TestInviteLapseDeclinesNode:
    @pytest.mark.parametrize(
        ("out", "expected"),
        [
            ({DECLINES_KEY: True}, Status.SUCCESS),
            ({DECLINES_KEY: False}, Status.FAILURE),
            ({}, Status.FAILURE),
        ],
    )
    def test_succeeds_only_when_the_evaluation_found_a_lapse_to_apply(
        self, bt_scenario: BTTestScenario, out: dict, expected: Status
    ) -> None:
        result = bt_scenario.run(InviteLapseDeclinesNode(result_out=out))
        assert result.status == expected


class TestRecordInviteLapseNode:
    @pytest.mark.executes_as(MANAGER)
    @pytest.mark.spec("CM-28-014")
    def test_declines_the_invitee_in_the_managers_store(
        self, bt_scenario: BTTestScenario
    ) -> None:
        participant_id = _seed(bt_scenario, deadline=NOW - timedelta(hours=1))
        result = bt_scenario.run(
            RecordInviteLapseNode(case_id=CASE_ID, invitee_id=INVITEE)
        )
        bt_scenario.assert_success(result)
        assert _pec(bt_scenario, participant_id) is PEC.DECLINED

    @pytest.mark.executes_as(MANAGER)
    def test_a_missing_participant_record_is_an_internal_error(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """Regime 1: the guard just read the record, so its absence is ours."""
        result = bt_scenario.run(
            RecordInviteLapseNode(
                case_id="https://example.org/cases/none", invitee_id=INVITEE
            )
        )
        bt_scenario.assert_failure(
            result, reason="cannot be read", allow_internal=True
        )


def _lapse_event(actor: str | None) -> Any:
    snapshot: dict[str, Any] = {"type": "Lapse", "context": CASE_ID}
    if actor is not None:
        snapshot["actor"] = actor
    entry = _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=CASE_ID,
            log_index=0,
            object_id=f"{CASE_ID}/embargo_invites/i1",
            event_type=INVITE_LAPSED_EVENT_TYPE,
            payload_snapshot=snapshot,
            prev_log_hash="0" * 64,
        )
    )
    return _make_event(entry, actor_id=MANAGER)


class TestApplyInviteLapseFromLedgerNode:
    @pytest.mark.executes_as(INVITEE)
    @pytest.mark.spec("CM-28-014")
    def test_a_replica_applies_the_managers_lapse_without_a_deadline(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """No deadline on the replica's record: it applies, never computes."""
        participant_id = _seed(bt_scenario, deadline=None)
        result = bt_scenario.run(
            ApplyInviteLapseFromLedgerNode(name="ApplyLapse"),
            activity=_lapse_event(INVITEE),
        )
        bt_scenario.assert_success(result)
        assert _pec(bt_scenario, participant_id) is PEC.DECLINED

    @pytest.mark.executes_as(INVITEE)
    def test_an_entry_naming_no_invitee_fails(
        self, bt_scenario: BTTestScenario
    ) -> None:
        participant_id = _seed(bt_scenario)
        result = bt_scenario.run(
            ApplyInviteLapseFromLedgerNode(name="ApplyLapse"),
            activity=_lapse_event(None),
        )
        assert result.status == Status.FAILURE
        assert _pec(bt_scenario, participant_id) is PEC.INVITED

    @pytest.mark.executes_as(INVITEE)
    def test_an_invitee_the_replica_does_not_hold_is_skipped(
        self, bt_scenario: BTTestScenario
    ) -> None:
        _seed(bt_scenario)
        result = bt_scenario.run(
            ApplyInviteLapseFromLedgerNode(name="ApplyLapse"),
            activity=_lapse_event("https://example.org/actors/elsewhere"),
        )
        bt_scenario.assert_success(result)

    @pytest.mark.executes_as(INVITEE)
    def test_a_replica_without_the_case_skips(
        self, bt_scenario: BTTestScenario
    ) -> None:
        result = bt_scenario.run(
            ApplyInviteLapseFromLedgerNode(name="ApplyLapse"),
            activity=_lapse_event(INVITEE),
        )
        bt_scenario.assert_success(result)
