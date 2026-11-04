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

"""Does a named actor hold a role in a case? (ADR-0153, CM-02-011)

:class:`ActorHoldsRoleInCaseNode` asks that of an actor the message names,
through the one sanctioned predicate.  The role is read from the roster for
each delivery, so a role granted or removed mid-case changes the answer.
"""

import py_trees
import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.role_condition import ActorHoldsRoleInCaseNode
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.enums.roles import CVDRole
from vultron.errors import VultronWiringError

CASE_ID = "https://example.org/cases/role-condition"
OWNER_ID = "https://example.org/actors/owner"
VENDOR_ID = "https://example.org/actors/vendor"
RECEIVER_ID = "https://example.org/actors/receiver"


def _store(*, with_case: bool = True) -> SqliteDataLayer:
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=RECEIVER_ID)
    if not with_case:
        return dl
    case = VulnerabilityCase(
        id_=CASE_ID, name="Role condition", attributed_to=OWNER_ID
    )
    for actor, roles in ((OWNER_ID, [CVDRole.CASE_OWNER]), (VENDOR_ID, [])):
        participant = CaseParticipant(
            id_=f"{CASE_ID}/participants/{actor.rsplit('/', 1)[-1]}",
            attributed_to=actor,
            context=CASE_ID,
            case_roles=list(roles),
        )
        dl.create(participant)
        case.case_participants.append(participant.id_)
        case.actor_participant_index[actor] = participant.id_
    dl.create(case)
    return dl


def _run(
    node: py_trees.behaviour.Behaviour, dl: SqliteDataLayer
) -> py_trees.behaviour.Behaviour:
    BTBridge(datalayer=dl).execute_with_setup(tree=node, actor_id=RECEIVER_ID)
    return node


@pytest.mark.spec("CM-02-011")
def test_the_role_holder_is_admitted() -> None:
    node = _run(
        ActorHoldsRoleInCaseNode(
            actor_id=OWNER_ID, role=CVDRole.CASE_OWNER, case_id=CASE_ID
        ),
        _store(),
    )

    assert node.status is Status.SUCCESS


@pytest.mark.spec("CM-02-011")
def test_an_actor_without_the_role_is_refused() -> None:
    """The subject holds a participant record, but not this role."""
    node = _run(
        ActorHoldsRoleInCaseNode(
            actor_id=VENDOR_ID, role=CVDRole.CASE_OWNER, case_id=CASE_ID
        ),
        _store(),
    )

    assert node.status is Status.FAILURE
    assert "does not hold CASE_OWNER" in node.feedback_message


@pytest.mark.spec("CM-02-011")
def test_a_case_the_store_does_not_hold_is_a_failure_not_an_error() -> None:
    """An actor holds no role in a case this store has no replica of."""
    node = _run(
        ActorHoldsRoleInCaseNode(
            actor_id=OWNER_ID, role=CVDRole.CASE_OWNER, case_id=CASE_ID
        ),
        _store(with_case=False),
    )

    assert node.status is Status.FAILURE


@pytest.mark.spec("CM-02-011")
def test_no_case_at_all_is_refused_with_the_reason() -> None:
    """Neither the constructor nor the blackboard names a case."""
    node = _run(
        ActorHoldsRoleInCaseNode(actor_id=OWNER_ID, role=CVDRole.CASE_OWNER),
        _store(),
    )

    assert node.status is Status.FAILURE
    assert "no case to read" in node.feedback_message


@pytest.mark.spec("CM-02-011")
def test_the_case_comes_from_the_blackboard_when_the_node_names_none() -> None:
    dl = _store()
    node = ActorHoldsRoleInCaseNode(actor_id=OWNER_ID, role=CVDRole.CASE_OWNER)
    BTBridge(datalayer=dl).execute_with_setup(
        tree=node, actor_id=RECEIVER_ID, case_id=CASE_ID
    )

    assert node.status is Status.SUCCESS


@pytest.mark.spec("ARCH-24-003")
@pytest.mark.spec("HP-01-037")
def test_the_authority_role_is_refused_at_construction() -> None:
    """Authority has one asker, and it is not this node.

    Asked about the executing actor this node would be a second authority
    condition node, and a role passed as a parameter is invisible to the
    detector both authority ratchets share, so the role is refused here
    rather than left to a reviewer to notice.
    """
    with pytest.raises(VultronWiringError, match="CASE_MANAGER"):
        ActorHoldsRoleInCaseNode(
            actor_id=OWNER_ID,
            role=CVDRole.CASE_MANAGER,
            case_id=CASE_ID,
        )
