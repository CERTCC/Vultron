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

"""Each state axis writes its own record (SM-10-003, SM-10-004).

A participant-specific transition (RM, VF, D) is recorded on the
participant's ``ParticipantStatus`` and never on the shared ``CaseStatus``
(SM-10-003).  A participant-agnostic transition (EM, PXA) is recorded on the
shared ``CaseStatus`` and never on a participant's own progress; the
``case_status`` a participant embeds in its ``ParticipantStatus`` is only its
claim, which the CASE_MANAGER's snapshot decides whether to promote
(SM-10-004).
"""

import typing

import pytest
from pydantic import BaseModel, ValidationError

from test.core.behaviors.bt_harness import BTTestScenario
from test.support.objects import make, with_times
from vultron.core.behaviors.case.nodes.participant.status import (
    CreateParticipantStatusNode,
)
from vultron.core.behaviors.case_status_snapshot import (
    EmitCaseStatusUpdateNode,
)
from vultron.core.models.actor import VultronService
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.dimensions import (
    DDimension,
    EmDimension,
    PxaDimension,
    RmDimension,
    VfDimension,
)
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.report import VulnerabilityReport
from vultron.core.states.cs import CS_d, CS_pxa, CS_vf
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole

CASE_ID = "https://example.org/cases/case-axis"
PARTICIPANT_ID = "https://example.org/participants/vendor-cp-axis"

_PARTICIPANT_AXES = (RmDimension, VfDimension, DDimension)
_CASE_AXES = (EmDimension, PxaDimension)


def _dimension_types(annotation: object) -> set[type]:
    """Every dimension class reachable inside *annotation*, at any depth.

    Walks unions, ``Annotated``, ``list[...]`` and other generic arguments,
    and counts a subclass of a dimension as that dimension.
    """
    found: set[type] = set()
    if isinstance(annotation, type):
        found.update(
            axis
            for axis in (*_PARTICIPANT_AXES, *_CASE_AXES)
            if issubclass(annotation, axis)
        )
    for arg in typing.get_args(annotation):
        found |= _dimension_types(arg)
    return found


def _field_types(model: type[BaseModel]) -> set[type]:
    """The dimension classes any field of *model* can hold."""
    found: set[type] = set()
    for info in model.model_fields.values():
        found |= _dimension_types(info.annotation)
        for meta in info.metadata:
            found |= _dimension_types(meta)
    return found


@pytest.fixture
def case_with_participant(
    bt_scenario: BTTestScenario,
    actor: VultronService,
    report: VulnerabilityReport,
) -> VulnerabilityCase:
    """A case whose one participant (the actor, a vendor and deployer) is in
    RM.VALID."""
    participant = make(
        CaseParticipant,
        id_=PARTICIPANT_ID,
        attributed_to=actor.id_,
        context=CASE_ID,
        case_roles=[CVDRole.VENDOR, CVDRole.DEPLOYER],
        participant_statuses=[
            make(
                ParticipantStatus,
                attributed_to=actor.id_,
                context=CASE_ID,
                rm=RmDimension(state=RM.RECEIVED),
            ),
            make(
                ParticipantStatus,
                attributed_to=actor.id_,
                context=CASE_ID,
                rm=RmDimension(state=RM.VALID),
            ),
        ],
    )
    case = make(
        VulnerabilityCase,
        id_=CASE_ID,
        name="Axis Scoping Case",
        vulnerability_reports=[report.id_],
        case_participants=[participant.id_],
        actor_participant_index={actor.id_: participant.id_},
        attributed_to=actor.id_,
    )
    bt_scenario.seed(participant, case)
    return case


def _case(bt_scenario: BTTestScenario) -> VulnerabilityCase:
    case = bt_scenario.dl.read(CASE_ID)
    assert isinstance(case, VulnerabilityCase)
    return case


def _statuses(bt_scenario: BTTestScenario) -> list[ParticipantStatus]:
    participant = bt_scenario.dl.read(PARTICIPANT_ID)
    assert isinstance(participant, CaseParticipant)
    return participant.participant_statuses


def _write_status(
    bt_scenario: BTTestScenario,
    actor: VultronService,
    *,
    rm_state: RM | None = None,
    vf_state: CS_vf | None = None,
    d_state: CS_d | None = None,
    pxa_state: CS_pxa | None = None,
) -> None:
    """Run ``CreateParticipantStatusNode`` for *actor* on the test case."""
    bt_scenario.assert_success(
        bt_scenario.run(
            CreateParticipantStatusNode(
                actor_id=actor.id_,
                rm_state=rm_state,
                vf_state=vf_state,
                d_state=d_state,
                pxa_state=pxa_state,
            ),
            actor_id=actor.id_,
            case_id=CASE_ID,
        )
    )


def _case_status_ids(case: VulnerabilityCase) -> list[str]:
    return [
        status.id_ if isinstance(status, CaseStatus) else status
        for status in case.case_statuses
    ]


class TestParticipantAxesNeverWriteCaseStatus:
    """SM-10-003: an RM or VFD transition never writes the shared CaseStatus."""

    @pytest.mark.spec("SM-10-003")
    def test_case_status_has_no_participant_axis(self) -> None:
        """``CaseStatus`` holds EM and PXA only, and refuses an RM, VF or D
        value, so no write can put participant progress on it."""
        assert _field_types(CaseStatus) == set(_CASE_AXES)
        for key, value in (
            ("rmState", "ACCEPTED"),
            ("vfState", "Vf"),
            ("dState", "D"),
        ):
            # Positive control: the value is valid on its owning model, so
            # the refusal below comes from the missing field.
            ParticipantStatus.model_validate(
                with_times(
                    ParticipantStatus,
                    {"context": CASE_ID, "cvdRole": ["VENDOR"], key: value},
                )
            )
            with pytest.raises(ValidationError):
                CaseStatus.model_validate(
                    with_times(CaseStatus, {"context": CASE_ID, key: value})
                )

    @pytest.mark.spec("SM-10-003")
    @pytest.mark.parametrize(
        ("rm_state", "vf_state", "d_state", "attr", "expected"),
        [
            pytest.param(RM.ACCEPTED, None, None, "rm", RM.ACCEPTED, id="rm"),
            pytest.param(None, CS_vf.Vf, None, "vf", CS_vf.Vf, id="vf"),
            # D needs RM.ACCEPTED first (cross-machine entailment).
            pytest.param(RM.ACCEPTED, None, CS_d.D, "d", CS_d.D, id="d"),
        ],
    )
    def test_participant_axis_transition_leaves_case_status_unchanged(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronService,
        case_with_participant: VulnerabilityCase,
        rm_state: RM | None,
        vf_state: CS_vf | None,
        d_state: CS_d | None,
        attr: str,
        expected: RM | CS_vf | CS_d,
    ) -> None:
        """An RM, VF or D move lands on the participant's ParticipantStatus,
        and the case's CaseStatus history is left as it was."""
        before = _case(bt_scenario)
        before_ids = _case_status_ids(before)
        before_current = before.current_status
        before_count = len(_statuses(bt_scenario))

        _write_status(
            bt_scenario,
            actor,
            rm_state=rm_state,
            vf_state=vf_state,
            d_state=d_state,
        )

        statuses = _statuses(bt_scenario)
        assert len(statuses) == before_count + 1
        assert getattr(statuses[-1], attr).state == expected
        after = _case(bt_scenario)
        assert _case_status_ids(after) == before_ids
        assert after.current_status.em.state == before_current.em.state
        assert after.current_status.pxa.state == before_current.pxa.state


class TestCaseAxesNeverWriteParticipantProgress:
    """SM-10-004: an EM or PXA transition writes the shared CaseStatus, never
    a participant's own progress; a participant's embedded view is a claim."""

    @pytest.mark.spec("SM-10-004")
    def test_participant_status_has_no_case_axis_of_its_own(self) -> None:
        """``ParticipantStatus`` holds RM, VF and D; EM and PXA appear only
        inside its embedded ``case_status`` claim, and a top-level EM or
        PXA value is refused."""
        assert _field_types(ParticipantStatus) == set(_PARTICIPANT_AXES)
        for key, value in (("emState", "ACTIVE"), ("pxaState", "PXA")):
            with pytest.raises(ValidationError):
                ParticipantStatus.model_validate(
                    with_times(
                        ParticipantStatus, {"context": CASE_ID, key: value}
                    )
                )

    @pytest.mark.spec("SM-10-004")
    def test_case_status_snapshot_leaves_participant_progress_unchanged(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronService,
        case_with_participant: VulnerabilityCase,
    ) -> None:
        """The CASE_MANAGER's PXA snapshot, adopting the participant's latest
        status as its report, writes a new CaseStatus and leaves that
        participant's ParticipantStatus history, the report included, as it
        was."""
        participant = bt_scenario.dl.read(PARTICIPANT_ID)
        assert isinstance(participant, CaseParticipant)
        report = make(
            ParticipantStatus,
            attributed_to=actor.id_,
            context=CASE_ID,
            rm=RmDimension(state=RM.VALID),
            case_status=make(
                CaseStatus, context=CASE_ID, pxa=PxaDimension(state=CS_pxa.Pxa)
            ),
        )
        participant.add_participant_status(report)
        bt_scenario.dl.save(participant)
        bt_scenario.seed(report)
        before = _case(bt_scenario)
        before_case_count = len(before.case_statuses)
        before_statuses = [s.model_dump() for s in _statuses(bt_scenario)]
        assert before_statuses[-1]["id_"] == report.id_

        bt_scenario.assert_success(
            bt_scenario.run(
                EmitCaseStatusUpdateNode(
                    case_id=CASE_ID, reported_status_id=report.id_
                ),
                actor_id=actor.id_,
            )
        )

        after = _case(bt_scenario)
        assert len(after.case_statuses) == before_case_count + 1
        assert after.current_status.pxa.state == CS_pxa.Pxa
        assert [
            s.model_dump() for s in _statuses(bt_scenario)
        ] == before_statuses

    @pytest.mark.spec("SM-10-004")
    def test_participant_view_of_case_state_is_only_a_claim(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronService,
        case_with_participant: VulnerabilityCase,
    ) -> None:
        """A participant reporting public awareness records it in its own
        ``case_status``; the case's CaseStatus is not changed until the
        CASE_MANAGER promotes it."""
        before = _case(bt_scenario)
        before_ids = _case_status_ids(before)
        assert before.current_status.pxa.state == CS_pxa.pxa

        _write_status(bt_scenario, actor, pxa_state=CS_pxa.Pxa)

        claim = _statuses(bt_scenario)[-1].case_status
        assert claim is not None
        assert claim.pxa.state == CS_pxa.Pxa
        after = _case(bt_scenario)
        assert _case_status_ids(after) == before_ids
        assert after.current_status.pxa.state == CS_pxa.pxa
