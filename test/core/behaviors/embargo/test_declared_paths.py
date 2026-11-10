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

"""Who each received embargo tree admits and refuses (ADR-0153).

*Which* paths each tree declares is pinned once for the whole migrated
corpus, in ``test/core/behaviors/test_declared_received_paths.py``
(CS-22-001); this module asserts what that declaration *does*.  The stage
comes out of the tree the production factory builds, so its declaration, its
build-time case and its place among the door guards are production's rather
than a fixture's, and it is then ticked on its own, because a factory-built
tree cannot be ticked whole without a received activity for its intake node:

- the stage is one of the tree's door guards, so its refusal ends the
  delivery before any commit (CLP-10-010);
- a receiver on a path the declaration omits is refused, with the reason
  composed from the resolved path and the declaration (HP-01-005,
  HP-01-039);
- a receiver on *each* declared path is admitted — both arms of a two-path
  declaration, not just the first.

The reason is what makes a narrowed declaration safe to make: each wording
is true of the receiver it refuses, so the case's own CASE_MANAGER is never
told it is not the CASE_MANAGER (#5041).  What no test here can falsify is
the narrowing itself; that is a claim about who receives a message type, and
only an end-to-end delivery to a real roster answers it (see
``notes/`` on the announce tree's both-paths declaration).
"""

from collections.abc import Callable

import py_trees
import pytest
from py_trees.common import Status

from test.core.behaviors.embargo.nodes.conftest import (
    CASE_MANAGER_ACTOR,
    OTHER_PARTICIPANT_ACTOR,
    make_case_with_manager,
)
from test.support.act_runner import run_tree
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.received_path import (
    ReceivedPath,
    ReceivedPathNode,
    undeclared_path_reason,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    ReceivedActivityTree,
)
from vultron.core.behaviors.case_id_scope import CaseIdScope
from vultron.core.behaviors.embargo.announce_received_tree import (
    announce_embargo_received_tree,
)
from vultron.core.behaviors.embargo.announce_teardown_tree import (
    invite_to_embargo_on_case_tree,
    remove_embargo_from_case_tree,
)
from vultron.core.behaviors.embargo.answer_trees import (
    accept_invite_to_embargo_tree,
    reject_invite_to_embargo_tree,
)
from vultron.core.behaviors.embargo.invite_received_tree import (
    embargo_invite_fault_tree,
)
from vultron.core.behaviors.embargo.owner_decision_tree import (
    activate_embargo_on_case_tree,
    reject_embargo_proposal_on_case_tree,
)
from vultron.core.behaviors.embargo.withdrawal_tree import (
    withdraw_from_embargo_on_case_tree,
)
from vultron.core.models._helpers import days_from_now_utc, now_utc
from vultron.core.states.em import EM
from vultron.core.states.embargo_register import TerminationReason
from vultron.core.use_cases.received.embargo.accept import (
    AcceptInviteToEmbargoOnCaseReceivedUseCase,
)
from vultron.core.use_cases.received.embargo.announce import (
    AnnounceEmbargoEventToCaseReceivedUseCase,
)
from vultron.core.use_cases.received.embargo.invite import (
    InviteToEmbargoOnCaseReceivedUseCase,
)
from vultron.core.use_cases.received.embargo.owner_decision import (
    ActivateEmbargoOnCaseReceivedUseCase,
    RejectEmbargoProposalOnCaseReceivedUseCase,
)
from vultron.core.use_cases.received.embargo.reject import (
    RejectInviteToEmbargoOnCaseReceivedUseCase,
)
from vultron.core.use_cases.received.embargo.remove import (
    RemoveEmbargoEventFromCaseReceivedUseCase,
)
from vultron.core.use_cases.received.embargo.withdraw import (
    WithdrawFromEmbargoOnCaseReceivedUseCase,
)

_STRANGER = "https://example.org/actors/stranger"
_INVITE = "https://example.org/activities/invite1"
_LEAVE = "https://example.org/activities/leave1"

#: The two declarations the embargo trees make.  No embargo type declares the
#: participant-replica path alone: an announcement reaches the manager too when
#: the manager is a participant of its own case, which is what the exchange
#: demos showed (HP-01-038).
_MANAGER_ONLY = frozenset({ReceivedPath.CASE_MANAGER})
_BOTH = frozenset(
    {ReceivedPath.CASE_MANAGER, ReceivedPath.PARTICIPANT_REPLICA}
)

#: A builder takes the case and its embargo and returns the built tree.
_Builder = Callable[[str, str], py_trees.behaviour.Behaviour]


def _accept(case_id: str, embargo_id: str) -> py_trees.behaviour.Behaviour:
    return accept_invite_to_embargo_tree(
        case_id=case_id,
        embargo_id=embargo_id,
        accepting_actor_id=OTHER_PARTICIPANT_ACTOR,
        invite_id=_INVITE,
        sender_rule=AcceptInviteToEmbargoOnCaseReceivedUseCase.sender_entitlement,
        now=now_utc(),
    )


def _reject_invite(
    case_id: str, embargo_id: str
) -> py_trees.behaviour.Behaviour:
    return reject_invite_to_embargo_tree(
        case_id=case_id,
        rejecting_actor_id=OTHER_PARTICIPANT_ACTOR,
        invite_id=_INVITE,
        embargo_id=embargo_id,
        sender_rule=RejectInviteToEmbargoOnCaseReceivedUseCase.sender_entitlement,
    )


def _activate(case_id: str, embargo_id: str) -> py_trees.behaviour.Behaviour:
    return activate_embargo_on_case_tree(
        case_id=case_id,
        embargo_id=embargo_id,
        sender_actor_id=OTHER_PARTICIPANT_ACTOR,
        sender_rule=ActivateEmbargoOnCaseReceivedUseCase.sender_entitlement,
    )


def _reject_proposal(
    case_id: str, embargo_id: str
) -> py_trees.behaviour.Behaviour:
    return reject_embargo_proposal_on_case_tree(
        case_id=case_id,
        embargo_id=embargo_id,
        sender_actor_id=OTHER_PARTICIPANT_ACTOR,
        sender_rule=RejectEmbargoProposalOnCaseReceivedUseCase.sender_entitlement,
    )


def _withdraw(case_id: str, embargo_id: str) -> py_trees.behaviour.Behaviour:
    return withdraw_from_embargo_on_case_tree(
        case_id=case_id,
        embargo_id=embargo_id,
        withdrawing_actor_id=OTHER_PARTICIPANT_ACTOR,
        activity_id=_LEAVE,
        sender_rule=WithdrawFromEmbargoOnCaseReceivedUseCase.sender_entitlement,
    )


def _announce(case_id: str, embargo_id: str) -> py_trees.behaviour.Behaviour:
    return announce_embargo_received_tree(
        case_id=case_id,
        embargo_id=embargo_id,
        sender_id=CASE_MANAGER_ACTOR,
        sender_rule=AnnounceEmbargoEventToCaseReceivedUseCase.sender_entitlement,
    )


def _invite(case_id: str, embargo_id: str) -> py_trees.behaviour.Behaviour:
    return invite_to_embargo_on_case_tree(
        case_id=case_id,
        invitee_id=OTHER_PARTICIPANT_ACTOR,
        invite_id=_INVITE,
        embargo_id=embargo_id,
        proposer_id=OTHER_PARTICIPANT_ACTOR,
        sender_actor_id=OTHER_PARTICIPANT_ACTOR,
        sender_rule=InviteToEmbargoOnCaseReceivedUseCase.sender_entitlement,
    )


def _remove(case_id: str, embargo_id: str) -> py_trees.behaviour.Behaviour:
    return remove_embargo_from_case_tree(
        case_id=case_id,
        embargo_id=embargo_id,
        sender_actor_id=CASE_MANAGER_ACTOR,
        termination_reason=TerminationReason.EARLY,
        terminated_at=days_from_now_utc(0),
        sender_rule=RemoveEmbargoEventFromCaseReceivedUseCase.sender_entitlement,
    )


#: ``(label, builder, declaration)`` for every received embargo tree
#: that declares its paths.  ``embargo_invite_fault_tree`` is deliberately
#: absent; see :func:`test_the_fault_tree_declares_no_paths`.  The
#: declaration repeated here is the one
#: ``test/core/behaviors/test_declared_received_paths.py`` pins for the whole
#: corpus; it is what each row probes against, and that module is what fails
#: if a tree changes it.
TREES: tuple[tuple[str, _Builder, frozenset[ReceivedPath]], ...] = (
    (
        "accept-invite",
        _accept,
        _MANAGER_ONLY,
    ),
    # The Reject of an Invite is also the CASE_MANAGER's own refusal to the
    # participant it turns away (EMB-02-004, EP-09-017), so its tree admits
    # that replica too even though only the manager records an answer.
    (
        "reject-invite",
        _reject_invite,
        _BOTH,
    ),
    (
        "activate",
        _activate,
        _MANAGER_ONLY,
    ),
    (
        "reject-proposal",
        _reject_proposal,
        _MANAGER_ONLY,
    ),
    (
        "withdraw",
        _withdraw,
        _MANAGER_ONLY,
    ),
    (
        "announce-embargo",
        _announce,
        _BOTH,
    ),
    (
        "invite",
        _invite,
        _BOTH,
    ),
    (
        "remove",
        _remove,
        _BOTH,
    ),
)

#: Who each declaration turns away, and the path the stage resolves there.
#: The manager-only trees refuse a replica, and the two-path trees refuse a
#: store holding no replica.  No embargo type declares the participant-replica
#: path alone, so no row turns away the case's own CASE_MANAGER.
_REFUSED: dict[frozenset[ReceivedPath], tuple[str, ReceivedPath]] = {
    _MANAGER_ONLY: ("replica", ReceivedPath.PARTICIPANT_REPLICA),
    _BOTH: ("stranger", ReceivedPath.NO_CASE),
}

#: The store role that puts a receiver on each path.
_ROLE_FOR_PATH: dict[ReceivedPath, str] = {
    ReceivedPath.CASE_MANAGER: "manager",
    ReceivedPath.PARTICIPANT_REPLICA: "replica",
    ReceivedPath.NO_CASE: "stranger",
}


def _store(role: str, suffix: str) -> tuple[str, str, str, SqliteDataLayer]:
    """A store for *role*: ``(case_id, embargo_id, actor_id, datalayer)``.

    ``manager`` and ``replica`` hold the same case, under the CASE_MANAGER's
    and a participant's own store (TB-06-007).  ``stranger`` holds no replica
    of it at all, which is the no-case path.
    """
    case, _, dl = make_case_with_manager(
        f"paths-{suffix}",
        em_state=EM.ACTIVE,
        store_actor_id=None if role == "manager" else OTHER_PARTICIPANT_ACTOR,
    )
    embargo_id = f"{case.id_}/embargo_events/e1"
    if role == "stranger":
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_STRANGER)
        return case.id_, embargo_id, _STRANGER, dl
    actor = (
        CASE_MANAGER_ACTOR if role == "manager" else OTHER_PARTICIPANT_ACTOR
    )
    return case.id_, embargo_id, actor, dl


def _path_stage(tree: py_trees.behaviour.Behaviour) -> ReceivedPathNode:
    (stage,) = [n for n in tree.iterate() if isinstance(n, ReceivedPathNode)]
    return stage


def _run_stage(
    label: str, builder: _Builder, role: str
) -> tuple[ReceivedPathNode, str]:
    """Run *builder*'s path stage in *role*'s store; return it and the case."""
    case_id, embargo_id, actor, dl = _store(role, f"{label}-{role}")
    tree = builder(case_id, embargo_id)
    stage = _path_stage(tree)
    # The door is the scope that seeds the stage's /case_id port.
    door = stage.parent
    assert isinstance(door, CaseIdScope) and door.case_id == case_id
    assert isinstance(tree, ReceivedActivityTree)
    assert door in tree.door_guards, (
        "the path stage is a door guard, so its refusal ends the tree before"
        " any commit (CLP-10-010)"
    )
    run_tree(BTBridge(datalayer=dl), tree=door, actor_id=actor)
    return stage, case_id


@pytest.mark.spec("HP-01-038")
@pytest.mark.spec("HP-01-041")
def test_the_fault_tree_declares_no_paths() -> None:
    """The malformed-Invite fault answers its sender on every path.

    Nothing about it is path-scoped: the ``Create(ProcessingFault)`` is the
    receiver's own answer wherever the Invite landed (MSM-05-001), and a
    misrouted Invite may land on a store holding no replica of the case it
    names.  Declaring the no-case path is not open either — an
    ``Invite(EmbargoEvent)`` is case-scoped, so it waits at the inbox's defer
    check instead (HP-01-041) — so the tree declares none and keeps its
    recorded emit exemption.
    """
    tree = embargo_invite_fault_tree("probe-failure", None)

    assert [n for n in tree.iterate() if isinstance(n, ReceivedPathNode)] == []


@pytest.mark.spec("HP-01-039")
@pytest.mark.spec("HP-01-005")
@pytest.mark.parametrize(
    ("label", "builder", "declared"),
    [pytest.param(*row, id=row[0]) for row in TREES],
)
def test_a_receiver_off_the_declared_path_is_refused(
    label: str, builder: _Builder, declared: frozenset[ReceivedPath]
) -> None:
    """The refusal, and the reason the one composer gives for it.

    The expected wording comes from :func:`undeclared_path_reason` itself,
    so the reason each tree gives is the composed one and nothing beside it
    (HP-01-039).
    """
    role, refused_path = _REFUSED[declared]

    stage, case_id = _run_stage(label, builder, role)

    assert stage.status is Status.FAILURE
    assert stage.resolved_path is refused_path
    assert stage.feedback_message == undeclared_path_reason(
        refused_path, declared, case_id
    )
    # No embargo type declares a manager-free set today, so the composer's
    # other arm — the one that tells the case's own CASE_MANAGER that it *is*
    # the CASE_MANAGER — is pinned where it lives, in
    # `test/core/behaviors/case/test_received_path_stage.py`, rather than
    # asserted here against a configuration no row has (#5041).  The tripwire
    # for that changing is the `_REFUSED[declared]` lookup above, which raises
    # KeyError for a declaration shape this module has no row for.


@pytest.mark.spec("HP-01-037")
@pytest.mark.parametrize(
    ("label", "builder", "declared"),
    [pytest.param(*row, id=row[0]) for row in TREES],
)
def test_every_receiver_on_a_declared_path_is_admitted(
    label: str, builder: _Builder, declared: frozenset[ReceivedPath]
) -> None:
    """The complement, on *each* declared path, not just the first.

    A two-path declaration is the whole point of the Invite, Remove and
    Reject trees, so both of its arms are admitted here; checking one would
    leave the newly branched path unexercised.
    """
    for path in sorted(declared, key=lambda p: p.value):
        stage, _ = _run_stage(label, builder, _ROLE_FOR_PATH[path])

        assert stage.status is Status.SUCCESS, path
        assert stage.resolved_path is path
