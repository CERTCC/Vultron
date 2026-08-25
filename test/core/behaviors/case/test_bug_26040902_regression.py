#!/usr/bin/env python
"""Regression test for BUG-26040902 (updated for ADR-0041).

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

ADR-0041 update: ReceiveReportCaseBT no longer creates a VulnerabilityCase.
Instead it writes a VultronReportCaseLink and enqueues Create(as_CaseProposal).
The test now verifies the pending link is written and the outbox is non-empty.

This test verifies the fix by:
  1. NOT importing VulnerabilityCase or VulnerabilityReport explicitly
  2. Running ReceiveReportCaseBT against a fresh in-memory DataLayer
  3. Asserting Status.SUCCESS and a pending VultronReportCaseLink in the DataLayer
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

_CASE_ACTOR_SERVICE_URL = "http://case-actor:7999/api/v2"


@pytest.fixture(autouse=True)
def configure_case_actor_url(monkeypatch):
    """Set VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL for the regression test."""
    monkeypatch.setenv(
        "VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL", _CASE_ACTOR_SERVICE_URL
    )
    from vultron.config.app import reload_config

    reload_config()
    yield
    # Undo the env patch BEFORE reloading: monkeypatch's own undo runs after
    # this teardown, so reloading first would re-cache this fixture's URL into
    # the module-level config for the rest of the session (#2086).
    monkeypatch.undo()
    reload_config()


@pytest.fixture
def _fresh_datalayer():
    """In-memory SQLite DataLayer with NO pre-seeded vocabulary imports."""
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


@pytest.mark.spec("CM-12-001")
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

    ADR-0041: tree now writes a VultronReportCaseLink and queues a proposal.
    """
    from vultron.core.behaviors.bridge import BTBridge
    from vultron.core.behaviors.case.receive_report_case_tree import (
        create_receive_report_case_tree,
    )
    from vultron.core.models.report_case_link import VultronReportCaseLink
    from vultron.core.models.vultron_types import (
        VultronCaseActor,
        VultronOffer,
        VultronReport,
    )
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

    # Run the BT — must succeed without conftest side-effect imports
    from vultron.adapters.driven.trigger_activity_adapter import (
        TriggerActivityAdapter,
    )
    from vultron.core.models.activity import VultronActivity
    from vultron.core.models.events import MessageSemantics
    from vultron.core.models.events.report import SubmitReportReceivedEvent

    offer_activity_snapshot = VultronActivity(
        id_=_offer_id,
        type_="Offer",
        actor=_reporter_actor_id,
        object_=report,
    )
    submit_report_event = SubmitReportReceivedEvent(
        semantic_type=MessageSemantics.SUBMIT_REPORT,
        activity_id=_offer_id,
        activity_type="Offer",
        actor_id=_reporter_actor_id,
        activity=offer_activity_snapshot,
    )

    bridge = BTBridge(
        datalayer=dl, trigger_activity=TriggerActivityAdapter(dl)
    )
    tree = create_receive_report_case_tree(
        report_id=_report_id,
        offer_id=_offer_id,
        reporter_actor_id=_reporter_actor_id,
    )
    result = bridge.execute_with_setup(
        tree=tree, actor_id=_actor_id, activity=submit_report_event
    )

    assert result.status == Status.SUCCESS, (
        f"BUG-26040902 regression: ReceiveReportCaseBT returned {result.status} "
        "— empty vocabulary registry likely caused silent BT failure"
    )

    # ADR-0041: verify a pending VultronReportCaseLink was written
    link_id = VultronReportCaseLink.build_id(_report_id)
    link = dl.read(link_id)
    assert isinstance(link, VultronReportCaseLink), (
        "BUG-26040902 regression (ADR-0041): no VultronReportCaseLink written"
        " after BT success"
    )
    assert link.case_id is None, "Link must be pending (case_id=None)"

    # Verify outbox has the Create(as_CaseProposal) notification
    outbox_items = dl.clone_for_actor(_actor_id).outbox_list()
    assert len(outbox_items) > 0, (
        "BUG-26040902 regression: no outbox entry created — "
        "CaseActor would never receive the CaseProposal"
    )
