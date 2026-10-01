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

"""``RMClosureWriter`` closes an RM state by ordinary transitions (RMB-14-005).

The writer is the closure path shared by the Leave nodes and the replica
close fan-out.  These tests pin its contract directly: the path it writes,
the no-op at ``RM.CLOSED``, the refusal it reports when a step is not an RM
transition (no override hides it) and the refusal for a status that is not
core-shaped.
"""

import py_trees
import pytest
from py_trees.common import Status

from test.core.behaviors.bt_harness import BTTestScenario
from vultron.core.behaviors.case.nodes.participant import rm_closure
from vultron.core.behaviors.case.nodes.participant.rm_closure import (
    RMClosureWriter,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.dimensions import RmDimension
from vultron.core.models.participant_status import (
    ParticipantStatus,
    participant_status_rm_state,
)
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole
from vultron.errors import VultronValidationError

ACTOR_A = "https://example.test/actors/closure-a"
ACTOR_B = "https://example.test/actors/closure-b"


def _seed_case(
    bt_scenario: BTTestScenario, states: dict[str, RM]
) -> tuple[VulnerabilityCase, dict[str, CaseParticipant]]:
    """Seed a case with one participant per actor, each at its given RM state."""
    case = VulnerabilityCase(name="closure case", attributed_to=ACTOR_A)
    participants: dict[str, CaseParticipant] = {}
    for actor_id, rm_state in states.items():
        participant = CaseParticipant(
            id_=f"{case.id_}/participants/{actor_id.rsplit('/', 1)[-1]}",
            attributed_to=actor_id,
            context=case.id_,
            case_roles=[CVDRole.COORDINATOR],
            participant_statuses=[
                ParticipantStatus(
                    rm=RmDimension(state=rm_state),
                    context=case.id_,
                    attributed_to=actor_id,
                )
            ],
        )
        case.add_participant(participant)
        participants[actor_id] = participant
    bt_scenario.seed(*participants.values(), case)
    return case, participants


def _rm_history(bt_scenario: BTTestScenario, participant_id: str) -> list[RM]:
    stored = bt_scenario.dl.read(participant_id)
    assert isinstance(stored, CaseParticipant)
    return [
        participant_status_rm_state(ps) for ps in stored.participant_statuses
    ]


def _probe() -> py_trees.behaviour.Behaviour:
    return py_trees.behaviours.Success(name="ClosureProbe")


@pytest.mark.spec("RMB-14-005")
@pytest.mark.parametrize(
    ("source", "written"),
    [
        (RM.RECEIVED, [RM.CLOSED]),
        (RM.INVALID, [RM.CLOSED]),
        (RM.ACCEPTED, [RM.CLOSED]),
        (RM.DEFERRED, [RM.CLOSED]),
        (RM.VALID, [RM.DEFERRED, RM.CLOSED]),
        (RM.START, [RM.RECEIVED, RM.CLOSED]),
        (RM.CLOSED, []),
    ],
    ids=lambda v: v.name if isinstance(v, RM) else None,
)
def test_close_writes_the_closure_path(
    bt_scenario: BTTestScenario, source: RM, written: list[RM]
) -> None:
    """One status per step on the path; nothing at all from RM.CLOSED."""
    case, participants = _seed_case(bt_scenario, {ACTOR_A: source})
    participant_id = participants[ACTOR_A].id_
    before = _rm_history(bt_scenario, participant_id)

    status = RMClosureWriter(name="Close").close(
        _probe(), bt_scenario.dl, participant_id, case.id_, actor_id=ACTOR_A
    )

    assert status == Status.SUCCESS
    assert _rm_history(bt_scenario, participant_id) == [*before, *written]


@pytest.mark.spec("RMB-14-005")
def test_one_writer_closes_each_actor_it_is_given(
    bt_scenario: BTTestScenario,
) -> None:
    """One writer closes whichever actor each ``close`` call names."""
    case, participants = _seed_case(
        bt_scenario, {ACTOR_A: RM.VALID, ACTOR_B: RM.RECEIVED}
    )
    writer = RMClosureWriter(name="Close")

    for actor_id in (ACTOR_A, ACTOR_B):
        status = writer.close(
            _probe(),
            bt_scenario.dl,
            participants[actor_id].id_,
            case.id_,
            actor_id=actor_id,
        )
        assert status == Status.SUCCESS, actor_id

    assert _rm_history(bt_scenario, participants[ACTOR_A].id_)[-3:] == [
        RM.VALID,
        RM.DEFERRED,
        RM.CLOSED,
    ]
    assert _rm_history(bt_scenario, participants[ACTOR_B].id_)[-2:] == [
        RM.RECEIVED,
        RM.CLOSED,
    ]


@pytest.mark.spec("RMB-14-005")
@pytest.mark.spec("VP-02-004")
def test_a_step_off_the_rm_table_is_refused_not_forced(
    bt_scenario: BTTestScenario, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The writes keep RM adjacency, so ``V → C`` is refused and reported.

    The path is patched to the forbidden single step to show the writer has
    no override to fall back on: the participant stays at RM.VALID.
    """
    case, participants = _seed_case(bt_scenario, {ACTOR_A: RM.VALID})
    participant_id = participants[ACTOR_A].id_
    before = _rm_history(bt_scenario, participant_id)
    monkeypatch.setattr(rm_closure, "rm_closure_path", lambda _s: (RM.CLOSED,))
    probe = _probe()

    status = RMClosureWriter(name="Close").close(
        probe, bt_scenario.dl, participant_id, case.id_, actor_id=ACTOR_A
    )

    assert status == Status.FAILURE
    assert "VALID -> CLOSED refused" in probe.feedback_message
    assert _rm_history(bt_scenario, participant_id) == before


@pytest.mark.spec("RMB-14-005")
def test_a_failed_step_keeps_the_rungs_written_and_a_retry_resumes(
    bt_scenario: BTTestScenario, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A refused ``D → C`` leaves the actor at DEFERRED; a retry writes only C.

    Each rung is a legal state on its own, so the writer keeps what it wrote
    rather than rolling back, and the next ``close`` continues the path from
    the state the actor reached instead of re-walking it.
    """
    case, participants = _seed_case(bt_scenario, {ACTOR_A: RM.VALID})
    participant_id = participants[ACTOR_A].id_
    before = _rm_history(bt_scenario, participant_id)
    writer = RMClosureWriter(name="Close")
    closed_step = writer._writers[RM.CLOSED]
    probe = _probe()

    with monkeypatch.context() as patch:
        patch.setattr(closed_step, "update", lambda: Status.FAILURE)
        status = writer.close(
            probe, bt_scenario.dl, participant_id, case.id_, actor_id=ACTOR_A
        )

    assert status == Status.FAILURE
    assert "DEFERRED -> CLOSED refused" in probe.feedback_message
    assert _rm_history(bt_scenario, participant_id) == [*before, RM.DEFERRED]

    status = writer.close(
        _probe(), bt_scenario.dl, participant_id, case.id_, actor_id=ACTOR_A
    )

    assert status == Status.SUCCESS
    assert _rm_history(bt_scenario, participant_id) == [
        *before,
        RM.DEFERRED,
        RM.CLOSED,
    ]


@pytest.mark.spec("ARCH-15-001")
def test_unreadable_status_is_reported_as_failure(
    bt_scenario: BTTestScenario, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A status that is not core-shaped fails the closure; nothing is written."""
    case, participants = _seed_case(bt_scenario, {ACTOR_A: RM.ACCEPTED})
    participant_id = participants[ACTOR_A].id_
    before = _rm_history(bt_scenario, participant_id)

    def _raise(*_args: object) -> None:
        raise VultronValidationError("wire-shaped status")

    monkeypatch.setattr(
        rm_closure, "resolve_participant_state_from_dl", _raise
    )
    probe = _probe()

    status = RMClosureWriter(name="Close").close(
        probe, bt_scenario.dl, participant_id, case.id_, actor_id=ACTOR_A
    )

    assert status == Status.FAILURE
    assert "not core-shaped" in probe.feedback_message
    assert _rm_history(bt_scenario, participant_id) == before
