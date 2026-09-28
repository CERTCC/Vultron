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

"""``ReadProposedEmbargoIdNode`` selects by earliest end, not by position.

The public-disclosure cascade (EMB-16-001) rejects *the* proposed embargo
when P/X/A flips while EM is PROPOSED.  With several proposals open the one
to reject first is the earliest-expiring (EP-08-002, ADR-0100, #3470); the
node used to read ``proposed_embargoes[0]``, which is arrival order.
"""

from datetime import timedelta

import py_trees
import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.embargo.nodes.reject_proposed import (
    ReadProposedEmbargoIdNode,
)
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.states.em import EM
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

from .conftest import CASE_MANAGER_ACTOR, setup_blackboard


def _proposed_case(
    dl: SqliteDataLayer, suffix: str, days: list[int]
) -> tuple[VulnerabilityCase, dict[int, str]]:
    """A PROPOSED case whose proposals are recorded in the order of *days*."""
    case = VulnerabilityCase(
        id_=f"https://example.org/cases/case_{suffix}",
        name=f"Test Case {suffix}",
        attributed_to=CASE_MANAGER_ACTOR,
    )
    case.append_case_status(em_state=EM.PROPOSED)
    ids: dict[int, str] = {}
    for d in days:
        embargo = as_EmbargoEvent(
            id_=f"{case.id_}/embargo_events/{d}d",
            context=case.id_,
            end_time=days_from_now_utc(d),
        )
        dl.create(embargo)
        case.proposed_embargoes.append(embargo.id_)
        ids[d] = embargo.id_
    dl.create(case)
    return case, ids


def _tick(node: ReadProposedEmbargoIdNode) -> Status:
    bt = py_trees.trees.BehaviourTree(root=node)
    bt.setup()
    bt.tick()
    return node.status


@pytest.mark.spec("EP-08-002")
def test_reads_the_earliest_expiring_proposed_embargo(
    dl: SqliteDataLayer,
) -> None:
    """Recorded 60, 15, 30 days out: neither first nor last is the answer."""
    case, ids = _proposed_case(dl, "rpe-order", [60, 15, 30])
    setup_blackboard(dl, actor_id=CASE_MANAGER_ACTOR)

    node = ReadProposedEmbargoIdNode(case_id=case.id_)
    assert _tick(node) == Status.SUCCESS
    assert py_trees.blackboard.Blackboard.get("/embargo_id") == ids[15]


@pytest.mark.spec("EP-08-002")
def test_fails_rather_than_guess_when_a_proposal_cannot_be_ordered(
    dl: SqliteDataLayer,
) -> None:
    """A proposed id with no stored record is FAILURE with a reason, not a pick."""
    case, _ids = _proposed_case(dl, "rpe-ghost", [30])
    case.proposed_embargoes.append(f"{case.id_}/embargo_events/never-stored")
    dl.save(case)
    setup_blackboard(dl, actor_id=CASE_MANAGER_ACTOR)

    node = ReadProposedEmbargoIdNode(case_id=case.id_)
    assert _tick(node) == Status.FAILURE
    assert "never-stored" in node.feedback_message
    assert "Cannot order the proposed embargoes" in node.feedback_message


def test_fails_when_nothing_is_proposed(dl: SqliteDataLayer) -> None:
    case, _ids = _proposed_case(dl, "rpe-none", [])
    setup_blackboard(dl, actor_id=CASE_MANAGER_ACTOR)

    node = ReadProposedEmbargoIdNode(case_id=case.id_)
    assert _tick(node) == Status.FAILURE
    assert "No proposed embargoes" in node.feedback_message


# ``timedelta`` documents that ``days_from_now_utc`` measures from now; the
# ordering under test is between the three ends, not their absolute values.
assert timedelta(days=15) < timedelta(days=30) < timedelta(days=60)
