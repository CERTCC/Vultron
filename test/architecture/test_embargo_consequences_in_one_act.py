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

"""Every node that commits after an act runs in that act's transaction.

The CASE_MANAGER commits a received act's own entry, the case-file changes
its entries carry and every consequence a later node in the act's tree
commits in one DataLayer transaction (CLP-07-015, ADR-0146): when any of
them fails, none of them is kept.  ``create_receive_activity_tree`` gives
every received tree that commits to a case that shape by default,
``ActTransaction[GuardedCommit, *replica_effects, CaseManagerGate]``, and a
tree runs outside it only by naming a registered ``OneActExemption``.

The walk builds every received-side tree (``_received_tree_builds``) and
every embargo trigger tree (the factories
``test_embargo_trigger_writes_are_case_manager_gated`` names), and checks
three things, each held to equality with a pinned set in both directions
(ARCH-18-001), so a new unwrapped node fails and so does a row the code no
longer needs:

- every received tree whose guarded commit runs outside an
  ``ActTransaction`` names its one-act exemption
  (:data:`ONE_ACT_EXEMPT_TREES`), and every registered exemption is used;
- every node after a guarded commit, in the tree that commits it, sits in
  the ``ActTransaction`` that holds the commit;
- every known later-consequence node (:data:`_LATER_NODES`) sits under an
  ``ActTransaction`` wherever it appears, including in a tree with no
  guarded commit of its own (case creation).  :data:`OUTSIDE_AN_ACT` names
  the ones that do not, each with its reason.
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
from vultron.core.behaviors.act_transaction import (
    ONE_ACT_EXEMPTIONS,
    ActTransaction,
)
from vultron.core.behaviors.case.nodes.stub_reissue import (
    ReissueStubInvitesNode,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    ReceivedActivityTree,
)
from vultron.core.behaviors.embargo.nodes.relay import (
    RelayEmbargoInviteToEachNode,
)

pytestmark = pytest.mark.spec("CLP-07-015")

_B = "vultron/core/behaviors"

_Site = tuple[str, str]

#: The name of the guarded commit of a received act's own entry.
_GUARDED_COMMIT = "GuardedCommitCaseLedgerEntryBT"

#: Later-consequence nodes checked wherever they appear: the stub re-issue
#: (CM-11-016) and a proposal's relay, with its subclasses (EP-09-002).
_LATER_NODES = (ReissueStubInvitesNode, RelayEmbargoInviteToEachNode)

#: ``(module, factory)`` of each received tree whose guarded commit runs
#: outside an ``ActTransaction``, with the name of its registered one-act
#: exemption.  Empty: every received tree that commits runs as one act.
ONE_ACT_EXEMPT_TREES: dict[_Site, str] = {}

#: ``(module, factory, node class)`` of each later node that runs outside an
#: ``ActTransaction``, with the reason.
OUTSIDE_AN_ACT: dict[tuple[str, str, str], str] = {
    (
        f"{_B}/case/case_proposal_received_tree.py",
        "create_case_proposal_received_tree",
        "RelayCreationTimeRevisionNode",
    ): "case creation; the relay keeps its stored marker; #4984",
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


def _act_of(node: py_trees.behaviour.Behaviour) -> ActTransaction | None:
    """The nearest ``ActTransaction`` holding *node*, or ``None``."""
    return next(
        (a for a in _ancestors(node) if isinstance(a, ActTransaction)), None
    )


def _guarded_commits(
    tree: py_trees.behaviour.Behaviour,
) -> list[py_trees.behaviour.Behaviour]:
    return [node for node in tree.iterate() if node.name == _GUARDED_COMMIT]


def _after(
    commit: py_trees.behaviour.Behaviour,
) -> Iterator[py_trees.behaviour.Behaviour]:
    """Every node that runs after *commit* in the tree that commits it.

    The factory places the guarded commit as a child of the act block, or of
    the tree's root when the tree is exempt; the nodes after it are its
    later siblings there and everything under them.
    """
    parent = commit.parent
    assert parent is not None, "a guarded commit always has a parent"
    siblings = list(parent.children)
    for later in siblings[siblings.index(commit) + 1 :]:
        yield from later.iterate()


def _later_nodes_outside_their_act(
    tree: py_trees.behaviour.Behaviour,
) -> set[str]:
    """Class names of later nodes in *tree* not in their act's transaction."""
    outside: set[str] = set()
    for commit in _guarded_commits(tree):
        act = _act_of(commit)
        outside |= {
            type(node).__name__
            for node in _after(commit)
            if act is None or not any(a is act for a in _ancestors(node))
        }
    outside |= {
        type(node).__name__
        for node in tree.iterate()
        if isinstance(node, _LATER_NODES) and _act_of(node) is None
    }
    return outside


def _received_trees_in(
    tree: py_trees.behaviour.Behaviour,
) -> list[ReceivedActivityTree]:
    """*tree* and every received tree nested in it (the close-case arm)."""
    return [n for n in tree.iterate() if isinstance(n, ReceivedActivityTree)]


@pytest.mark.spec("ARCH-18-001")
def test_every_received_act_commits_its_own_entry_in_one_act() -> None:
    """A received tree's own entry commits inside an ``ActTransaction``
    unless the tree names a registered one-act exemption (ADR-0151)."""
    outside = frozenset(
        site
        for site, tree in built_received_trees().items()
        if any(_act_of(c) is None for c in _guarded_commits(tree))
    )
    _assert_pinned(
        "received tree whose own entry commits outside an ActTransaction",
        outside,
        frozenset(ONE_ACT_EXEMPT_TREES),
        "drop the one_act_exemption, or register one with its reason"
        " (CLP-07-015)",
    )


@pytest.mark.spec("ARCH-18-001")
def test_every_one_act_exemption_is_pinned_and_used() -> None:
    """Each exempt tree names the pinned exemption, and none is stale."""
    named = {
        site: received.one_act_exemption.name
        for site, tree in built_received_trees().items()
        for received in _received_trees_in(tree)
        if received.one_act_exemption is not None
    }
    assert named == ONE_ACT_EXEMPT_TREES
    assert set(named.values()) == set(ONE_ACT_EXEMPTIONS)


@pytest.mark.spec("ARCH-18-001")
def test_received_later_nodes_run_in_their_acts_transaction() -> None:
    actual = frozenset(
        (rel, factory, name)
        for (rel, factory), tree in built_received_trees().items()
        for name in _later_nodes_outside_their_act(tree)
    )
    _assert_pinned(
        "later node outside its act's ActTransaction",
        actual,
        frozenset(OUTSIDE_AN_ACT),
        "run the act and the node in one ActTransaction (CLP-07-015)",
    )


@pytest.mark.parametrize("factory", sorted(_TRIGGER_FACTORIES))
def test_trigger_later_nodes_run_in_their_acts_transaction(
    factory: str,
) -> None:
    assert _later_nodes_outside_their_act(_TRIGGER_FACTORIES[factory]()) == (
        set()
    )


def test_the_walk_finds_later_nodes_inside_an_act() -> None:
    """Guard against a vacuous walk: committing trees with later nodes in
    their act are seen, case trees and embargo trees alike."""
    inside = {
        site
        for site, tree in built_received_trees().items()
        for commit in _guarded_commits(tree)
        if (act := _act_of(commit)) is not None
        and any(
            any(a is act for a in _ancestors(node)) for node in _after(commit)
        )
    }
    assert {
        (
            f"{_B}/case/accept_invite_tree.py",
            "create_accept_invite_actor_to_case_tree",
        ),
        (
            f"{_B}/case/case_participant_received_tree.py",
            "create_add_case_participant_received_tree",
        ),
        (
            f"{_B}/case/receive_close_case_tree.py",
            "create_close_case_received_tree",
        ),
        (
            f"{_B}/case/ownership_transfer_tree.py",
            "create_propose_ownership_transfer_tree",
        ),
        (
            f"{_B}/note/add_note_received_tree.py",
            "create_add_note_to_case_received_tree",
        ),
        (f"{_B}/report/prioritize_tree.py", "create_engage_case_tree"),
        (
            f"{_B}/status/add_participant_status_tree.py",
            "add_participant_status_tree",
        ),
        (
            f"{_B}/embargo/owner_decision_tree.py",
            "activate_embargo_on_case_tree",
        ),
        (
            f"{_B}/embargo/announce_teardown_tree.py",
            "invite_to_embargo_on_case_tree",
        ),
        (
            f"{_B}/embargo/withdrawal_tree.py",
            "withdraw_from_embargo_on_case_tree",
        ),
    } <= inside
    # The named later-node classes are seen inside an act too.
    named_inside = {
        type(node).__name__
        for tree in built_received_trees().values()
        for node in tree.iterate()
        if isinstance(node, _LATER_NODES) and _act_of(node) is not None
    }
    assert {
        "RelayOpenProposalsToJoinerNode",
        "InviteReinstatedParticipantToEmbargoNode",
        "ReissueStubInvitesNode",
    } <= named_inside
