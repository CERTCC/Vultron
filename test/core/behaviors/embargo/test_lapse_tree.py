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

"""The CASE_MANAGER-gated invite-lapse tree (``lapse_tree.py``, CM-28-014).

Only the CASE_MANAGER evaluates lapse, and its CM-28-009 entry is committed
behind the role gate, before the DECLINE it records is applied.  A lapse
already applied is not committed twice, a commit that fails applies nothing so
a retry commits it, and a store that is not the CASE_MANAGER runs nothing at
all.
"""

from datetime import UTC, datetime, timedelta
from typing import Any, cast

import py_trees
import pytest
from py_trees.common import Status

from test.core.behaviors.bt_harness import BTTestScenario
from vultron.core.behaviors.embargo.lapse_tree import (
    create_invite_lapse_tree,
    lapse_payload_snapshot,
)
from vultron.core.behaviors.embargo.nodes.lapse import (
    DECLINES_KEY,
    IS_LAPSED_KEY,
)
from vultron.core.behaviors.sync.nodes.event_conditions import (
    INVITE_LAPSED_EVENT_TYPE,
)
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import (  # noqa: F401
    as_VulnerabilityCase,
)

CASE_ID = "https://example.org/cases/lapse-tree"
EMBARGO_ID = f"{CASE_ID}/embargo_events/e1"
INVITE_ID = f"{CASE_ID}/embargo_invites/i1"
MANAGER = "https://example.org/actors/lapse-manager"
INVITEE = "https://example.org/actors/lapse-invitee"
REPLICA = "https://example.org/actors/lapse-replica"
PUBLISHED = datetime.now(tz=UTC).replace(microsecond=0).isoformat()
NOW = datetime.now(tz=UTC)


def _seed(
    scenario: BTTestScenario, pec: PEC, deadline: datetime | None
) -> str:
    """A case under an active embargo, ``MANAGER`` holding the role."""
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
        case_roles=[CVDRole.VENDOR],
        embargo_consent_state=pec,
        invite_rsvp_deadline=deadline,
    )
    case = VulnerabilityCase(
        id_=CASE_ID,
        name="Lapse tree",
        attributed_to=MANAGER,
        case_participants=[manager.id_, invitee.id_],
        actor_participant_index={
            MANAGER: manager.id_,
            INVITEE: invitee.id_,
        },
    )
    case.append_case_status(em_state=EM.ACTIVE)
    case.set_embargo(EMBARGO_ID)
    embargo = as_EmbargoEvent(
        id_=EMBARGO_ID, context=CASE_ID, end_time=days_from_now_utc(45)
    )
    scenario.seed(manager, invitee, case, embargo)
    return invitee.id_


def _run(scenario: BTTestScenario) -> tuple[Any, dict[str, Any]]:
    result_out: dict[str, Any] = {}
    tree = create_invite_lapse_tree(
        case_id=CASE_ID,
        invitee_id=INVITEE,
        invite_id=INVITE_ID,
        embargo_id=EMBARGO_ID,
        published=PUBLISHED,
        now=NOW,
        result_out=result_out,
    )
    return scenario.run(tree), result_out


def _pec(scenario: BTTestScenario, participant_id: str) -> PEC:
    record = scenario.dl.read(participant_id)
    assert isinstance(record, CaseParticipant)
    return PEC(record.embargo_consent_state)


def _lapse_entries(scenario: BTTestScenario) -> list[CaseLedgerEntry]:
    return [
        cast(CaseLedgerEntry, e)
        for e in scenario.dl.list_objects("CaseLedgerEntry")
        if cast(CaseLedgerEntry, e).event_type == INVITE_LAPSED_EVENT_TYPE
    ]


@pytest.mark.executes_as(MANAGER)
@pytest.mark.spec("CM-28-014")
@pytest.mark.spec("CM-28-009")
def test_the_manager_lapses_a_passed_deadline_and_commits_the_entry(
    bt_scenario: BTTestScenario,
) -> None:
    participant_id = _seed(bt_scenario, PEC.INVITED, NOW - timedelta(days=1))

    result, out = _run(bt_scenario)

    bt_scenario.assert_success(result)
    assert out == {IS_LAPSED_KEY: True, DECLINES_KEY: True}
    assert _pec(bt_scenario, participant_id) is PEC.DECLINED
    (entry,) = _lapse_entries(bt_scenario)
    assert entry.log_object_id == INVITE_ID
    # Attributed to the invitee, at its own claimed time (CLP-15-003).
    assert entry.payload_snapshot["actor"] == INVITEE
    assert entry.payload_snapshot["published"] == PUBLISHED


class _FailingCommit(py_trees.behaviour.Behaviour):
    """Stands in for the lapse entry's commit, which fails."""

    def update(self) -> Status:
        self.feedback_message = "commit unavailable"
        return Status.FAILURE


@pytest.mark.executes_as(MANAGER)
@pytest.mark.spec("CM-28-009")
@pytest.mark.spec("CLP-10-006")
def test_a_failed_commit_applies_nothing_so_a_retry_commits_the_lapse(
    bt_scenario: BTTestScenario, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Guard, then commit, then effect: a lost commit is not a lost lapse."""
    participant_id = _seed(bt_scenario, PEC.INVITED, NOW - timedelta(days=1))
    monkeypatch.setattr(
        "vultron.core.behaviors.embargo.lapse_tree.create_commit_log_entry_tree",
        lambda **_: _FailingCommit(name="FailingCommit"),
    )

    failed, _ = _run(bt_scenario)

    bt_scenario.assert_failure(failed)
    assert _pec(bt_scenario, participant_id) is PEC.INVITED
    assert _lapse_entries(bt_scenario) == []

    monkeypatch.undo()
    retried, out = _run(bt_scenario)

    bt_scenario.assert_success(retried)
    assert out == {IS_LAPSED_KEY: True, DECLINES_KEY: True}
    assert _pec(bt_scenario, participant_id) is PEC.DECLINED
    assert len(_lapse_entries(bt_scenario)) == 1


@pytest.mark.executes_as(MANAGER)
@pytest.mark.spec("CM-28-014")
def test_an_open_invite_commits_nothing(bt_scenario: BTTestScenario) -> None:
    participant_id = _seed(bt_scenario, PEC.INVITED, NOW + timedelta(days=3))

    result, out = _run(bt_scenario)

    bt_scenario.assert_success(result)
    assert out == {IS_LAPSED_KEY: False, DECLINES_KEY: False}
    assert _pec(bt_scenario, participant_id) is PEC.INVITED
    assert _lapse_entries(bt_scenario) == []


@pytest.mark.executes_as(MANAGER)
@pytest.mark.spec("CM-28-009")
def test_a_lapse_already_applied_is_not_committed_twice(
    bt_scenario: BTTestScenario,
) -> None:
    """Still lapsed for routing, but the entry was written the first time."""
    _seed(bt_scenario, PEC.DECLINED, NOW - timedelta(days=1))

    result, out = _run(bt_scenario)

    bt_scenario.assert_success(result)
    assert out[IS_LAPSED_KEY] is True
    assert out[DECLINES_KEY] is False
    assert _lapse_entries(bt_scenario) == []


@pytest.mark.executes_as(REPLICA)
@pytest.mark.spec("CM-28-014")
@pytest.mark.spec("CM-28-003")
def test_a_store_that_is_not_the_manager_runs_nothing(
    bt_scenario: BTTestScenario,
) -> None:
    """The gate passes over a non-manager: no evaluation, no consent, no entry."""
    participant_id = _seed(bt_scenario, PEC.INVITED, NOW - timedelta(days=1))

    result, out = _run(bt_scenario)

    bt_scenario.assert_success(result)
    assert out == {}
    assert _pec(bt_scenario, participant_id) is PEC.INVITED
    assert _lapse_entries(bt_scenario) == []


@pytest.mark.executes_as(MANAGER)
def test_an_actor_with_no_record_has_no_invite_to_lapse(
    bt_scenario: BTTestScenario,
) -> None:
    _seed(bt_scenario, PEC.INVITED, NOW - timedelta(days=1))
    result_out: dict[str, Any] = {}
    tree = create_invite_lapse_tree(
        case_id=CASE_ID,
        invitee_id="https://example.org/actors/stranger",
        invite_id=INVITE_ID,
        embargo_id=EMBARGO_ID,
        published=PUBLISHED,
        now=NOW,
        result_out=result_out,
    )

    result = bt_scenario.run(tree)

    bt_scenario.assert_success(result)
    assert result_out == {IS_LAPSED_KEY: False, DECLINES_KEY: False}
    assert _lapse_entries(bt_scenario) == []


def test_lapse_payload_snapshot_names_the_invite_and_its_embargo() -> None:
    snapshot = lapse_payload_snapshot(
        case_id=CASE_ID,
        invitee_id=INVITEE,
        invite_id=INVITE_ID,
        embargo_id=EMBARGO_ID,
        published=PUBLISHED,
    )

    assert snapshot == {
        "type": "Lapse",
        "actor": INVITEE,
        "context": CASE_ID,
        "published": PUBLISHED,
        "object": {
            "type": "Invite",
            "id": INVITE_ID,
            "object": {"type": "EmbargoEvent", "id": EMBARGO_ID},
        },
    }
