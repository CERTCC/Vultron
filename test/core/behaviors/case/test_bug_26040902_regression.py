#!/usr/bin/env python
"""Regression test for BUG-26040902.

Verifies that ReceiveReportCaseBT succeeds without any explicit
VulnerabilityCase or VulnerabilityReport imports as side effects.

Previously, the test suite only passed in isolation because
test/core/behaviors/case/conftest.py imported VulnerabilityCase,
populating the vocabulary registry as a side effect.  In Docker
(or any environment where that conftest does not run), the registry
was empty and the BT silently failed.

VOCAB-REG-1.2 fixes this by adding dynamic module discovery to the
vocab package __init__.py files, ensuring all types are registered
automatically when the package is imported.

This test verifies the fix by:
  1. NOT importing VulnerabilityCase or VulnerabilityReport explicitly
  2. Running ReceiveReportCaseBT against a fresh in-memory DataLayer
  3. Asserting Status.SUCCESS and a non-empty outbox
"""

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

import pytest
from py_trees.common import Status


@pytest.fixture
def _fresh_datalayer():
    """In-memory TinyDB DataLayer with NO pre-seeded vocabulary imports."""
    from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

    return SqliteDataLayer("sqlite:///:memory:")


@pytest.fixture
def _actor_id():
    return "https://example.org/actors/vendor"


@pytest.fixture
def _reporter_actor_id():
    return "https://example.org/actors/reporter"


@pytest.fixture
def _report_id():
    return "https://example.org/reports/BUG-26040902-regression"


@pytest.fixture
def _offer_id():
    return "https://example.org/activities/offer-BUG-26040902"


def test_receive_report_case_bt_succeeds_without_conftest_imports(
    _fresh_datalayer,
    _actor_id,
    _reporter_actor_id,
    _report_id,
    _offer_id,
):
    """BUG-26040902 regression: BT works without explicit vocab side-effect imports.

    This test deliberately does NOT import VulnerabilityCase or
    VulnerabilityReport at module level.  If dynamic discovery is broken,
    the vocabulary registry will be empty and the BT will return FAILURE
    because dl.read(report_id) cannot reconstruct the VulnerabilityReport
    from its TinyDB record.
    """
    from vultron.core.behaviors.bridge import BTBridge
    from vultron.core.behaviors.case.receive_report_case_tree import (
        create_receive_report_case_tree,
    )
    from vultron.core.models.participant_status import VultronParticipantStatus
    from vultron.core.models.vultron_types import (
        VultronCaseActor,
        VultronOffer,
        VultronReport,
    )
    from vultron.core.states.rm import RM
    from vultron.core.use_cases._helpers import _report_phase_status_id
    from vultron.wire.as2.vocab.base.registry import VOCABULARY

    dl = _fresh_datalayer

    # Verify key types ARE registered (dynamic discovery must have run)
    assert "VulnerabilityReport" in VOCABULARY, (
        "BUG-26040902: VulnerabilityReport not in VOCABULARY — "
        "dynamic discovery did not run"
    )
    assert "VulnerabilityCase" in VOCABULARY, (
        "BUG-26040902: VulnerabilityCase not in VOCABULARY — "
        "dynamic discovery did not run"
    )

    # Seed minimal DataLayer state (mirrors what upstream use cases create)
    actor = VultronCaseActor(id_=_actor_id, name="Vendor Co")
    dl.create(actor)

    reporter_actor = VultronCaseActor(
        id_=_reporter_actor_id, name="Reporter Co"
    )
    dl.create(reporter_actor)

    report = VultronReport(
        id_=_report_id,
        name="BUG-26040902 Regression Report",
        content="Buffer overflow in regression test component",
    )
    dl.create(report)

    offer = VultronOffer(
        id_=_offer_id,
        actor=_reporter_actor_id,
        object_=_report_id,
        target=_actor_id,
    )
    dl.create(offer)

    reporter_status = VultronParticipantStatus(
        id_=_report_phase_status_id(
            _reporter_actor_id, _report_id, RM.ACCEPTED.value
        ),
        context=_report_id,
        attributed_to=_reporter_actor_id,
        rm_state=RM.ACCEPTED,
    )
    dl.create(reporter_status)

    vendor_status = VultronParticipantStatus(
        id_=_report_phase_status_id(_actor_id, _report_id, RM.RECEIVED.value),
        context=_report_id,
        attributed_to=_actor_id,
        rm_state=RM.RECEIVED,
    )
    dl.create(vendor_status)

    # Run the BT — must succeed without conftest side-effect imports
    from vultron.adapters.driven.trigger_activity_adapter import (
        TriggerActivityAdapter,
    )

    bridge = BTBridge(
        datalayer=dl, trigger_activity=TriggerActivityAdapter(dl)
    )
    tree = create_receive_report_case_tree(
        report_id=_report_id,
        offer_id=_offer_id,
        reporter_actor_id=_reporter_actor_id,
    )
    result = bridge.execute_with_setup(tree=tree, actor_id=_actor_id)

    assert result.status == Status.SUCCESS, (
        f"BUG-26040902 regression: ReceiveReportCaseBT returned {result.status} "
        "— empty vocabulary registry likely caused silent BT failure"
    )

    # Verify a case was created
    case = dl.find_case_by_report_id(_report_id)
    assert (
        case is not None
    ), "BUG-26040902 regression: no VulnerabilityCase created after BT success"

    # Verify outbox has the Create(Case) notification
    updated_actor = dl.read(_actor_id)
    assert updated_actor is not None
    assert len(updated_actor.outbox.items) > 0, (
        "BUG-26040902 regression: no outbox entry created — "
        "reporter would never receive VulnerabilityCase"
    )
