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

"""Failure arms of the copy-model embargo nodes (#4715, ADR-0124).

A lifecycle node that only decides refuses what the lifecycle refuses and
writes nothing; one applying after intake's commit fails when the case
changed under its decision; the commit node raises without a decision; and a
received-answer node raises without the received answer.
"""

from types import SimpleNamespace

import pytest
from py_trees.common import Status

from test.core.behaviors.bt_harness import BTTestScenario
from test.core.behaviors.embargo.nodes.conftest import (
    CASE_MANAGER_ACTOR,
    OTHER_PARTICIPANT_ACTOR,
    make_case_with_manager,
)
from test.support.ledger import committed_event_types
from vultron.core.behaviors.embargo.decided_entries import EMBARGO_DECISION_KEY
from vultron.core.behaviors.embargo.nodes import lifecycle, withdrawal
from vultron.core.behaviors.embargo.nodes.lifecycle import (
    AcceptEmbargoLifecycleNode,
    ProposeEmbargoLifecycleNode,
)
from vultron.core.behaviors.embargo.nodes.manager_commit import (
    CommitEmbargoDecisionNode,
)
from vultron.core.behaviors.embargo.nodes.proposal import (
    RecordParticipantAcceptanceNode,
)
from vultron.core.behaviors.embargo.nodes.withdrawal import (
    EmbargoWithdrawalAppliesNode,
    RecordParticipantWithdrawalNode,
)
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.states.em import EM
from vultron.errors import VultronBTInternalError, VultronEntryRefusedError
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent


def _seed(bt_scenario: BTTestScenario, suffix: str, em_state: EM) -> str:
    """Seed the scenario's store (the CASE_MANAGER's) with a case."""
    case, _cm, dl = make_case_with_manager(
        suffix, em_state=em_state, other_consent=None
    )
    assert dl.read(case.id_) is not None
    assert bt_scenario.dl.read(case.id_) is not None, "one store per actor"
    return case.id_


@pytest.mark.executes_as(CASE_MANAGER_ACTOR)
def test_a_refused_decision_fails_and_leaves_no_decision(
    bt_scenario: BTTestScenario,
) -> None:
    """``EXITED`` admits no proposal: the decision fails, nothing staged."""
    case_id = _seed(bt_scenario, "copy-refused", EM.EXITED)
    result_out: dict[str, object] = {}
    embargo = as_EmbargoEvent(
        id_=f"{case_id}/embargo_events/late",
        context=case_id,
        end_time=days_from_now_utc(30),
    )

    result = bt_scenario.run(
        ProposeEmbargoLifecycleNode(
            case_id=case_id,
            embargo_id=embargo.id_,
            result_out=result_out,
            embargo=embargo,
        ).deciding()
    )

    bt_scenario.assert_failure(result)
    assert EMBARGO_DECISION_KEY not in result_out
    assert "error" in result_out


@pytest.mark.executes_as(CASE_MANAGER_ACTOR)
def test_applying_after_a_case_that_changed_fails_without_a_write(
    bt_scenario: BTTestScenario, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The trial refuses an entry because the case moved: FAILURE."""
    case_id = _seed(bt_scenario, "copy-moved", EM.PROPOSED)
    embargo_id = "https://example.org/cases/case_copy-moved/embargo_events/e1"
    before = committed_event_types(bt_scenario.dl, case_id)

    def _refuse(**_kwargs: object) -> None:
        raise VultronEntryRefusedError("the case moved")

    monkeypatch.setattr(lifecycle, "commit_and_apply_decision", _refuse)
    result_out: dict[str, object] = {}
    result = bt_scenario.run(
        AcceptEmbargoLifecycleNode(
            case_id=case_id, embargo_id=embargo_id, result_out=result_out
        ).applying_after(cause_id="https://example.org/activities/accept")
    )

    bt_scenario.assert_failure(result, reason="the case moved")
    assert committed_event_types(bt_scenario.dl, case_id) == before


@pytest.mark.executes_as(CASE_MANAGER_ACTOR)
def test_a_commit_node_with_no_decision_raises(
    bt_scenario: BTTestScenario,
) -> None:
    """A deciding lifecycle node must run first; without it, a fault."""
    case_id = _seed(bt_scenario, "copy-no-decision", EM.PROPOSED)

    result = bt_scenario.run(
        CommitEmbargoDecisionNode(
            case_id=case_id,
            event_type="accept_invite_to_embargo_on_case",
            builder=lambda _to: ("urn:uuid:act", '{"id": "urn:uuid:act"}'),
            decision_from={},
        )
    )

    assert result.status == Status.FAILURE
    assert result.internal_error
    assert "no embargo decision" in (result.feedback_message or "")


@pytest.mark.executes_as(CASE_MANAGER_ACTOR)
def test_an_answer_node_with_no_received_answer_raises(
    bt_scenario: BTTestScenario,
) -> None:
    """The row's cause is the received answer; a tree without it is a fault."""
    case_id = _seed(bt_scenario, "copy-no-answer", EM.PROPOSED)

    result = bt_scenario.run(
        RecordParticipantAcceptanceNode(
            case_id=case_id,
            embargo_id=f"{case_id}/embargo_events/e1",
            accepting_actor_id=OTHER_PARTICIPANT_ACTOR,
        )
    )

    assert result.status == Status.FAILURE
    assert result.internal_error
    assert "no received act" in (result.feedback_message or "")


@pytest.mark.executes_as(CASE_MANAGER_ACTOR)
def test_an_answer_node_records_the_row_on_the_answers_own_entry(
    bt_scenario: BTTestScenario,
) -> None:
    """Applying an answer intake committed adds no entry (ADR-0122)."""
    case_id = _seed(bt_scenario, "copy-answer", EM.PROPOSED)
    before = committed_event_types(bt_scenario.dl, case_id)

    result = bt_scenario.run(
        RecordParticipantAcceptanceNode(
            case_id=case_id,
            embargo_id=f"{case_id}/embargo_events/e1",
            accepting_actor_id=OTHER_PARTICIPANT_ACTOR,
        ),
        activity=SimpleNamespace(
            activity_id="https://example.org/activities/accept"
        ),
    )

    bt_scenario.assert_success(result)
    assert committed_event_types(bt_scenario.dl, case_id) == before


# ---------------------------------------------------------------------------
# #4717: the received withdrawal's decision guard and effect
# ---------------------------------------------------------------------------


@pytest.mark.executes_as(CASE_MANAGER_ACTOR)
def test_the_withdrawal_guard_refuses_what_the_lifecycle_refuses(
    bt_scenario: BTTestScenario,
) -> None:
    """No embargo in force: the staged decision refuses; nothing written."""
    case_id = _seed(bt_scenario, "copy-withdraw-guard", EM.PROPOSED)
    before = committed_event_types(bt_scenario.dl, case_id)

    result = bt_scenario.run(
        EmbargoWithdrawalAppliesNode(
            case_id=case_id,
            embargo_id=f"{case_id}/embargo_events/e1",
            withdrawing_actor_id=OTHER_PARTICIPANT_ACTOR,
        )
    )

    bt_scenario.assert_failure(result, reason="records nothing")
    assert committed_event_types(bt_scenario.dl, case_id) == before


@pytest.mark.executes_as(CASE_MANAGER_ACTOR)
def test_the_withdrawal_guard_raises_on_a_decision_fault(
    bt_scenario: BTTestScenario, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A decision whose entries do not carry its writes is a fault."""
    case_id = _seed(bt_scenario, "copy-withdraw-fault", EM.ACTIVE)

    def _fault(*_args: object, **_kwargs: object) -> None:
        raise VultronBTInternalError("the entries do not carry it")

    monkeypatch.setattr(withdrawal, "decide_embargo_act", _fault)
    result = bt_scenario.run(
        EmbargoWithdrawalAppliesNode(
            case_id=case_id,
            embargo_id=f"{case_id}/embargo_events/e1",
            withdrawing_actor_id=OTHER_PARTICIPANT_ACTOR,
        )
    )

    assert result.status == Status.FAILURE
    assert result.internal_error


@pytest.mark.executes_as(CASE_MANAGER_ACTOR)
def test_a_withdrawal_effect_whose_decision_is_refused_writes_nothing(
    bt_scenario: BTTestScenario,
) -> None:
    """The case changed since the guard (no embargo in force): FAILURE."""
    case_id = _seed(bt_scenario, "copy-withdraw-moved", EM.PROPOSED)
    before = committed_event_types(bt_scenario.dl, case_id)

    result = bt_scenario.run(
        RecordParticipantWithdrawalNode(
            case_id=case_id,
            embargo_id=f"{case_id}/embargo_events/e1",
            withdrawing_actor_id=OTHER_PARTICIPANT_ACTOR,
        ),
        activity=SimpleNamespace(
            activity_id="https://example.org/activities/leave"
        ),
    )

    assert result.status == Status.FAILURE
    assert not result.internal_error
    assert committed_event_types(bt_scenario.dl, case_id) == before
