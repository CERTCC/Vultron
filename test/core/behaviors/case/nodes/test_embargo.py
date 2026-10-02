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

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from py_trees.common import Status

from test.conftest import seed_case_owner_participant
from test.core.behaviors.bt_harness import BTTestScenario
from vultron.core.behaviors.case.embargo_tree import (
    InitializeDefaultEmbargoNode,
)
from vultron.core.behaviors.case.nodes.embargo import (
    AdvanceEMStateToActiveNode,
    AttachEmbargoToCaseNode,
    CreateEmbargoEventNode,
    SeedOwnerAsSignatoryNode,
)
from vultron.core.behaviors.case.nodes.embargo_resolution import (
    CaseEmbargoAlreadyInitializedNode,
    CaseNotEmbargoEligibleNode,
    ResolveEmbargoDurationNode,
)
from vultron.core.behaviors.case.nodes.embargo_revision import (
    RegisterLongerProposalAsRevisionNode,
)
from vultron.core.behaviors.case.participant_tree import (
    CreateCaseOwnerParticipant,
)
from vultron.core.models.actor import VultronOrganization
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_actor import CaseActor
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.embargo_policy import EmbargoPolicy
from vultron.core.models.report import VulnerabilityReport
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC

# ---------------------------------------------------------------------------
# Fixtures


def _profile(
    actor_id: str, policy_duration: timedelta | None = None
) -> VultronOrganization:
    """The CASE_OWNER's inline profile, as the Create carried it (CP-01-010)."""
    if policy_duration is None:
        return VultronOrganization(id_=actor_id)
    return VultronOrganization(
        id_=actor_id,
        embargo_policy=EmbargoPolicy(
            actor_id=actor_id,
            inbox=f"{actor_id}/inbox",
            preferred_duration=policy_duration,
        ),
    )


# ---------------------------------------------------------------------------


@pytest.fixture
def actor_id() -> str:
    return "https://example.org/actors/vendor"


@pytest.fixture
def actor(bt_scenario: BTTestScenario, actor_id: str) -> CaseActor:
    obj = CaseActor(id_=actor_id, name="Vendor Co")
    bt_scenario.dl.create(obj)
    return obj


@pytest.fixture
def report(bt_scenario: BTTestScenario) -> VulnerabilityReport:
    obj = VulnerabilityReport(
        name="TEST-001", content="Test vulnerability report"
    )
    bt_scenario.dl.create(obj)
    return obj


@pytest.fixture
def case_obj(
    bt_scenario: BTTestScenario, actor_id: str, report: VulnerabilityReport
) -> VulnerabilityCase:
    """A case whose owner participant exists, as CM-14-002 requires."""
    case = VulnerabilityCase(
        id_="https://example.org/cases/case-001",
        name="Test Case",
        attributed_to=actor_id,
        vulnerability_reports=[report.id_],
    )
    seed_case_owner_participant(bt_scenario.dl, case)
    bt_scenario.dl.create(case)
    return case


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.spec("CP-09-003")
class TestInitializeDefaultEmbargoNode:
    """InitializeDefaultEmbargoNode creates and attaches a default embargo."""

    def test_succeeds_and_sets_active_embargo(
        self,
        bt_scenario: BTTestScenario,
        actor: CaseActor,
        actor_id: str,
        case_obj: VulnerabilityCase,
    ) -> None:
        result = bt_scenario.run(
            InitializeDefaultEmbargoNode(),
            actor_id=actor_id,
            owner_profile=_profile(actor_id),
            case_id=case_obj.id_,
        )
        assert result.status == Status.SUCCESS

        stored_case = cast(Any, bt_scenario.dl.read(case_obj.id_))
        assert stored_case.active_embargo is not None

    def test_em_state_advances_to_active(
        self,
        bt_scenario: BTTestScenario,
        actor: CaseActor,
        actor_id: str,
        case_obj: VulnerabilityCase,
    ) -> None:
        """After initialization, case EM state should be ACTIVE (propose+accept)."""
        bt_scenario.run(
            InitializeDefaultEmbargoNode(),
            actor_id=actor_id,
            owner_profile=_profile(actor_id),
            case_id=case_obj.id_,
        )

        stored_case = cast(Any, bt_scenario.dl.read(case_obj.id_))
        assert stored_case.current_status.em.state == EM.ACTIVE

    def test_fails_without_case_id(
        self,
        bt_scenario: BTTestScenario,
        actor: CaseActor,
        actor_id: str,
    ) -> None:
        result = bt_scenario.run(
            InitializeDefaultEmbargoNode(),
            actor_id=actor_id,
            owner_profile=_profile(actor_id),
            # No case_id
        )
        assert result.status == Status.FAILURE

    def test_idempotent_active_embargo_not_overwritten(
        self,
        bt_scenario: BTTestScenario,
        actor: CaseActor,
        actor_id: str,
        case_obj: VulnerabilityCase,
    ) -> None:
        """Running twice does not replace an already-active embargo."""
        bt_scenario.run(
            InitializeDefaultEmbargoNode(),
            actor_id=actor_id,
            owner_profile=_profile(actor_id),
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
            owner_profile=_profile(actor_id),
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
        actor: CaseActor,
        actor_id: str,
        case_obj: VulnerabilityCase,
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
            owner_profile=_profile(actor_id),
            case_id=case_obj.id_,
        )

        stored_case = cast(Any, bt_scenario.dl.read(case_obj.id_))
        participant_id = stored_case.actor_participant_index.get(actor_id)
        assert participant_id is not None

        participant = cast(Any, bt_scenario.dl.read(participant_id))
        assert participant is not None
        assert participant.embargo_consent_state == PEC.SIGNATORY

    def test_a_second_run_creates_no_orphan_embargo_event(
        self,
        bt_scenario: BTTestScenario,
        actor: CaseActor,
        actor_id: str,
        case_obj: VulnerabilityCase,
    ) -> None:
        """Default path, run twice: exactly one ``EmbargoEvent`` is stored.

        Before the idempotency arm the creation arm re-ran on the initialized
        case, minting a second event that nothing attached — an orphan left
        by every repeated proposal for the same report.
        """
        for _ in range(2):
            result = bt_scenario.run(
                InitializeDefaultEmbargoNode(),
                actor_id=actor_id,
                owner_profile=_profile(actor_id),
                case_id=case_obj.id_,
            )
            assert result.status == Status.SUCCESS

        events = list(bt_scenario.dl.list_objects("EmbargoEvent"))
        assert len(events) == 1

    @pytest.mark.spec("EP-04-003")
    def test_a_second_run_registers_no_second_revision(
        self,
        bt_scenario: BTTestScenario,
        actor: CaseActor,
        actor_id: str,
        case_obj: VulnerabilityCase,
    ) -> None:
        """Contested path, run twice: one revision, and EM stays REVISE.

        The demo that first exercised the negotiated path (#3393) delivered
        its report Offer twice and found two pending revisions on the case —
        one per ``Create(CaseProposal)`` — because the creation arm ran again
        on the case it had already initialized.
        """
        from datetime import timedelta

        from vultron.core.models._helpers import days_from_now_utc

        proposal = EmbargoEvent(
            context="https://example.org/reports/r-1",
            end_time=days_from_now_utc(10),
        )
        for _ in range(2):
            result = bt_scenario.run(
                InitializeDefaultEmbargoNode(),
                actor_id=actor_id,
                case_id=case_obj.id_,
                sender_proposed_embargo_duration=timedelta(days=10),
                sender_proposed_embargo=proposal,
                owner_profile=_profile(actor_id, timedelta(days=30)),
            )
            assert result.status == Status.SUCCESS

        stored_case = cast(Any, bt_scenario.dl.read(case_obj.id_))
        assert stored_case.current_status.em.state == EM.REVISE
        assert len(stored_case.proposed_embargoes) == 1
        assert stored_case.active_embargo_id == proposal.id_
        # The Reporter's event plus the one registered revision, nothing else.
        events = list(bt_scenario.dl.list_objects("EmbargoEvent"))
        assert len(events) == 2

    def test_already_initialized_guard_raises_on_a_missing_case(
        self, bt_scenario: BTTestScenario, actor_id: str
    ) -> None:
        """A refusal arm ahead of a write raises rather than falls through:
        FAILURE here would run the creation arm against an unreadable case."""
        result = bt_scenario.run(
            CaseEmbargoAlreadyInitializedNode(),
            actor_id=actor_id,
            case_id="https://example.org/cases/absent",
        )

        # The raise reaches BTBridge, which fails the whole tree and names the
        # case; a plain FAILURE from the node would have run the creation arm.
        assert result.status == Status.FAILURE
        assert "BtNodePreconditionError" in result.feedback_message
        assert "https://example.org/cases/absent" in result.feedback_message

    def test_is_composed_subtree_of_named_leaf_nodes(self) -> None:
        node = InitializeDefaultEmbargoNode()

        initialized_arm, refusal_arm, creation_arm = node.children
        assert isinstance(initialized_arm, CaseEmbargoAlreadyInitializedNode)
        assert isinstance(refusal_arm, CaseNotEmbargoEligibleNode)
        assert [type(child) for child in creation_arm.children] == [
            ResolveEmbargoDurationNode,
            CreateEmbargoEventNode,
            AdvanceEMStateToActiveNode,
            AttachEmbargoToCaseNode,
            SeedOwnerAsSignatoryNode,
            RegisterLongerProposalAsRevisionNode,
        ]

    def test_advance_em_state_delegates_to_embargo_lifecycle(
        self,
        bt_scenario: BTTestScenario,
        actor: CaseActor,
        actor_id: str,
        case_obj: VulnerabilityCase,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        calls: list[tuple[str, str, str, str]] = []
        embargo = EmbargoEvent(
            end_time=datetime.now(tz=UTC) + timedelta(days=1),
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
                result = MagicMock()
                result.em_after = kwargs.get("em_before", EM.NONE)
                return result

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
                object.__setattr__(
                    stored_case, "active_embargo", kwargs["embargo_id"]
                )
                stored_case.append_case_status(em_state=EM.ACTIVE)
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


class TestAttachEmbargoToCaseNodeAC1:
    """AC-1 regression for AttachEmbargoToCaseNode (issue #2583)."""

    @pytest.mark.spec("EMB-18-001")
    def test_em_write_routes_through_embargo_lifecycle(
        self,
        bt_scenario: BTTestScenario,
        actor_id: str,
        case_obj: VulnerabilityCase,
    ) -> None:
        """AC-1 (issue #2712): EM write routes through EmbargoLifecycle.activate_embargo.

        When activate_embargo raises VultronError the node returns FAILURE —
        proving the EM write is delegated to the service layer.
        """
        from unittest.mock import patch

        from vultron.core.services.embargo_lifecycle import EmbargoLifecycle
        from vultron.errors import VultronInvalidStateTransitionError

        embargo = EmbargoEvent(
            end_time=datetime.now(tz=UTC) + timedelta(days=1),
            context=case_obj.id_,
        )
        bt_scenario.dl.create(embargo)

        bt_scenario.run(
            CreateCaseOwnerParticipant(),
            actor_id=actor_id,
            case_id=case_obj.id_,
        )

        with patch.object(
            EmbargoLifecycle,
            "activate_embargo",
            side_effect=VultronInvalidStateTransitionError("forced failure"),
        ):
            result = bt_scenario.run(
                AttachEmbargoToCaseNode(),
                actor_id=actor_id,
                case_id=case_obj.id_,
                default_embargo_id=embargo.id_,
                default_embargo_initialized=True,
            )

        assert result.status == Status.FAILURE


class TestSeedOwnerAsSignatoryNode:
    """SeedOwnerAsSignatoryNode is idempotent when participant is already SIGNATORY."""

    def test_already_signatory_is_idempotent(
        self,
        bt_scenario: BTTestScenario,
        actor: CaseActor,
        actor_id: str,
        case_obj: VulnerabilityCase,
    ) -> None:
        """AC-5: SIGNATORY participant stays SIGNATORY without raising.

        SeedOwnerAsSignatoryNode guards against ACCEPT from SIGNATORY
        (which would raise VultronInvalidStateTransitionError). The node
        must succeed idempotently when the participant is already SIGNATORY.
        """
        bt_scenario.run(
            CreateCaseOwnerParticipant(),
            actor_id=actor_id,
            case_id=case_obj.id_,
        )

        bt_scenario.run(
            InitializeDefaultEmbargoNode(),
            actor_id=actor_id,
            owner_profile=_profile(actor_id),
            case_id=case_obj.id_,
        )

        stored_case = cast(Any, bt_scenario.dl.read(case_obj.id_))
        participant_id = stored_case.actor_participant_index.get(actor_id)
        participant = cast(Any, bt_scenario.dl.read(participant_id))
        assert participant.embargo_consent_state == PEC.SIGNATORY

        result = bt_scenario.run(
            SeedOwnerAsSignatoryNode(),
            actor_id=actor_id,
            case_id=case_obj.id_,
            default_embargo_initialized=True,
        )
        assert result.status == Status.SUCCESS

        refreshed = cast(Any, bt_scenario.dl.read(participant_id))
        assert refreshed.embargo_consent_state == PEC.SIGNATORY


_CASE_MANAGER_ID = "https://example.org/case-actors/svc-1"
_OWNER_ID = "https://example.org/actors/vendor"


def _seed_manager_run_case(scenario: BTTestScenario) -> VulnerabilityCase:
    """Seed, in *scenario*'s store, a case as a proposal leaves it.

    ``attributed_to`` names the owner, and a separate participant holds
    CASE_MANAGER, so the CASE_MANAGER executing the subtree is not the owner
    (CP-09-001).
    """
    from vultron.core.models.case_participant import CaseParticipant
    from vultron.enums.roles import CVDRole

    report = VulnerabilityReport(name="TEST-CM", content="Test report")
    case = VulnerabilityCase(
        id_="https://example.org/cases/case-cm",
        attributed_to=_OWNER_ID,
        vulnerability_reports=[report.id_],
    )
    owner = CaseParticipant(
        attributed_to=_OWNER_ID,
        context=case.id_,
        case_roles=[CVDRole.CASE_OWNER],
    )
    manager = CaseParticipant(
        attributed_to=_CASE_MANAGER_ID,
        context=case.id_,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    for participant in (owner, manager):
        case.add_participant(participant)
    scenario.seed(report, owner, manager, case)
    return case


@pytest.mark.spec("CP-09-001")
@pytest.mark.spec("CM-13-001")
class TestCaseManagerInitializesTheOwnersEmbargo:
    """The CASE_MANAGER runs the subtree; the owner it seeds is the case's."""

    def test_owner_from_attributed_to_is_seeded_signatory(self) -> None:
        scenario = BTTestScenario(actor_id=_CASE_MANAGER_ID)
        case = _seed_manager_run_case(scenario)

        result = scenario.run(
            InitializeDefaultEmbargoNode(),
            case_id=case.id_,
            owner_profile=_profile(_OWNER_ID),
        )
        assert result.status == Status.SUCCESS, result.feedback_message

        stored_case = cast(Any, scenario.dl.read(case.id_))
        assert stored_case.active_embargo is not None
        index = stored_case.actor_participant_index
        owner = cast(Any, scenario.dl.read(index[_OWNER_ID]))
        assert owner.embargo_consent_state == PEC.SIGNATORY
        assert stored_case.active_embargo in owner.accepted_embargo_ids

    def test_an_actor_neither_owner_nor_manager_cannot_activate(self) -> None:
        stranger = "https://example.org/actors/stranger"
        scenario = BTTestScenario(actor_id=stranger)
        case = _seed_manager_run_case(scenario)
        embargo = EmbargoEvent(
            end_time=datetime.now(tz=UTC) + timedelta(days=1),
            context=case.id_,
        )
        scenario.seed(embargo)

        result = scenario.run(
            AdvanceEMStateToActiveNode(),
            case_id=case.id_,
            default_embargo_id=embargo.id_,
        )

        assert result.status == Status.FAILURE
        assert "neither case owner" in result.feedback_message
        stored_case = cast(Any, scenario.dl.read(case.id_))
        assert stored_case.active_embargo is None

    @pytest.mark.spec("CM-14-002")
    def test_a_missing_owner_participant_fails_initialization(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """No owner record to seed is a broken precondition, not a success."""
        scenario = BTTestScenario(actor_id=_OWNER_ID)
        report = VulnerabilityReport(name="TEST-NO", content="Test report")
        case = VulnerabilityCase(
            id_="https://example.org/cases/case-no-owner",
            attributed_to=_OWNER_ID,
            vulnerability_reports=[report.id_],
        )
        scenario.seed(report, case)

        with caplog.at_level(logging.ERROR):
            result = scenario.run(
                InitializeDefaultEmbargoNode(),
                case_id=case.id_,
                owner_profile=_profile(_OWNER_ID),
            )

        assert result.status == Status.FAILURE
        assert "has no participant record" in caplog.text
