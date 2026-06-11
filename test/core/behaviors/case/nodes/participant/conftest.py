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

"""Shared fixtures for participant-node tests."""

import pytest

from vultron.core.models.vultron_types import (
    VultronCase,
    VultronCaseActor,
    VultronReport,
)
from test.core.behaviors.bt_harness import BTTestScenario


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
