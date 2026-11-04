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

"""The guard that refuses a status fixture in a CSB-18-001-impossible state.

Five tests in this package once paired ``rm=VALID`` or ``rm=RECEIVED`` with
``vf=VF`` — a combination CSB-18-001 says cannot exist, chosen because it was
convenient.  Adding the receive-path entailment check broke all five, so a real
enforcement improvement read as a regression (#2906).  These tests pin the
guard that stops that recurring (#3046): the autouse fixture in this package's
``conftest.py``, and the check inside the shared ``current_status`` fixture
builder.

The guard is keyed on ``composite_state_violations`` — the one evaluator all
three protocol paths share (RSH-09-004, RSH-09-012) — and on the DataLayer
write, not on any fixture builder's name, so renaming or hand-rolling a builder
cannot slip past it.
"""

from typing import cast

import pytest

from test.support.participant_status import (
    assert_possible_participant_status,
    impossible_state_reasons,
)
from test.support.rm_declaration import (
    ACTOR_ID,
    CASE_ID,
    CASE_MANAGER_ID,
    PARTICIPANT_ID,
    current_status,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.dimensions import (
    DDimension,
    RmDimension,
    VfDimension,
)
from vultron.core.states.cs import CS_d, CS_pxa, CS_vf
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.case_status import as_ParticipantStatus

#: The pairs the five #2906 casualties used, plus the two other rules
#: ``composite_state_violations`` composes.  Each is named by the rule it
#: breaks so a failure says which entailment the fixture ignored.
IMPOSSIBLE_PAIRS = [
    pytest.param(RM.RECEIVED, CS_vf.VF, None, "RM↔VF", id="received-and-VF"),
    pytest.param(RM.VALID, CS_vf.VF, None, "RM↔VF", id="valid-and-VF"),
    pytest.param(RM.START, CS_vf.VF, None, "RM↔VF", id="start-and-VF"),
    pytest.param(RM.INVALID, CS_vf.VF, None, "RM↔VF", id="invalid-and-VF"),
    pytest.param(RM.VALID, None, CS_d.D, "RM↔D", id="valid-and-D"),
    pytest.param(RM.ACCEPTED, CS_vf.Vf, CS_d.D, "VF↔D", id="Vf-and-D"),
]

#: Pairs CSB-18-001 permits, so the guard is shown to admit as well as refuse.
POSSIBLE_PAIRS = [
    pytest.param(RM.ACCEPTED, CS_vf.VF, CS_d.D, id="accepted-VF-and-D"),
    pytest.param(RM.DEFERRED, CS_vf.VF, None, id="deferred-and-VF"),
    pytest.param(RM.CLOSED, CS_vf.VF, CS_d.D, id="closed-VF-and-D"),
    pytest.param(RM.RECEIVED, CS_vf.Vf, None, id="received-and-Vf"),
    pytest.param(RM.VALID, None, None, id="valid-with-no-vendor-path"),
    pytest.param(RM.RECEIVED, None, CS_d.d, id="received-and-not-deployed"),
]


def _status(
    rm: RM, vf: CS_vf | None, d: CS_d | None, status_id: str
) -> as_ParticipantStatus:
    return as_ParticipantStatus(
        id_=status_id,
        context=CASE_ID,
        rm=RmDimension(state=rm),
        vf=VfDimension(state=vf) if vf is not None else None,
        d=DDimension(state=d) if d is not None else None,
    )


def _participant(status: as_ParticipantStatus) -> as_CaseParticipant:
    participant = as_CaseParticipant(
        id_=PARTICIPANT_ID,
        context=CASE_ID,
        attributed_to=ACTOR_ID,
        case_roles=[CVDRole.VENDOR, CVDRole.DEPLOYER],
    )
    participant.participant_statuses.append(status)
    return participant


class TestImpossibleStateReasons:
    """``impossible_state_reasons`` reports every rule a pair breaks."""

    @pytest.mark.spec("CSB-18-001")
    @pytest.mark.spec("CSB-17-001")
    @pytest.mark.parametrize(("rm", "vf", "d", "rule"), IMPOSSIBLE_PAIRS)
    def test_an_impossible_pair_is_reported(self, rm, vf, d, rule):
        reasons = impossible_state_reasons(
            _status(rm, vf, d, f"{PARTICIPANT_ID}/statuses/probe")
        )

        assert reasons, f"{rule} must refuse rm={rm.name} vf={vf} d={d}"
        assert any("entailment violated" in reason for reason in reasons)

    @pytest.mark.spec("CSB-18-001")
    @pytest.mark.parametrize(("rm", "vf", "d"), POSSIBLE_PAIRS)
    def test_a_permitted_pair_is_not_reported(self, rm, vf, d):
        assert (
            impossible_state_reasons(
                _status(rm, vf, d, f"{PARTICIPANT_ID}/statuses/probe")
            )
            == []
        )

    @pytest.mark.spec("CSB-18-001")
    def test_the_assertion_names_the_fixture_and_the_rule(self):
        """The message points at the fixture, not at the guard (#3046)."""
        status = _status(
            RM.VALID, CS_vf.VF, None, f"{PARTICIPANT_ID}/statuses/probe"
        )

        with pytest.raises(AssertionError) as caught:
            assert_possible_participant_status(status, "a_fixture_builder()")

        message = str(caught.value)
        assert "a_fixture_builder()" in message
        assert "#3046" in message
        assert "RM='VALID'" in message


class TestTheGuardIsLiveInThisPackage:
    """Storing an impossible participant state fails the test that does it.

    The autouse fixture wraps the DataLayer write methods, so the check runs
    while the test is running and the failure names the test that seeded the
    state.  A teardown scan could not: the store a test opens is closed by the
    fixture that opened it.
    """

    @pytest.mark.spec("CSB-18-001")
    def test_a_participant_written_directly_is_refused(self, store_for):
        dl = store_for(CASE_MANAGER_ID)
        participant = _participant(
            _status(RM.VALID, CS_vf.VF, None, f"{PARTICIPANT_ID}/statuses/bad")
        )

        with pytest.raises(AssertionError, match="#3046"):
            dl.create(participant)

    @pytest.mark.spec("CSB-18-001")
    def test_a_participant_inline_on_a_case_is_refused(self, store_for):
        """A case can carry a participant inline, and ``_dehydrate_data`` keeps it.

        ``add_participant`` appends the id, but ``case_participants`` is
        ``list[NonEmptyString | CaseParticipant]``: an announced case copy
        arrives with its roster embedded, and that snapshot reaches the store.
        """
        dl = store_for(CASE_MANAGER_ID)
        participant = _participant(
            _status(
                RM.RECEIVED, None, CS_d.D, f"{PARTICIPANT_ID}/statuses/bad"
            )
        )
        case = VulnerabilityCase(
            id_=CASE_ID,
            name="Guard case",
            attributed_to=CASE_MANAGER_ID,
            case_participants=[cast(CaseParticipant, participant)],
        )

        with pytest.raises(AssertionError, match="#3046"):
            dl.create(case)

    @pytest.mark.spec("CSB-18-001")
    def test_a_possible_participant_is_written(self, store_for):
        """The guard admits as well as refuses, so it is not a blanket veto."""
        dl = store_for(CASE_MANAGER_ID)
        participant = _participant(
            _status(
                RM.ACCEPTED,
                CS_vf.VF,
                CS_d.D,
                f"{PARTICIPANT_ID}/statuses/good",
            )
        )

        dl.create(participant)

        assert dl.read(PARTICIPANT_ID) is not None


class TestTheSharedFixtureBuilderRefusesAnImpossiblePair:
    """``current_status`` stands for already-recorded state, so it must be possible."""

    @pytest.mark.spec("CSB-18-001")
    def test_a_pre_acceptance_rm_with_the_f_bit_is_refused(self):
        with pytest.raises(AssertionError, match="current_status"):
            current_status(RM.VALID, CS_vf.VF, CS_pxa.pxa)

    @pytest.mark.spec("CSB-18-001")
    def test_an_accepted_rm_with_the_f_bit_is_built(self):
        status = current_status(RM.ACCEPTED, CS_vf.VF, CS_pxa.pxa)

        assert status.vf is not None
        assert status.vf.state is CS_vf.VF
