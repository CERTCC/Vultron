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

"""
Unit tests for InitializeDefaultEmbargoNode.

Per specs/case-management.yaml CM-02, OX-03-001, CM-14-003.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, cast

import pytest
from py_trees.common import Status

from vultron.core.behaviors.case.embargo_tree import (
    InitializeDefaultEmbargoNode,
)
from vultron.core.behaviors.case.nodes.embargo import (
    AdvanceEMStateToActiveNode,
    AttachEmbargoToCaseNode,
    CreateEmbargoEventNode,
    ResolveEmbargoDurationNode,
    SeedOwnerAsSignatoryNode,
)
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.behaviors.case.nodes.participant import (
    CreateCaseOwnerParticipant,
)
from vultron.core.models.vultron_types import (
    VultronCase,
    VultronCaseActor,
    VultronReport,
)
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC
from test.core.behaviors.bt_harness import BTTestScenario

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def actor_id() -> str:
    return "https://example.org/actors/vendor"


@pytest.fixture
def actor(bt_scenario: BTTestScenario, actor_id: str) -> VultronCaseActor:
    obj = VultronCaseActor(id_=actor_id, name="Vendor Co")
    bt_scenario.dl.create(obj)
    return obj


@pytest.fixture
def report(bt_scenario: BTTestScenario) -> VultronReport:
    obj = VultronReport(name="TEST-001", content="Test vulnerability report")
    bt_scenario.dl.create(obj)
    return obj


@pytest.fixture
def case_obj(
    bt_scenario: BTTestScenario, actor_id: str, report: VultronReport
) -> VultronCase:
    case = VultronCase(
        id_="https://example.org/cases/case-001",
        name="Test Case",
        attributed_to=actor_id,
        vulnerability_reports=[report.id_],
    )
    bt_scenario.dl.create(case)
    return case


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestInitializeDefaultEmbargoNode:
    """InitializeDefaultEmbargoNode creates and attaches a default embargo."""

    def test_succeeds_and_sets_active_embargo(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        actor_id: str,
        case_obj: VultronCase,
    ) -> None:
        result = bt_scenario.run(
            InitializeDefaultEmbargoNode(),
            actor_id=actor_id,
            case_id=case_obj.id_,
        )
        assert result.status == Status.SUCCESS

        stored_case = cast(Any, bt_scenario.dl.read(case_obj.id_))
        assert stored_case.active_embargo is not None

    def test_em_state_advances_to_active(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        actor_id: str,
        case_obj: VultronCase,
    ) -> None:
        """After initialization, case EM state should be ACTIVE (propose+accept)."""
        bt_scenario.run(
            InitializeDefaultEmbargoNode(),
            actor_id=actor_id,
            case_id=case_obj.id_,
        )

        stored_case = cast(Any, bt_scenario.dl.read(case_obj.id_))
        assert stored_case.current_status.em_state == EM.ACTIVE

    def test_fails_without_case_id(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        actor_id: str,
    ) -> None:
        result = bt_scenario.run(
            InitializeDefaultEmbargoNode(),
            actor_id=actor_id,
            # No case_id
        )
        assert result.status == Status.FAILURE

    def test_idempotent_active_embargo_not_overwritten(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        actor_id: str,
        case_obj: VultronCase,
    ) -> None:
        """Running twice does not replace an already-active embargo."""
        bt_scenario.run(
            InitializeDefaultEmbargoNode(),
            actor_id=actor_id,
            case_id=case_obj.id_,
        )
        stored_case = cast(Any, bt_scenario.dl.read(case_obj.id_))
        first_embargo_id = (
            stored_case.active_embargo
            if isinstance(stored_case.active_embargo, str)
            else getattr(stored_case.active_embargo, "id_", None)
        )

        bt_scenario.run(
            InitializeDefaultEmbargoNode(),
            actor_id=actor_id,
            case_id=case_obj.id_,
        )
        stored_case2 = cast(Any, bt_scenario.dl.read(case_obj.id_))
        second_embargo_id = (
            stored_case2.active_embargo
            if isinstance(stored_case2.active_embargo, str)
            else getattr(stored_case2.active_embargo, "id_", None)
        )
        assert first_embargo_id == second_embargo_id

    def test_seeds_owner_as_signatory(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        actor_id: str,
        case_obj: VultronCase,
    ) -> None:
        """Owner participant is seeded as PEC.SIGNATORY (CM-14-003)."""
        # First create an owner participant
        bt_scenario.run(
            CreateCaseOwnerParticipant(),
            actor_id=actor_id,
            case_id=case_obj.id_,
        )

        bt_scenario.run(
            InitializeDefaultEmbargoNode(),
            actor_id=actor_id,
            case_id=case_obj.id_,
        )

        stored_case = cast(Any, bt_scenario.dl.read(case_obj.id_))
        participant_id = stored_case.actor_participant_index.get(actor_id)
        assert participant_id is not None

        participant = cast(Any, bt_scenario.dl.read(participant_id))
        assert participant is not None
        assert participant.embargo_consent_state == PEC.SIGNATORY

    def test_is_composed_subtree_of_named_leaf_nodes(self) -> None:
        node = InitializeDefaultEmbargoNode()

        assert [type(child) for child in node.children] == [
            ResolveEmbargoDurationNode,
            CreateEmbargoEventNode,
            AdvanceEMStateToActiveNode,
            AttachEmbargoToCaseNode,
            SeedOwnerAsSignatoryNode,
        ]

    def test_advance_em_state_delegates_to_embargo_lifecycle(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        actor_id: str,
        case_obj: VultronCase,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        calls: list[tuple[str, str, str, str]] = []
        embargo = EmbargoEvent(
            end_time=datetime.now(tz=timezone.utc) + timedelta(days=1),
            context=case_obj.id_,
        )
        bt_scenario.dl.create(embargo)

        bt_scenario.run(
            CreateCaseOwnerParticipant(),
            actor_id=actor_id,
            case_id=case_obj.id_,
        )

        class FakeEmbargoLifecycle:
            def __init__(self, persistence: Any) -> None:
                self.persistence = persistence

            def propose_embargo(self, **kwargs: Any) -> Any:
                calls.append(
                    (
                        "propose",
                        kwargs["case_id"],
                        kwargs["embargo_id"],
                        kwargs["transition_mode"].value,
                    )
                )
                return object()

            def accept_embargo_invite(self, **kwargs: Any) -> Any:
                calls.append(
                    (
                        "accept",
                        kwargs["case_id"],
                        kwargs["embargo_id"],
                        kwargs["transition_mode"].value,
                    )
                )
                stored_case = cast(
                    Any, self.persistence.read(kwargs["case_id"])
                )
                stored_case.active_embargo = kwargs["embargo_id"]
                stored_case.current_status.em_state = EM.ACTIVE
                self.persistence.save(stored_case)
                return object()

        monkeypatch.setattr(
            "vultron.core.behaviors.case.nodes.embargo.EmbargoLifecycle",
            FakeEmbargoLifecycle,
        )

        result = bt_scenario.run(
            AdvanceEMStateToActiveNode(),
            actor_id=actor_id,
            case_id=case_obj.id_,
            default_embargo_id=embargo.id_,
        )

        assert result.status == Status.SUCCESS
        assert calls == [
            ("propose", case_obj.id_, embargo.id_, "STRICT"),
        ]
