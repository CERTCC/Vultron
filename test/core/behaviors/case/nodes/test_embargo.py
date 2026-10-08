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
from test.support.embargo_register import activate
from vultron.core.behaviors.case.embargo_tree import (
    InitializeDefaultEmbargoNode,
)
from vultron.core.behaviors.case.nodes.embargo import (
    CreateEmbargoEventNode,
    InitializeCreationEmbargoNode,
)
from vultron.core.behaviors.case.nodes.embargo_resolution import (
    CaseEmbargoAlreadyInitializedNode,
    CaseNotEmbargoEligibleNode,
    ResolveEmbargoDurationNode,
)
from vultron.core.behaviors.case.nodes.embargo_revision import (
    ResolveCreationTimeRevisionNode,
)
from vultron.core.behaviors.case.participant_tree import (
    CreateCaseOwnerParticipant,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.actor import VultronOrganization
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_actor import CaseActor
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.embargo_policy import EmbargoPolicy
from vultron.core.models.report import VulnerabilityReport
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)

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
        """Owner participant is seeded with an ACCEPTED row for the default embargo (CM-14-003)."""
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
        assert participant.is_signatory(stored_case.active_embargo_id)

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
                InitializeDefaultEmbargoNode(
                    report_id="https://example.org/reports/r-1"
                ),
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
        # The contest's other party is the reporter (#4152).
        report = VulnerabilityReport(
            name="TEST-REV",
            content="Test report",
            attributed_to="https://example.org/actors/reporter",
        )
        bt_scenario.dl.create(report)
        for _ in range(2):
            result = bt_scenario.run(
                InitializeDefaultEmbargoNode(report_id=report.id_),
                actor_id=actor_id,
                case_id=case_obj.id_,
                sender_proposed_embargo_duration=timedelta(days=10),
                sender_proposed_embargo=proposal,
                owner_profile=_profile(actor_id, timedelta(days=30)),
            )
            assert result.status == Status.SUCCESS

        stored_case = cast(Any, bt_scenario.dl.read(case_obj.id_))
        assert stored_case.current_status.em.state == EM.REVISE
        assert len(stored_case.proposed_embargo_ids) == 1
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
            ResolveCreationTimeRevisionNode,
            InitializeCreationEmbargoNode,
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

            def initialize_creation_embargo(self, **kwargs: Any) -> Any:
                calls.append(
                    (
                        "initialize",
                        kwargs["case_id"],
                        kwargs["embargo"].id_,
                        kwargs["actor_id"],
                    )
                )
                return MagicMock()

        monkeypatch.setattr(
            "vultron.core.behaviors.case.nodes.embargo.EmbargoLifecycle",
            FakeEmbargoLifecycle,
        )

        result = bt_scenario.run(
            InitializeCreationEmbargoNode(),
            actor_id=actor_id,
            case_id=case_obj.id_,
            default_embargo=embargo,
        )

        assert result.status == Status.SUCCESS
        # One lifecycle call, not propose then activate (EP-04-002, #4123).
        assert calls == [
            ("initialize", case_obj.id_, embargo.id_, actor_id),
        ]


class TestInitializeCreationEmbargoNodeAC1:
    """AC-1 regression for the creation-time EM write (issues #2583, #4123)."""

    @pytest.mark.spec("EMB-18-001")
    def test_em_write_routes_through_embargo_lifecycle(
        self,
        bt_scenario: BTTestScenario,
        actor_id: str,
        case_obj: VulnerabilityCase,
    ) -> None:
        """AC-1 (issue #2712): EM write routes through EmbargoLifecycle.

        When ``initialize_creation_embargo`` raises VultronError the node
        returns FAILURE — proving the EM write is delegated to the service
        layer — and the case is left at ``EM.NONE`` (EP-04-002).
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
            "initialize_creation_embargo",
            side_effect=VultronInvalidStateTransitionError("forced failure"),
        ):
            result = bt_scenario.run(
                InitializeCreationEmbargoNode(),
                actor_id=actor_id,
                case_id=case_obj.id_,
                default_embargo=embargo,
            )

        assert result.status == Status.FAILURE
        stored = cast(Any, bt_scenario.dl.read(case_obj.id_))
        assert stored.current_status.em.state == EM.NONE
        assert stored.active_embargo is None

    @pytest.mark.spec("EP-04-012")
    def test_an_attached_embargo_at_none_fails_rather_than_skips(
        self,
        bt_scenario: BTTestScenario,
        actor_id: str,
        case_obj: VulnerabilityCase,
    ) -> None:
        """A case at ``EM.NONE`` with an embargo attached is not initialized.

        The guard ahead of the node takes every case past ``NONE``, so this
        state is inconsistent.  The node reports the service's refusal as
        FAILURE instead of a SUCCESS that initialized nothing (ARCH-15).
        """
        attached = EmbargoEvent(
            end_time=datetime.now(tz=UTC) + timedelta(days=1),
            context=case_obj.id_,
        )
        default = EmbargoEvent(
            end_time=datetime.now(tz=UTC) + timedelta(days=2),
            context=case_obj.id_,
        )
        bt_scenario.dl.create(attached)
        bt_scenario.dl.create(default)
        bt_scenario.run(
            CreateCaseOwnerParticipant(),
            actor_id=actor_id,
            case_id=case_obj.id_,
        )
        stored = cast(VulnerabilityCase, bt_scenario.dl.read(case_obj.id_))
        activate(stored, attached.id_)
        bt_scenario.dl.save(stored)

        result = bt_scenario.run(
            InitializeCreationEmbargoNode(),
            actor_id=actor_id,
            case_id=case_obj.id_,
            default_embargo=default,
        )

        assert result.status == Status.FAILURE
        assert "already attached" in result.feedback_message
        after = cast(Any, bt_scenario.dl.read(case_obj.id_))
        assert after.em_state == EM.ACTIVE
        assert _as_id(after.active_embargo) == attached.id_


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
        assert owner.is_signatory(stored_case.active_embargo_id)
        assert (
            owner.consent_for(stored_case.active_embargo_id)
            == EmbargoConsentState.ACCEPTED
        )

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
            InitializeCreationEmbargoNode(),
            case_id=case.id_,
            default_embargo=embargo,
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
        assert f"for owner '{_OWNER_ID}' not found" in caplog.text
        # Refused before the activation, so the case is left for a rerun.
        stored_case = cast(Any, scenario.dl.read(case.id_))
        assert stored_case.current_status.em.state == EM.NONE
        assert stored_case.active_embargo is None
