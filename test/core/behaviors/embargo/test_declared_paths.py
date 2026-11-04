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

"""What each received embargo tree declares, and who it refuses (ADR-0153).

Every received embargo tree declares the paths it handles once, as the
factory's ``paths`` argument (HP-01-038).  Two things follow, and both are
pinned here:

- the declaration itself, tree by tree, so a tree that quietly widens or
  narrows the receivers it serves fails;
- the disposition of a delivery whose receiver is on a path the declaration
  omits: the path stage refuses it, with a reason composed from the resolved
  path and the declaration, and the tree ends there because the stage is a
  door guard (HP-01-005, HP-01-039, CLP-10-010).

The reason is what makes a replica-only or manager-only declaration safe to
make: each wording is true of the receiver it refuses, so the case's own
CASE_MANAGER is never told it is not the CASE_MANAGER (#5041).
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

#: The two declarations the embargo trees make.
_MANAGER_ONLY = frozenset({ReceivedPath.CASE_MANAGER})
_REPLICA_ONLY = frozenset({ReceivedPath.PARTICIPANT_REPLICA})
_BOTH = frozenset(
    {ReceivedPath.CASE_MANAGER, ReceivedPath.PARTICIPANT_REPLICA}
)

#: A builder takes the case and its embargo and returns the built tree.
_Builder = Callable[[str, str], py_trees.behaviour.Behaviour]

#: ``(module path, function)`` of a production factory, as
#: ``received_tree_factories()`` keys it.
_Site = tuple[str, str]


def _site(factory: Callable[..., object]) -> _Site:
    """The corpus key of *factory*, read off the function itself."""
    return (factory.__module__.replace(".", "/") + ".py", factory.__name__)


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


#: ``(label, builder, declaration)`` for every received embargo tree that
#: declares its paths.  ``embargo_invite_fault_tree`` is deliberately absent;
#: see :func:`test_the_fault_tree_declares_no_paths`.
TREES: tuple[tuple[str, _Builder, frozenset[ReceivedPath], _Site], ...] = (
    (
        "accept-invite",
        _accept,
        _MANAGER_ONLY,
        _site(accept_invite_to_embargo_tree),
    ),
    # The Reject of an Invite is also the CASE_MANAGER's own refusal to the
    # participant it turns away (EMB-02-004, EP-09-017), so its tree admits
    # that replica too even though only the manager records an answer.
    (
        "reject-invite",
        _reject_invite,
        _BOTH,
        _site(reject_invite_to_embargo_tree),
    ),
    (
        "activate",
        _activate,
        _MANAGER_ONLY,
        _site(activate_embargo_on_case_tree),
    ),
    (
        "reject-proposal",
        _reject_proposal,
        _MANAGER_ONLY,
        _site(reject_embargo_proposal_on_case_tree),
    ),
    (
        "withdraw",
        _withdraw,
        _MANAGER_ONLY,
        _site(withdraw_from_embargo_on_case_tree),
    ),
    (
        "announce-embargo",
        _announce,
        _REPLICA_ONLY,
        _site(announce_embargo_received_tree),
    ),
    (
        "invite",
        _invite,
        _BOTH,
        _site(invite_to_embargo_on_case_tree),
    ),
    (
        "remove",
        _remove,
        _BOTH,
        _site(remove_embargo_from_case_tree),
    ),
)

#: Who each declaration turns away, and the path the stage resolves there.
#: The manager-only trees refuse a replica, the replica-only tree refuses the
#: case's own CASE_MANAGER, and the two-path trees refuse a store holding no
#: replica.
_REFUSED: dict[frozenset[ReceivedPath], tuple[str, ReceivedPath]] = {
    _MANAGER_ONLY: ("replica", ReceivedPath.PARTICIPANT_REPLICA),
    _REPLICA_ONLY: ("manager", ReceivedPath.CASE_MANAGER),
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
    assert isinstance(tree, ReceivedActivityTree)
    assert stage in tree.door_guards, (
        "the path stage is a door guard, so its refusal ends the tree before"
        " any commit (CLP-10-010)"
    )
    BTBridge(datalayer=dl).execute_with_setup(tree=stage, actor_id=actor)
    return stage, case_id


#: The one embargo received tree that declares no paths, with its reason in
#: :func:`test_the_fault_tree_declares_no_paths`.
_DECLARES_NOTHING = (
    "vultron/core/behaviors/embargo/invite_received_tree.py",
    "embargo_invite_fault_tree",
)


@pytest.mark.spec("HP-01-038")
@pytest.mark.spec("ARCH-18-001")
def test_every_embargo_received_tree_is_covered() -> None:
    """:data:`TREES` covers every embargo received-tree factory there is.

    Keyed on the discovered corpus rather than on this hand-written list, so
    a tenth embargo tree cannot slip past its declaration pin — the
    hand-maintained-subject-list failure of #5535.  Each factory is either
    in :data:`TREES` or is the fault tree, which declares nothing.
    """
    from test.architecture._received_tree_builds import (
        received_tree_factories,
    )

    discovered = {
        site
        for site in received_tree_factories()
        if site[0].startswith("vultron/core/behaviors/embargo/")
    }
    covered = {site for _, _, _, site in TREES}

    assert discovered, "no embargo received-tree factory found at all"
    assert discovered - {_DECLARES_NOTHING} == covered, (
        "every embargo received tree is pinned here or named as the one that"
        f" declares nothing: discovered {sorted(discovered)}, covered"
        f" {sorted(covered)}"
    )


@pytest.mark.spec("HP-01-038")
@pytest.mark.parametrize(
    ("label", "builder", "declared"),
    [pytest.param(*row[:3], id=row[0]) for row in TREES],
)
def test_each_tree_declares_the_paths_it_handles(
    label: str, builder: _Builder, declared: frozenset[ReceivedPath]
) -> None:
    """The declaration, tree by tree: widening or narrowing it fails here."""
    case_id, embargo_id, _, _ = _store("manager", f"decl-{label}")

    stage = _path_stage(builder(case_id, embargo_id))

    assert stage.declared == declared


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
    [pytest.param(*row[:3], id=row[0]) for row in TREES],
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
    if ReceivedPath.CASE_MANAGER not in declared:
        # A manager-free declaration refuses the case's own CASE_MANAGER, so
        # the clause is true of it and what the reason names as missing is a
        # branch, not the role (#5041).
        assert "is the CASE_MANAGER of case" not in stage.feedback_message
        assert stage.feedback_message.startswith("the CASE_MANAGER of case")
        assert "this message type does not address" in stage.feedback_message


@pytest.mark.spec("HP-01-037")
@pytest.mark.parametrize(
    ("label", "builder", "declared"),
    [pytest.param(*row[:3], id=row[0]) for row in TREES],
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
