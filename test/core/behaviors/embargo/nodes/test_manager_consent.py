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

"""The CASE_MANAGER's own consent row at the proposal commit (EP-09-002, #4180).

The relay never invites the manager, so a manager that is also a stakeholder
writes its own row when it adjudicates a proposal: ``ACCEPTED`` or
``DECLINED`` by its policy call-out, nothing when it is the proposer (the
proposal already recorded it, ADR-0093), the case owner (EP-09-005), or a bare
container with no stake.
"""

from typing import cast

import py_trees
import pytest
from py_trees.common import Status

from test.core.behaviors.bt_harness import BTTestScenario
from test.support.embargo_register import propose
from vultron.core.behaviors.call_out.bundles.embargo import (
    EmbargoCallOutBundle,
)
from vultron.core.behaviors.embargo.nodes.manager_consent import (
    record_manager_embargo_consent_tree,
)
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

CASE_ID = "https://example.org/cases/manager-consent"
EMBARGO_ID = f"{CASE_ID}/embargo_events/proposed"
MANAGER = "https://example.org/actors/mc-manager"
PROPOSER = "https://example.org/actors/mc-proposer"
OWNER = "https://example.org/actors/mc-owner"


class _Fail(py_trees.behaviour.Behaviour):
    def update(self) -> Status:
        return Status.FAILURE


def _declining_bundle() -> EmbargoCallOutBundle:
    return EmbargoCallOutBundle(
        evaluate_embargo_proposal_factory=lambda name: _Fail(name=name)  # type: ignore[arg-type]
    )


def _seed(
    scenario: BTTestScenario,
    manager_roles: list[CVDRole],
    *,
    owner: str = OWNER,
) -> None:
    records = [
        CaseParticipant(
            id_=f"{CASE_ID}/participants/{actor.rsplit('/', 1)[-1]}",
            attributed_to=actor,
            context=CASE_ID,
            case_roles=roles,
        )
        for actor, roles in (
            (MANAGER, manager_roles),
            (PROPOSER, [CVDRole.VENDOR]),
            (OWNER, [CVDRole.CASE_OWNER]),
        )
    ]
    case = VulnerabilityCase(
        id_=CASE_ID,
        name="Manager consent",
        attributed_to=owner,
        case_participants=[p.id_ for p in records],
        actor_participant_index={
            cast(str, p.attributed_to): p.id_ for p in records
        },
    )
    propose(case, EMBARGO_ID)
    for record in records:
        # The row the proposal wrote for every participant (ADR-0122).
        record.write_uninvited_rows([EMBARGO_ID])
    embargo = as_EmbargoEvent(
        id_=EMBARGO_ID, context=CASE_ID, end_time=days_from_now_utc(30)
    )
    scenario.seed(*records, case, embargo)


def _managers_row(scenario: BTTestScenario) -> EmbargoConsentState:
    case = cast(VulnerabilityCase, scenario.dl.read(CASE_ID))
    participant = scenario.dl.read(case.actor_participant_index[MANAGER])
    assert isinstance(participant, CaseParticipant)
    return participant.consent_for(EMBARGO_ID)


def _run(
    scenario: BTTestScenario,
    proposer_id: str = PROPOSER,
    call_out: EmbargoCallOutBundle | None = None,
):
    kwargs = {"call_out": call_out} if call_out is not None else {}
    return scenario.run(
        record_manager_embargo_consent_tree(
            case_id=CASE_ID,
            embargo_id=EMBARGO_ID,
            proposer_id=proposer_id,
            **kwargs,
        )
    )


@pytest.mark.executes_as(MANAGER)
@pytest.mark.spec("EP-09-002")
class TestManagerConsentAtCommit:
    def test_a_stakeholder_manager_accepts_by_default_policy(
        self, bt_scenario: BTTestScenario
    ) -> None:
        _seed(bt_scenario, [CVDRole.CASE_MANAGER, CVDRole.VENDOR])
        assert _run(bt_scenario).status == Status.SUCCESS
        assert _managers_row(bt_scenario) == EmbargoConsentState.AGREED

    def test_a_coordinator_manager_with_a_stake_is_covered(
        self, bt_scenario: BTTestScenario
    ) -> None:
        _seed(
            bt_scenario,
            [CVDRole.CASE_MANAGER, CVDRole.COORDINATOR, CVDRole.DEPLOYER],
        )
        assert _run(bt_scenario).status == Status.SUCCESS
        assert _managers_row(bt_scenario) == EmbargoConsentState.AGREED

    def test_a_declining_policy_records_declined(
        self, bt_scenario: BTTestScenario
    ) -> None:
        _seed(bt_scenario, [CVDRole.CASE_MANAGER, CVDRole.VENDOR])
        result = _run(bt_scenario, call_out=_declining_bundle())
        assert result.status == Status.SUCCESS
        assert _managers_row(bt_scenario) == EmbargoConsentState.DECLINED

    def test_a_bare_container_manager_writes_nothing(
        self, bt_scenario: BTTestScenario
    ) -> None:
        _seed(bt_scenario, [CVDRole.CASE_MANAGER, CVDRole.COORDINATOR])
        assert _run(bt_scenario).status == Status.SUCCESS
        assert _managers_row(bt_scenario) == EmbargoConsentState.UNINVITED

    def test_the_owner_manager_is_left_to_its_owner_decision(
        self, bt_scenario: BTTestScenario
    ) -> None:
        _seed(
            bt_scenario,
            [CVDRole.CASE_MANAGER, CVDRole.VENDOR],
            owner=MANAGER,
        )
        assert _run(bt_scenario).status == Status.SUCCESS
        assert _managers_row(bt_scenario) == EmbargoConsentState.UNINVITED

    def test_the_proposer_manager_is_not_written_here(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """Its AGREE comes from the proposal (ADR-0093); this leaf adds none."""
        _seed(bt_scenario, [CVDRole.CASE_MANAGER, CVDRole.VENDOR])
        result = _run(
            bt_scenario, proposer_id=MANAGER, call_out=_declining_bundle()
        )
        assert result.status == Status.SUCCESS
        assert _managers_row(bt_scenario) == EmbargoConsentState.UNINVITED

    def test_an_existing_row_is_left_alone(
        self, bt_scenario: BTTestScenario
    ) -> None:
        _seed(bt_scenario, [CVDRole.CASE_MANAGER, CVDRole.VENDOR])
        assert _run(bt_scenario).status == Status.SUCCESS
        # A redelivered proposal: the policy now says no, the row stays.
        result = _run(bt_scenario, call_out=_declining_bundle())
        assert result.status == Status.SUCCESS
        assert _managers_row(bt_scenario) == EmbargoConsentState.AGREED
