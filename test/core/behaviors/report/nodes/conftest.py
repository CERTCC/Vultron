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
Fixtures for test/core/behaviors/report/nodes tests.

Imports VulnerabilityCase (and related wire-layer types) as a side effect so
that the global vocabulary registry is populated before any test in this
package runs.
"""

import pytest

from vultron.core.models.activity import VultronOffer
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_actor import VultronCaseActor
from vultron.core.models.report import VultronReport
from test.core.behaviors.bt_harness import BTTestScenario

# noqa: F401 — imported for vocabulary registration side-effect
from vultron.wire.as2.vocab.objects.vulnerability_case import (  # noqa: F401
    VulnerabilityCase as _WireVulnerabilityCase,
)


@pytest.fixture
def actor(bt_scenario: BTTestScenario) -> VultronCaseActor:
    """Create a test actor and persist it in the scenario DataLayer."""
    obj = VultronCaseActor(
        id_="https://example.org/actors/vendor",
        name="Vendor Co",
    )
    bt_scenario.dl.create(obj)
    return obj


@pytest.fixture
def report(bt_scenario: BTTestScenario) -> VultronReport:
    """Create a test report and persist it in the scenario DataLayer."""
    obj = VultronReport(
        name="TEST-001",
        content="Test vulnerability report",
    )
    bt_scenario.dl.create(obj)
    return obj


@pytest.fixture
def offer(
    bt_scenario: BTTestScenario,
    report: VultronReport,
    actor: VultronCaseActor,
) -> VultronOffer:
    """Create a test offer and persist it in the scenario DataLayer."""
    obj = VultronOffer(actor=actor.id_, object_=report.id_)
    bt_scenario.dl.create(obj)
    return obj


@pytest.fixture
def case(
    bt_scenario: BTTestScenario,
    report: VultronReport,
    actor: VultronCaseActor,
) -> VulnerabilityCase:
    """Create a VulnerabilityCase linked to the test report."""
    obj = VulnerabilityCase(
        name="Test Case for TEST-001",
        vulnerability_reports=[report.id_],
        attributed_to=actor.id_,
    )
    bt_scenario.dl.create(obj)
    return obj
