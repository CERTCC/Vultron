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
Unit tests for case condition nodes.

Covers CheckCaseAlreadyExists and CheckCaseExistsForReport.
Per specs/idempotency.yaml ID-04-004.

Also covers the construction-time guarantee that VultronCase rejects
invalid id_ values (ARCH-10-001), which made the former ValidateCaseObject
BT node redundant (removed in issue #716).
"""

import pytest
from py_trees.common import Status
from pydantic import ValidationError

from vultron.core.behaviors.case.nodes.conditions import (
    CheckCaseAlreadyExists,
    CheckCaseExistsForReport,
)
from vultron.core.models.vultron_types import (
    VultronCase,
    VultronCaseActor,
    VultronParticipant,
    VultronReport,
)
from vultron.core.states.roles import CVDRole
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
    bt_scenario: BTTestScenario, report: VultronReport
) -> VultronCase:
    case = VultronCase(
        id_="https://example.org/cases/case-001",
        name="Test Case",
        vulnerability_reports=[report.id_],
    )
    bt_scenario.dl.create(case)
    return case


@pytest.fixture
def participant(
    bt_scenario: BTTestScenario,
    case_obj: VultronCase,
    actor_id: str,
) -> VultronParticipant:
    p = VultronParticipant(
        attributed_to=actor_id,
        context=case_obj.id_,
        case_roles=[CVDRole.VENDOR],
    )
    bt_scenario.dl.create(p)
    case_obj.case_participants.append(p.id_)
    bt_scenario.dl.save(case_obj)
    return p


# ---------------------------------------------------------------------------
# CheckCaseAlreadyExists
# ---------------------------------------------------------------------------


class TestCheckCaseAlreadyExists:
    """ID-04-004: idempotency guard — case with participants → SUCCESS."""

    def test_returns_failure_when_case_missing(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        actor_id: str,
    ) -> None:
        result = bt_scenario.run(
            CheckCaseAlreadyExists(
                case_id="https://example.org/cases/missing"
            ),
            actor_id=actor_id,
        )
        assert result.status == Status.FAILURE

    def test_returns_failure_when_case_has_no_participants(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        actor_id: str,
        case_obj: VultronCase,
    ) -> None:
        """Case exists but has no participants → still FAILURE (needs init)."""
        result = bt_scenario.run(
            CheckCaseAlreadyExists(case_id=case_obj.id_),
            actor_id=actor_id,
        )
        assert result.status == Status.FAILURE

    def test_returns_success_when_case_has_participants(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        actor_id: str,
        case_obj: VultronCase,
        participant: VultronParticipant,
    ) -> None:
        """Case with participants → SUCCESS (already initialized)."""
        result = bt_scenario.run(
            CheckCaseAlreadyExists(case_id=case_obj.id_),
            actor_id=actor_id,
        )
        assert result.status == Status.SUCCESS


# ---------------------------------------------------------------------------
# CheckCaseExistsForReport
# ---------------------------------------------------------------------------


class TestCheckCaseExistsForReport:
    """ID-04-004: idempotency guard — case by report — with/without participants."""

    def test_returns_failure_when_no_case_for_report(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        actor_id: str,
        report: VultronReport,
    ) -> None:
        result = bt_scenario.run(
            CheckCaseExistsForReport(report_id=report.id_),
            actor_id=actor_id,
        )
        assert result.status == Status.FAILURE

    def test_returns_failure_when_case_has_no_participants(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        actor_id: str,
        case_obj: VultronCase,
        report: VultronReport,
    ) -> None:
        """Case linked to report exists but has no participants → FAILURE."""
        result = bt_scenario.run(
            CheckCaseExistsForReport(report_id=report.id_),
            actor_id=actor_id,
        )
        assert result.status == Status.FAILURE

    def test_returns_success_when_case_has_participants(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        actor_id: str,
        case_obj: VultronCase,
        report: VultronReport,
        participant: VultronParticipant,
    ) -> None:
        """Case linked to report with participants → SUCCESS."""
        result = bt_scenario.run(
            CheckCaseExistsForReport(report_id=report.id_),
            actor_id=actor_id,
        )
        assert result.status == Status.SUCCESS


# ---------------------------------------------------------------------------
# VultronCase construction-time id_ contract (ARCH-10-001)
# ---------------------------------------------------------------------------


class TestVultronCaseIdContract:
    """VultronCase rejects invalid id_ at construction time (ARCH-10-001).

    This guarantees that any VultronCase object that exists at runtime already
    has a valid non-empty id_, making a runtime BT validation node redundant
    (see issue #716).
    """

    def test_empty_id_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            VultronCase(id_="")

    def test_whitespace_only_id_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            VultronCase(id_="   ")

    def test_auto_generated_id_is_nonempty(self) -> None:
        case = VultronCase()
        assert case.id_ and case.id_.strip()
