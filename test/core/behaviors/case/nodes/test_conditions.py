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

Covers CheckCaseAlreadyExists, CheckCaseExistsForReport, and ValidateCaseObject.
Per specs/idempotency.yaml ID-04-004.
"""

import pytest
from py_trees.common import Status

from vultron.core.behaviors.case.nodes.conditions import (
    CheckCaseAlreadyExists,
    CheckCaseExistsForReport,
    ValidateCaseObject,
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
# ValidateCaseObject
# ---------------------------------------------------------------------------


class TestValidateCaseObject:
    """ValidateCaseObject returns SUCCESS for valid cases, FAILURE otherwise."""

    def test_succeeds_for_valid_case(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        actor_id: str,
        case_obj: VultronCase,
    ) -> None:
        result = bt_scenario.run(
            ValidateCaseObject(case_obj=case_obj),
            actor_id=actor_id,
        )
        assert result.status == Status.SUCCESS
