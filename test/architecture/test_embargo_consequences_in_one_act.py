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

"""A later node that commits an embargo consequence runs in its act's transaction.

The stub re-issue (``ReissueStubInvitesNode``, CM-11-016) and a proposal's
relay (``RelayEmbargoInviteToEachNode`` and its subclasses, EP-09-002) commit
consequences of the act before them in the tree.  The act and those
consequences commit as one or not at all (CLP-07-015, ADR-0146), so each such
node MUST sit under an ``ActTransaction`` that also holds the act.

The walk builds every received-side tree (``_received_tree_builds``) and
every embargo trigger tree (the factories
``test_embargo_trigger_writes_are_case_manager_gated`` names), and finds each
such node with no ``ActTransaction`` ancestor.  The **pinned exemption set**
:data:`OUTSIDE_AN_ACT` names the ones that are not a later node of an
embargo act, each with its reason; it is held to equality in both
directions (ARCH-18-001), so a new unwrapped later node fails, and so does
a row the code no longer needs.

A received embargo act's own entry is one of its act's writes too: every
received embargo tree that commits runs its guarded commit under the same
``ActTransaction`` (ADR-0151), with no exemption.
"""

from collections.abc import Iterator

import py_trees
import pytest

from test.architecture._received_tree_builds import built_received_trees
from test.architecture.test_embargo_trigger_writes_are_case_manager_gated import (
    _FACTORIES as _TRIGGER_FACTORIES,
)
from test.architecture.test_received_tree_case_manager_gate import (
    _assert_pinned,
)
from vultron.core.behaviors.act_transaction import ActTransaction
from vultron.core.behaviors.case.nodes.stub_reissue import (
    ReissueStubInvitesNode,
)
from vultron.core.behaviors.embargo.nodes.relay import (
    RelayEmbargoInviteToEachNode,
)

pytestmark = pytest.mark.spec("CLP-07-015")

_B = "vultron/core/behaviors"

_LATER_NODES = (ReissueStubInvitesNode, RelayEmbargoInviteToEachNode)

#: ``(module, factory, node class)`` of each later-node class that runs
#: outside an ``ActTransaction``, with the reason.
OUTSIDE_AN_ACT: dict[tuple[str, str, str], str] = {
    (
        f"{_B}/case/accept_invite_tree.py",
        "create_accept_invite_actor_to_case_tree",
        "RelayOpenProposalsToJoinerNode",
    ): "a case tree (the stub Accept's join), not an embargo act; #4959",
    (
        f"{_B}/case/case_participant_received_tree.py",
        "create_add_case_participant_received_tree",
        "InviteReinstatedParticipantToEmbargoNode",
    ): "a case tree (a reinstatement), not an embargo act; #4959",
    (
        f"{_B}/case/case_proposal_received_tree.py",
        "create_case_proposal_received_tree",
        "RelayCreationTimeRevisionNode",
    ): "case creation; the relay keeps its stored marker; #4959",
    (
        f"{_B}/embargo/answer_trees.py",
        "accept_invite_to_embargo_tree",
        "ReinviteLateAccepterNode",
    ): (
        "the re-invite is the act itself, not a later node: its Invite and"
        " row commit in the node's own transaction"
    ),
}


def _ancestors(
    node: py_trees.behaviour.Behaviour,
) -> Iterator[py_trees.behaviour.Behaviour]:
    parent = node.parent
    while parent is not None:
        yield parent
        parent = parent.parent


def _outside_an_act(
    tree: py_trees.behaviour.Behaviour,
) -> set[str]:
    return {
        type(node).__name__
        for node in tree.iterate()
        if isinstance(node, _LATER_NODES)
        and not any(isinstance(a, ActTransaction) for a in _ancestors(node))
    }


@pytest.mark.spec("ARCH-18-001")
def test_received_later_nodes_run_in_their_acts_transaction() -> None:
    actual = frozenset(
        (rel, factory, name)
        for (rel, factory), tree in built_received_trees().items()
        for name in _outside_an_act(tree)
    )
    _assert_pinned(
        "later embargo-consequence node outside an ActTransaction",
        actual,
        frozenset(OUTSIDE_AN_ACT),
        "run the act and the node in one ActTransaction"
        " (as_one_act=True, CLP-07-015)",
    )


@pytest.mark.parametrize("factory", sorted(_TRIGGER_FACTORIES))
def test_trigger_later_nodes_run_in_their_acts_transaction(
    factory: str,
) -> None:
    assert _outside_an_act(_TRIGGER_FACTORIES[factory]()) == set()


def test_the_walk_finds_later_nodes_inside_an_act() -> None:
    """Guard against a vacuous walk: the wrapped trees are seen too."""
    inside = {
        (rel, factory)
        for (rel, factory), tree in built_received_trees().items()
        for node in tree.iterate()
        if isinstance(node, _LATER_NODES)
        and any(isinstance(a, ActTransaction) for a in _ancestors(node))
    }
    for wrapped in (
        (
            f"{_B}/embargo/owner_decision_tree.py",
            "activate_embargo_on_case_tree",
        ),
        (
            f"{_B}/embargo/owner_decision_tree.py",
            "reject_embargo_proposal_on_case_tree",
        ),
        (
            f"{_B}/embargo/announce_teardown_tree.py",
            "remove_embargo_from_case_tree",
        ),
        (
            f"{_B}/embargo/announce_teardown_tree.py",
            "invite_to_embargo_on_case_tree",
        ),
        (f"{_B}/embargo/answer_trees.py", "accept_invite_to_embargo_tree"),
    ):
        assert wrapped in inside, wrapped


_GUARDED_COMMIT = "GuardedCommitCaseLedgerEntryBT"


def _commits_in_an_act(
    tree: py_trees.behaviour.Behaviour,
) -> list[bool]:
    """For each guarded commit in *tree*, whether an ActTransaction holds it."""
    return [
        any(isinstance(a, ActTransaction) for a in _ancestors(node))
        for node in tree.iterate()
        if node.name == _GUARDED_COMMIT
    ]


@pytest.mark.spec("CLP-07-015")
def test_a_received_embargo_act_commits_its_own_entry_in_its_act() -> None:
    """A received embargo act's own entry commits in the same transaction as
    its consequences, so the act succeeds or fails as a whole (ADR-0151)."""
    embargo_trees = {
        key: _commits_in_an_act(tree)
        for key, tree in built_received_trees().items()
        if key[0].startswith(f"{_B}/embargo/")
    }
    committing = {key for key, found in embargo_trees.items() if found}
    outside = {key for key, found in embargo_trees.items() if not all(found)}

    assert outside == set(), (
        "received embargo trees whose own entry commits outside the act's"
        f" transaction: {sorted(outside)}; pass as_one_act=True"
    )
    # Guard against a vacuous walk: every committing embargo tree is seen.
    assert {
        (
            f"{_B}/embargo/withdrawal_tree.py",
            "withdraw_from_embargo_on_case_tree",
        ),
        (f"{_B}/embargo/answer_trees.py", "accept_invite_to_embargo_tree"),
        (f"{_B}/embargo/answer_trees.py", "reject_invite_to_embargo_tree"),
        (
            f"{_B}/embargo/announce_teardown_tree.py",
            "invite_to_embargo_on_case_tree",
        ),
        (
            f"{_B}/embargo/announce_teardown_tree.py",
            "remove_embargo_from_case_tree",
        ),
        (
            f"{_B}/embargo/owner_decision_tree.py",
            "activate_embargo_on_case_tree",
        ),
        (
            f"{_B}/embargo/owner_decision_tree.py",
            "reject_embargo_proposal_on_case_tree",
        ),
    } <= committing
