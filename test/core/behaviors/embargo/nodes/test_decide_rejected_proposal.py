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

"""``DecideRejectedEmbargoProposalNode``: the owner's Reject decides (EP-08-003).

Only the case owner's Reject decides an open proposal; it returns EM to the
prior terms (``REVISE → ACTIVE``, EJ) or to no embargo (``PROPOSED → NONE``,
ER) and forgets the proposal in one lifecycle call.  Before #3915 the
received path only pruned the proposal, leaving the case in REVISE with
nothing proposed.
"""

from typing import cast

import py_trees
import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.embargo.nodes.reject_proposed import (
    DecideRejectedEmbargoProposalNode,
)
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.services.embargo_lifecycle import TransitionMode
from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

from .conftest import (
    CASE_MANAGER_ACTOR,
    make_case_and_embargo,
    setup_blackboard,
)

OWNER = CASE_MANAGER_ACTOR
PARTICIPANT = "https://example.org/users/participant"


def _revising_case(
    dl: SqliteDataLayer, suffix: str, *, em_state: EM = EM.REVISE
) -> tuple[VulnerabilityCase, str, str]:
    """A case with an active embargo and one open revision of it."""
    case, active = make_case_and_embargo(
        suffix, em_state=em_state, attributed_to=OWNER
    )
    revision = as_EmbargoEvent(
        id_=f"{case.id_}/embargo_events/revision",
        context=case.id_,
        end_time=days_from_now_utc(90),
    )
    dl.create(active)
    dl.create(revision)
    case.proposed_embargoes.append(revision.id_)
    case.pending_embargo_proposal_index[revision.id_] = (
        f"{case.id_}/embargo_proposals/1"
    )
    dl.create(case)
    return case, active.id_, revision.id_


def _tick(node: DecideRejectedEmbargoProposalNode) -> Status:
    bt = py_trees.trees.BehaviourTree(root=node)
    bt.setup()
    bt.tick()
    return node.status


def _case(dl: SqliteDataLayer, case_id: str) -> VulnerabilityCase:
    return cast(VulnerabilityCase, dl.read(case_id))


@pytest.mark.spec("EP-08-003")
@pytest.mark.spec("EMB-18-001")
@pytest.mark.parametrize(
    "mode", [TransitionMode.STRICT, TransitionMode.OBSERVED]
)
def test_the_owners_reject_of_a_revision_returns_to_the_prior_terms(
    dl: SqliteDataLayer, mode: TransitionMode
) -> None:
    case, active_id, revision_id = _revising_case(dl, f"ej-{mode.value}")
    setup_blackboard(dl, actor_id=OWNER)

    status = _tick(
        DecideRejectedEmbargoProposalNode(
            case_id=case.id_,
            embargo_id=revision_id,
            rejecting_actor_id=OWNER,
            transition_mode=mode,
        )
    )

    assert status is Status.SUCCESS
    decided = _case(dl, case.id_)
    assert decided.current_status.em.state == EM.ACTIVE
    assert decided.active_embargo_id == active_id
    assert decided.proposed_embargo_ids == []
    assert decided.pending_embargo_proposal_index == {}


@pytest.mark.spec("EP-08-003")
def test_the_owners_reject_of_an_initial_proposal_leaves_no_embargo(
    dl: SqliteDataLayer,
) -> None:
    case, _, proposal_id = _revising_case(dl, "er", em_state=EM.PROPOSED)
    case.active_embargo = None
    dl.save(case)
    setup_blackboard(dl, actor_id=OWNER)

    status = _tick(
        DecideRejectedEmbargoProposalNode(
            case_id=case.id_, embargo_id=proposal_id, rejecting_actor_id=OWNER
        )
    )

    assert status is Status.SUCCESS
    decided = _case(dl, case.id_)
    assert decided.current_status.em.state == EM.NONE
    assert decided.proposed_embargo_ids == []


@pytest.mark.spec("EP-08-003")
def test_a_participants_reject_is_consent_and_decides_nothing(
    dl: SqliteDataLayer,
) -> None:
    case, _, revision_id = _revising_case(dl, "consent")
    setup_blackboard(dl, actor_id=OWNER)

    node = DecideRejectedEmbargoProposalNode(
        case_id=case.id_,
        embargo_id=revision_id,
        rejecting_actor_id=PARTICIPANT,
    )

    assert _tick(node) is Status.SUCCESS
    assert "consent" in (node.feedback_message or "")
    kept = _case(dl, case.id_)
    assert kept.current_status.em.state == EM.REVISE
    assert kept.proposed_embargo_ids == [revision_id]
    assert revision_id in kept.pending_embargo_proposal_index


@pytest.mark.spec("EP-08-003")
def test_a_reject_of_what_is_no_longer_proposed_changes_nothing(
    dl: SqliteDataLayer,
) -> None:
    """A repeated Reject, or one naming the active embargo, is a no-op here."""
    case, active_id, revision_id = _revising_case(dl, "repeat")
    setup_blackboard(dl, actor_id=OWNER)

    node = DecideRejectedEmbargoProposalNode(
        case_id=case.id_, embargo_id=active_id, rejecting_actor_id=OWNER
    )

    assert _tick(node) is Status.SUCCESS
    kept = _case(dl, case.id_)
    assert kept.current_status.em.state == EM.REVISE
    assert kept.proposed_embargo_ids == [revision_id]


@pytest.mark.spec("EMB-04-002")
def test_strict_ej_with_pxa_set_fails_and_writes_nothing(
    dl: SqliteDataLayer,
) -> None:
    case, _, revision_id = _revising_case(dl, "pxa")
    case.append_case_status(pxa_state=CS_pxa.Pxa)
    dl.save(case)
    setup_blackboard(dl, actor_id=OWNER)

    status = _tick(
        DecideRejectedEmbargoProposalNode(
            case_id=case.id_, embargo_id=revision_id, rejecting_actor_id=OWNER
        )
    )

    assert status is Status.FAILURE
    kept = _case(dl, case.id_)
    assert kept.current_status.em.state == EM.REVISE
    assert kept.proposed_embargo_ids == [revision_id]


def test_an_unknown_case_fails(dl: SqliteDataLayer) -> None:
    setup_blackboard(dl, actor_id=OWNER)
    node = DecideRejectedEmbargoProposalNode(
        case_id="https://example.org/cases/missing",
        embargo_id="https://example.org/cases/missing/embargo_events/x",
        rejecting_actor_id=OWNER,
    )
    assert _tick(node) is Status.FAILURE
