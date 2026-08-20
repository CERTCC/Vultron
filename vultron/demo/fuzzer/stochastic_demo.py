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
"""In-process STOCHASTIC bundle demo scenario (BT-23-001, BT-23-003).

Exercises STOCHASTIC call-out point bundles across validation, prioritization,
and embargo domains in a single in-process run.  No HTTP server required.

For each domain:

1. All call-out point nodes from the STOCHASTIC bundle singleton are
   instantiated and ticked ``N_TICKS`` times.  Each tick logs the node name
   and SUCCESS/FAILURE result so the probabilistic spread is visible.

2. The embargo domain additionally runs the full ``ManageEmbargoBT`` tree
   (10 call-out nodes) via the BTBridge + an in-memory DataLayer to show
   the complete tree execution path.

Run as a module::

    python -m vultron.demo.fuzzer.stochastic_demo

Or import :func:`run_stochastic_demo` to call it programmatically.

References
----------
- notes/call-out-configuration.md — three-mode model and bundle design
- specs/behavior-tree-integration.yaml — BT-23-001, BT-23-003
- Issue #1672 — AC-1 through AC-6
"""

from __future__ import annotations

import logging

import py_trees

logger = logging.getLogger(__name__)

# Number of ticks per call-out point node in the standalone tick loop.
N_TICKS = 5

# Actor / resource IDs used in the full-tree embargo run.
_DEMO_ACTOR_ID = "https://example.org/actors/demo-actor"
_DEMO_CASE_ID = "https://example.org/cases/demo-case-001"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _log_outcome(node: py_trees.behaviour.Behaviour, tick: int) -> None:
    logger.info(
        "call-out point outcome | tick=%d | node=%s | result=%s",
        tick,
        node.name,
        node.status.value,
    )


def _tick_node(node: py_trees.behaviour.Behaviour, tick: int) -> None:
    node.tick_once()
    _log_outcome(node, tick)


def _run_domain_nodes(
    domain: str,
    nodes: list[py_trees.behaviour.Behaviour],
    n_ticks: int = N_TICKS,
) -> None:
    """Setup and tick every node in a domain for n_ticks iterations."""
    logger.info("--- domain: %s (%d call-out points) ---", domain, len(nodes))
    for node in nodes:
        node.setup()
    for tick in range(1, n_ticks + 1):
        for node in nodes:
            # Reset to INVALID so each tick is independent
            node.stop(py_trees.common.Status.INVALID)
            _tick_node(node, tick)


# ---------------------------------------------------------------------------
# Domain-specific node lists
# ---------------------------------------------------------------------------


def _validation_nodes() -> list[py_trees.behaviour.Behaviour]:
    from vultron.demo.fuzzer.bundles.validation import VALIDATION_STOCHASTIC

    return [
        VALIDATION_STOCHASTIC.credibility_factory("EvaluateReportCredibility"),
        VALIDATION_STOCHASTIC.validity_factory("EvaluateReportValidity"),
        VALIDATION_STOCHASTIC.gather_info_factory("GatherValidationInfo"),
    ]


def _prioritization_nodes() -> list[py_trees.behaviour.Behaviour]:
    from vultron.demo.fuzzer.bundles.prioritization import (
        PRIORITIZATION_STOCHASTIC,
    )

    return [
        PRIORITIZATION_STOCHASTIC.on_accept_factory("OnAccept"),
        PRIORITIZATION_STOCHASTIC.on_defer_factory("OnDefer"),
        PRIORITIZATION_STOCHASTIC.enough_info_factory(
            "EnoughPrioritizationInfo"
        ),
        PRIORITIZATION_STOCHASTIC.gather_info_factory(
            "GatherPrioritizationInfo"
        ),
    ]


def _embargo_nodes() -> list[py_trees.behaviour.Behaviour]:
    from vultron.demo.fuzzer.bundles.embargo import EMBARGO_STOCHASTIC

    return [
        EMBARGO_STOCHASTIC.exit_embargo_when_deployed_factory(
            "ExitEmbargoWhenDeployed"
        ),
        EMBARGO_STOCHASTIC.exit_embargo_when_fix_ready_factory(
            "ExitEmbargoWhenFixReady"
        ),
        EMBARGO_STOCHASTIC.exit_embargo_for_other_reason_factory(
            "ExitEmbargoForOtherReason"
        ),
        EMBARGO_STOCHASTIC.stop_proposing_embargo_factory(
            "StopProposingEmbargo"
        ),
        EMBARGO_STOCHASTIC.select_embargo_offer_terms_factory(
            "SelectEmbargoOfferTerms"
        ),
        EMBARGO_STOCHASTIC.want_to_propose_embargo_factory(
            "WantToProposeEmbargo"
        ),
        EMBARGO_STOCHASTIC.willing_to_counter_factory(
            "WillingToCounterEmbargoProposal"
        ),
        EMBARGO_STOCHASTIC.reason_to_propose_when_deployed_factory(
            "ReasonToProposeEmbargoWhenDeployed"
        ),
        EMBARGO_STOCHASTIC.evaluate_embargo_proposal_factory(
            "EvaluateEmbargoProposal"
        ),
        EMBARGO_STOCHASTIC.current_embargo_acceptable_factory(
            "CurrentEmbargoAcceptable"
        ),
    ]


# ---------------------------------------------------------------------------
# Full-tree embargo run via BTBridge
# ---------------------------------------------------------------------------


def _run_embargo_full_tree(n_ticks: int = N_TICKS) -> None:
    """Run the full ManageEmbargoBT tree via BTBridge and in-memory DataLayer."""
    from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
    from vultron.adapters.driven.trigger_activity_adapter import (
        TriggerActivityAdapter,
    )
    from vultron.core.behaviors.bridge import BTBridge
    from vultron.core.behaviors.embargo.manage_embargo_tree import (
        create_manage_embargo_tree,
    )
    from vultron.demo.fuzzer.bundles.embargo import EMBARGO_STOCHASTIC

    logger.info(
        "--- domain: embargo (full tree via BTBridge, %d ticks) ---", n_ticks
    )

    # The tree executes as `_DEMO_ACTOR_ID` (below), and a BT reads and writes
    # its executing actor's own store (ADR-0066), so the store has to be that
    # actor's. Left unscoped, `BTBridge._store_for_actor` would re-scope away
    # from it and the fuzzer would tick against an empty store.
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_DEMO_ACTOR_ID)
    bridge = BTBridge(
        datalayer=dl,
        trigger_activity=TriggerActivityAdapter(dl),
    )

    for tick in range(1, n_ticks + 1):
        py_trees.blackboard.Blackboard.storage.clear()
        tree = create_manage_embargo_tree(
            case_id=_DEMO_CASE_ID,
            call_out=EMBARGO_STOCHASTIC,
        )
        result = bridge.execute_with_setup(
            tree,
            actor_id=_DEMO_ACTOR_ID,
        )
        for node in tree.iterate():
            if not isinstance(node, py_trees.composites.Composite):
                _log_outcome(node, tick)
        logger.info(
            "ManageEmbargoBT tick=%d root_status=%s",
            tick,
            result.status.value,
        )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_stochastic_demo(n_ticks: int = N_TICKS) -> None:
    """Run the full STOCHASTIC bundle demo across all three domains.

    Args:
        n_ticks: Number of ticks per call-out point node (default: ``N_TICKS``).
    """
    logger.info("=== Stochastic Bundle Demo — start ===")

    py_trees.blackboard.Blackboard.storage.clear()
    try:
        _run_domain_nodes("validation", _validation_nodes(), n_ticks)
        _run_domain_nodes("prioritization", _prioritization_nodes(), n_ticks)
        _run_domain_nodes(
            "embargo (standalone nodes)", _embargo_nodes(), n_ticks
        )
        _run_embargo_full_tree(n_ticks)
    finally:
        py_trees.blackboard.Blackboard.storage.clear()

    logger.info("=== Stochastic Bundle Demo — complete ===")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s %(message)s",
    )
    run_stochastic_demo()
