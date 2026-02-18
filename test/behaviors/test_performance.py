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

import time
from unittest.mock import MagicMock

import pytest
from py_trees.common import Status

from vultron.api.v2.datalayer.abc import DataLayer
from vultron.as_vocab.base.objects.activities.transitive import as_Accept
from vultron.as_vocab.base.objects.activities.transitive import as_Offer
from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport
from vultron.behaviors.bridge import BTBridge
from vultron.behaviors.report.validate_tree import create_validate_report_tree


@pytest.fixture
def mock_datalayer():
    """Mock DataLayer for performance testing."""
    dl = MagicMock()  # Don't spec=DataLayer since we need read() method too

    # Mock get() to return objects needed by BT nodes
    def mock_get(table, id_):
        if "report" in id_:
            return {
                "as_id": id_,
                "as_type": "VulnerabilityReport",
                "name": "TEST-REPORT",
                "content": "Test vulnerability report",
            }
        elif "offer" in id_:
            return {
                "as_id": id_,
                "as_type": "Offer",
                "actor": "https://example.org/finder",
                "as_object": "test-report-123",
            }
        elif "actor" in id_ or "Person" in table or "Organization" in table:
            return {
                "as_id": id_,
                "as_type": "Person",
                "inbox": {"items": []},
                "outbox": {"items": []},
            }
        return None

    # Mock read() for nodes that use TinyDB-specific method
    def mock_read(id_, raise_on_missing=False):
        if "report" in id_:
            report = VulnerabilityReport(
                name="TEST-REPORT", content="Test vulnerability report"
            )
            report.as_id = id_  # Override ID
            return report
        elif "offer" in id_:
            return as_Offer(
                actor="https://example.org/finder",
                as_object="test-report-123",
            )
        elif "case" in id_:
            from vultron.as_vocab.objects.vulnerability_case import (
                VulnerabilityCase,
            )

            case = VulnerabilityCase(name="Test Case")
            case.as_id = id_
            return case
        elif "example.org" in id_:  # Actor IDs
            from vultron.as_vocab.base.objects.actors import as_Actor

            actor = as_Actor()
            actor.as_id = id_
            actor.name = "Test Actor"
            return actor
        if raise_on_missing:
            raise ValueError(f"Object not found: {id_}")
        return None

    dl.get.side_effect = mock_get
    dl.read.side_effect = mock_read
    dl.update.return_value = None
    dl.create.return_value = None

    return dl


@pytest.fixture
def sample_activity():
    """Sample validation activity for testing."""
    report = VulnerabilityReport(
        name="TEST-PERF-001",
        content="Performance test report",
    )

    offer = as_Offer(
        actor="https://example.org/finder",
        as_object=report,
    )

    return as_Accept(
        actor="https://example.org/vendor",
        as_object=offer,
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
    print(f"\nBT execution time: {elapsed_ms:.2f}ms")

    # Document baseline (not a hard assertion for now, just measurement)
    if elapsed_ms >= 100:
        print(
            f"⚠️  WARNING: Execution time ({elapsed_ms:.2f}ms) exceeds 100ms target"
        )
    else:
        print(f"✓ Execution time within 100ms target")


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
    print(f"\nBT execution performance ({n_runs} runs):")
    print(f"  Mean:  {mean:.2f}ms")
    print(f"  P50:   {p50:.2f}ms")
    print(f"  P95:   {p95:.2f}ms")
    print(f"  P99:   {p99:.2f}ms")

    # Document whether we meet target
    if p99 >= 100:
        print(f"⚠️  WARNING: P99 ({p99:.2f}ms) exceeds 100ms target")
    else:
        print(f"✓ P99 performance meets 100ms target")

    # Soft assertion - document but don't fail build
    # (allows documenting current state even if not optimal)
    assert p99 < 200, f"P99 ({p99:.2f}ms) exceeds 200ms hard limit"
