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

"""Shared fixtures for test/core/behaviors/embargo/nodes tests.

Imports VulnerabilityCase as a side effect to populate the global vocabulary
registry before any test in this package runs.
"""

import py_trees
import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.states.em import EM
from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import (  # noqa: F401
    VulnerabilityCase,
)


def make_case_and_embargo(
    case_suffix: str,
    em_state: EM = EM.ACTIVE,
) -> tuple[VulnerabilityCase, EmbargoEvent]:
    """Create an in-memory VulnerabilityCase + EmbargoEvent pair."""
    case = VulnerabilityCase(
        id_=f"https://example.org/cases/case_{case_suffix}",
        name=f"Test Case {case_suffix}",
    )
    embargo = EmbargoEvent(
        id_=f"https://example.org/cases/case_{case_suffix}/embargo_events/e1",
        context=case.id_,
    )
    case.active_embargo = embargo.id_
    case.current_status.em_state = em_state
    return case, embargo


def setup_blackboard(
    dl: SqliteDataLayer,
    actor_id: str = "https://example.org/users/vendor",
) -> None:
    """Populate the py_trees blackboard with the DataLayer and actor_id."""
    py_trees.blackboard.Blackboard.enable_activity_stream()
    blackboard = py_trees.blackboard.Client(name="test-setup")
    blackboard.register_key(
        key="datalayer", access=py_trees.common.Access.WRITE
    )
    blackboard.register_key(
        key="actor_id", access=py_trees.common.Access.WRITE
    )
    blackboard.datalayer = dl
    blackboard.actor_id = actor_id


@pytest.fixture
def dl() -> SqliteDataLayer:
    """Return a fresh in-memory SQLite DataLayer."""
    return SqliteDataLayer("sqlite:///:memory:")
