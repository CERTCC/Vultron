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

"""The owner's rejection nodes (EP-08-003, MSM-07-009).

The effect of the case owner's ``Reject(EmbargoEvent, target=Case)``
(ADR-0122): it returns EM to the prior terms (``REVISE → ACTIVE``, EJ) or to
no embargo (``PROPOSED → NONE``, ER) and rejects the proposal in one
lifecycle call.  Only the owner sends the activity; the received tree's
sender guard establishes that, so the node itself checks no sender.
"""

from typing import NoReturn, cast

import py_trees
import pytest
from py_trees.common import Status

from test.support.embargo_register import propose
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.embargo.nodes import reject_proposed
from vultron.core.behaviors.embargo.nodes.reject_proposed import (
    DecideRejectedEmbargoProposalNode,
    EmbargoOutlivesDisclosureNode,
    OwnerRejectionAppliesNode,
)
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM
from vultron.core.states.embargo_register import EmbargoRegisterStatus
from vultron.errors import VultronInvalidStateTransitionError
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

from .conftest import (
    CASE_MANAGER_ACTOR,
    make_case_and_embargo,
    setup_blackboard,
)

OWNER = CASE_MANAGER_ACTOR
PARTICIPANT = "https://example.org/users/participant"


def _revising_case(
    dl: SqliteDataLayer, suffix: str, *, with_active: bool = True
) -> tuple[VulnerabilityCase, str, str]:
    """A case with an active embargo and one open revision of it (REVISE).

    With *with_active* false no embargo is in force, so the open proposal is
    an initial one (PROPOSED).
    """
    case, active = make_case_and_embargo(
        suffix,
        em_state=EM.ACTIVE if with_active else EM.NONE,
        attributed_to=OWNER,
    )
    revision = as_EmbargoEvent(
        id_=f"{case.id_}/embargo_events/revision",
        context=case.id_,
        end_time=days_from_now_utc(90),
    )
    dl.create(active)
    dl.create(revision)
    propose(case, revision)
    case.pending_embargo_proposal_index[revision.id_] = (
        f"{case.id_}/embargo_proposals/1"
    )
    dl.create(case)
    return case, active.id_, revision.id_


def _tick(node: py_trees.behaviour.Behaviour) -> Status:
    bt = py_trees.trees.BehaviourTree(root=node)
    bt.setup()
    bt.tick()
    return node.status


def _case(dl: SqliteDataLayer, case_id: str) -> VulnerabilityCase:
    return cast(VulnerabilityCase, dl.read(case_id))


@pytest.mark.spec("EP-08-003")
@pytest.mark.spec("EMB-18-001")
def test_the_owners_reject_of_a_revision_returns_to_the_prior_terms(
    dl: SqliteDataLayer,
) -> None:
    case, active_id, revision_id = _revising_case(dl, "ej")
    setup_blackboard(dl, actor_id=OWNER)

    status = _tick(
        DecideRejectedEmbargoProposalNode(
            case_id=case.id_, embargo_id=revision_id
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
    case, _, proposal_id = _revising_case(dl, "er", with_active=False)
    setup_blackboard(dl, actor_id=OWNER)

    status = _tick(
        DecideRejectedEmbargoProposalNode(
            case_id=case.id_, embargo_id=proposal_id
        )
    )

    assert status is Status.SUCCESS
    decided = _case(dl, case.id_)
    assert decided.current_status.em.state == EM.NONE
    assert decided.proposed_embargo_ids == []


@pytest.mark.spec("EP-08-003")
def test_the_node_checks_no_sender_and_writes_no_consent(
    dl: SqliteDataLayer,
) -> None:
    """Executed by any actor, the node rejects: the sender guard is upstream.

    It writes no consent row either (ADR-0122): the owner's rejection for the
    case is not its refusal as a participant.
    """
    case, active_id, revision_id = _revising_case(dl, "any-actor")
    setup_blackboard(dl, actor_id=PARTICIPANT)

    node = DecideRejectedEmbargoProposalNode(
        case_id=case.id_, embargo_id=revision_id
    )

    assert _tick(node) is Status.SUCCESS
    decided = _case(dl, case.id_)
    assert decided.current_status.em.state == EM.ACTIVE
    assert decided.active_embargo_id == active_id
    assert decided.proposed_embargo_ids == []


@pytest.mark.spec("EP-08-003")
def test_a_reject_of_what_is_no_longer_proposed_changes_nothing(
    dl: SqliteDataLayer,
) -> None:
    """A repeated Reject, or one naming the active embargo, is a no-op here."""
    case, active_id, revision_id = _revising_case(dl, "repeat")
    setup_blackboard(dl, actor_id=OWNER)

    node = DecideRejectedEmbargoProposalNode(
        case_id=case.id_, embargo_id=active_id
    )

    assert _tick(node) is Status.SUCCESS
    kept = _case(dl, case.id_)
    assert kept.current_status.em.state == EM.REVISE
    assert kept.proposed_embargo_ids == [revision_id]


@pytest.mark.spec("EMB-04-002")
@pytest.mark.spec("MSM-07-009")
def test_ej_with_pxa_set_records_the_reject_step(
    dl: SqliteDataLayer,
) -> None:
    """With P/X/A set the REJECT step is still recorded as decided.

    The prior terms stand only until the termination that follows in the
    same act; the node itself does not refuse (MSM-07-009).
    """
    case, active_id, revision_id = _revising_case(dl, "pxa")
    case.append_case_status(pxa=CS_pxa.Pxa)
    dl.save(case)
    setup_blackboard(dl, actor_id=OWNER)

    status = _tick(
        DecideRejectedEmbargoProposalNode(
            case_id=case.id_, embargo_id=revision_id
        )
    )

    assert status is Status.SUCCESS
    decided = _case(dl, case.id_)
    assert decided.embargo_register_status(revision_id) is (
        EmbargoRegisterStatus.REJECTED
    )
    assert decided.active_embargo_id == active_id


# ---------------------------------------------------------------------------
# OwnerRejectionAppliesNode: the guard trial (MSM-07-009)
# ---------------------------------------------------------------------------


@pytest.mark.spec("MSM-07-009")
@pytest.mark.parametrize("pxa", [CS_pxa.pxa, CS_pxa.Pxa, CS_pxa.pXA])
def test_the_rejection_and_its_termination_apply_and_nothing_is_written(
    dl: SqliteDataLayer, pxa: CS_pxa
) -> None:
    """The trial passes with or without P/X/A, and writes nothing."""
    case, _, revision_id = _revising_case(dl, f"trial-{pxa.name}")
    case.append_case_status(pxa=pxa)
    dl.save(case)
    before = _case(dl, case.id_).embargo_register
    setup_blackboard(dl, actor_id=OWNER)

    status = _tick(
        OwnerRejectionAppliesNode(case_id=case.id_, embargo_id=revision_id)
    )

    assert status is Status.SUCCESS
    assert _case(dl, case.id_).embargo_register == before


@pytest.mark.spec("MSM-07-009")
@pytest.mark.spec("EMB-13-005")
def test_a_termination_that_cannot_be_decided_refuses_the_rejection(
    dl: SqliteDataLayer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A refused TERMINATE refuses the act before either entry commits."""
    case, _, revision_id = _revising_case(dl, "trial-refused")
    case.append_case_status(pxa=CS_pxa.Pxa)
    dl.save(case)

    def _refuse(*_args: object) -> NoReturn:
        raise VultronInvalidStateTransitionError("termination refused")

    monkeypatch.setattr(reject_proposed, "decide_termination", _refuse)
    before = _case(dl, case.id_).embargo_register
    setup_blackboard(dl, actor_id=OWNER)

    node = OwnerRejectionAppliesNode(case_id=case.id_, embargo_id=revision_id)

    assert _tick(node) is Status.FAILURE
    assert "termination refused" in node.feedback_message
    assert _case(dl, case.id_).embargo_register == before


@pytest.mark.spec("MSM-07-009")
def test_a_reject_the_register_refuses_fails_the_trial(
    dl: SqliteDataLayer,
) -> None:
    """A REJECT naming the embargo in force, not a proposal, is refused."""
    case, active_id, _ = _revising_case(dl, "trial-not-open")
    setup_blackboard(dl, actor_id=OWNER)

    node = OwnerRejectionAppliesNode(case_id=case.id_, embargo_id=active_id)

    assert _tick(node) is Status.FAILURE


# ---------------------------------------------------------------------------
# EmbargoOutlivesDisclosureNode (EMB-04-002)
# ---------------------------------------------------------------------------


@pytest.mark.spec("EMB-04-002")
@pytest.mark.parametrize(
    ("pxa", "reject_first", "expected"),
    [
        (CS_pxa.Pxa, True, Status.SUCCESS),  # prior terms stand, P set
        (CS_pxa.pxa, True, Status.FAILURE),  # prior terms allowed
        (CS_pxa.Pxa, False, Status.FAILURE),  # revision still open
    ],
)
def test_the_embargo_outlives_disclosure_only_once_no_proposal_is_open(
    dl: SqliteDataLayer, pxa: CS_pxa, reject_first: bool, expected: Status
) -> None:
    case, _, revision_id = _revising_case(dl, f"outlives-{pxa.name}")
    case.append_case_status(pxa=pxa)
    dl.save(case)
    setup_blackboard(dl, actor_id=OWNER)
    if reject_first:
        assert (
            _tick(
                DecideRejectedEmbargoProposalNode(
                    case_id=case.id_, embargo_id=revision_id
                )
            )
            is Status.SUCCESS
        )

    assert _tick(EmbargoOutlivesDisclosureNode(case_id=case.id_)) is expected


def test_an_unknown_case_fails(dl: SqliteDataLayer) -> None:
    setup_blackboard(dl, actor_id=OWNER)
    node = DecideRejectedEmbargoProposalNode(
        case_id="https://example.org/cases/missing",
        embargo_id="https://example.org/cases/missing/embargo_events/x",
    )
    assert _tick(node) is Status.FAILURE
