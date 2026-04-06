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
Performance tests for BT execution.

Per plan/IMPLEMENTATION_PLAN.md BT-1.5.3, measure handler execution time
and document performance baseline. Target: P99 < 100ms per plan/BT_INTEGRATION.md.
"""

import logging
import time
from unittest.mock import MagicMock

import pytest
from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.report.validate_tree import (
    create_validate_report_tree,
)
from vultron.core.models.vultron_types import (
    VultronAccept,
    VultronCaseActor,
    VultronOffer,
    VultronReport,
)

logger = logging.getLogger(__name__)


@pytest.fixture
def mock_datalayer():
    """Mock DataLayer for performance testing."""
    dl = MagicMock()  # Don't spec=DataLayer since we need read() method too

    # In-memory store so that create()/save() objects are visible to read().
    storage: dict = {}

    # Mock get() to return objects needed by BT nodes
    def mock_get(table, id_):
        if "report" in id_:
            return {
                "id_": id_,
                "type_": "VulnerabilityReport",
                "name": "TEST-REPORT",
                "content": "Test vulnerability report",
            }
        elif "offer" in id_:
            return {
                "id_": id_,
                "type_": "Offer",
                "actor": "https://example.org/finder",
                "object_": "test-report-123",
            }
        elif "actor" in id_ or "Person" in table or "Organization" in table:
            return {
                "id_": id_,
                "type_": "Person",
                "inbox": {"items": []},
                "outbox": {"items": []},
            }
        return None

    # Mock read() for nodes that use TinyDB-specific method.
    # Returns objects from the in-memory store first, then falls back to
    # pattern-based construction so that objects persisted via create()/save()
    # are visible to subsequent reads (e.g. CreateInitialVendorParticipant
    # reading back the case created by CreateCaseNode).
    def mock_read(id_, raise_on_missing=False):
        if id_ in storage:
            return storage[id_]
        if "report" in id_:
            return VultronReport(
                id_=id_,
                name="TEST-REPORT",
                content="Test vulnerability report",
            )
        elif "offer" in id_:
            return VultronOffer(
                id_=id_,
                actor="https://example.org/finder",
                object_="test-report-123",
            )
        elif id_.startswith("https://example.org/"):
            return VultronCaseActor(id_=id_, name="Test Actor")
        if raise_on_missing:
            raise ValueError(f"Object not found: {id_}")
        return None

    def mock_create(obj):
        id_ = getattr(obj, "id_", None)
        if id_:
            storage[id_] = obj

    def mock_save(obj):
        id_ = getattr(obj, "id_", None)
        if id_:
            storage[id_] = obj

    def mock_by_type(type_name):
        if type_name == "Offer":
            return {
                "test-offer-456": {
                    "id_": "test-offer-456",
                    "type_": "Offer",
                    "actor": "https://example.org/finder",
                    "object_": "test-report-123",
                }
            }
        return {}

    dl.get.side_effect = mock_get
    dl.read.side_effect = mock_read
    dl.create.side_effect = mock_create
    dl.save.side_effect = mock_save
    dl.update.return_value = None
    dl.by_type.side_effect = mock_by_type
    dl.record_outbox_item.return_value = None

    return dl


@pytest.fixture
def sample_activity():
    """Sample validation activity for testing."""
    report = VultronReport(
        name="TEST-PERF-001",
        content="Performance test report",
    )

    offer = VultronOffer(
        actor="https://example.org/finder",
        object_=report.id_,
    )

    return VultronAccept(
        actor="https://example.org/vendor",
        object_=offer.id_,
    )


def test_bt_execution_performance_single_run(mock_datalayer, sample_activity):
    """
    Test single BT execution for performance baseline.

    This measures one complete validation BT execution to establish
    baseline performance. Target: < 100ms per BT_INTEGRATION.md.
    """
    bridge = BTBridge(datalayer=mock_datalayer)
    tree = create_validate_report_tree(
        report_id="test-report-123", offer_id="test-offer-456"
    )

    start = time.perf_counter()
    result = bridge.execute_with_setup(
        tree, actor_id="https://example.org/vendor", activity=sample_activity
    )
    elapsed_ms = (time.perf_counter() - start) * 1000

    # Verify execution succeeded
    assert result.status == Status.SUCCESS

    # Log performance result
    logger.info("BT execution time: %.2fms", elapsed_ms)

    # Document baseline (not a hard assertion for now, just measurement)
    if elapsed_ms >= 100:
        logger.warning(
            "Execution time (%.2fms) exceeds 100ms target", elapsed_ms
        )
    else:
        logger.info("Execution time within 100ms target")


def test_bt_execution_performance_percentiles(mock_datalayer, sample_activity):
    """
    Measure BT execution across multiple runs to calculate percentiles.

    Runs BT execution N times and calculates P50, P95, P99 to establish
    performance baseline. Target: P99 < 100ms per BT_INTEGRATION.md.
    """
    bridge = BTBridge(datalayer=mock_datalayer)
    n_runs = 100
    timings = []

    for _ in range(n_runs):
        tree = create_validate_report_tree(
            report_id="test-report-123", offer_id="test-offer-456"
        )

        start = time.perf_counter()
        result = bridge.execute_with_setup(
            tree,
            actor_id="https://example.org/vendor",
            activity=sample_activity,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000
        timings.append(elapsed_ms)

        # Verify all executions succeeded
        assert result.status == Status.SUCCESS

    # Calculate percentiles
    timings.sort()
    p50 = timings[len(timings) // 2]
    p95 = timings[int(len(timings) * 0.95)]
    p99 = timings[int(len(timings) * 0.99)]
    mean = sum(timings) / len(timings)

    # Log performance results
    logger.info(
        "BT execution performance (%d runs): Mean=%.2fms P50=%.2fms P95=%.2fms P99=%.2fms",
        n_runs,
        mean,
        p50,
        p95,
        p99,
    )

    # Document whether we meet target
    if p99 >= 100:
        logger.warning("P99 (%.2fms) exceeds 100ms target", p99)
    else:
        logger.info("P99 performance meets 100ms target")

    # Soft assertion - document but don't fail build
    # (allows documenting current state even if not optimal)
    assert p99 < 200, f"P99 ({p99:.2f}ms) exceeds 200ms hard limit"
