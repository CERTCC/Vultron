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

"""Every received tree carries the addressee door guard, or says why not.

``create_receive_activity_tree`` places
:class:`~vultron.core.behaviors.case.nodes.addressee.ActivityAddressedToReceiverNode`
in every tree it builds (HP-01-005, CLP-10-010); a tree leaves it out only by
passing a registered ``AddresseeExemption`` (#4832).  These checks keep that
the only way out, and keep the exception set closed and reasoned:

1. **Pinned exemption set** ``ADDRESSEE_EXEMPTION_USES``: which tree passes
   each exemption, held to equality in both directions (ARCH-18-001,
   ARCH-18-002), and every registered exemption is used by some tree.
2. The registry is the module's whole list: every ``AddresseeExemption``
   constant in ``addressee.py`` is registered, each with its own reason.
3. Every received tree, built as it runs, holds exactly one guard, unless
   its site is pinned as exempt; an exempt tree holds what its reason says
   stands in for the guard (:data:`STAND_INS`).
4. Every routed message hands its tree the activity whose ``to`` the guard
   reads.
5. **Pinned exemption set** ``OTHER_TO_COMPARISONS``: no received-side code
   compares an actor with a ``to`` list outside ``addressee.py``, so no tree
   or use case writes its own copy of the check; the retired per-handler
   helpers stay gone.
"""

import ast
import inspect

import py_trees
import pytest

from test.architecture import _corpus
from test.architecture._received_tree_builds import built_received_trees
from test.architecture.test_received_tree_case_manager_gate import (
    _receive_calls,
)
from vultron.core.behaviors.case.nodes import addressee
from vultron.core.behaviors.case.nodes.addressee import (
    ADDRESSEE_EXEMPTIONS,
    ActivityAddressedToReceiverNode,
    AddresseeExemption,
)
from vultron.core.behaviors.case.nodes.submit_report import (
    CheckOfferAddressedToReceiverNode,
)
from vultron.core.behaviors.embargo.invite_received_tree import (
    embargo_invite_fault_tree,
)
from vultron.core.behaviors.embargo.nodes.invite_fault import (
    EmitEmbargoInviteFaultNode,
)
from vultron.core.models.events.base import MessageSemantics
from vultron.semantic_registry import SEMANTIC_REGISTRY

_KEYWORD = "addressee_exemption"
_ADDRESSEE_MODULE = "vultron/core/behaviors/case/nodes/addressee.py"
_RECEIVED_SIDE = (
    _corpus.REPO_ROOT / "vultron" / "core" / "behaviors",
    _corpus.REPO_ROOT / "vultron" / "core" / "use_cases" / "received",
)
_TO_COMPARISON = "is_addressed_to"
_RETIRED_HELPERS = frozenset({"unaddressed_copy_refusal", "is_recipient"})
_C = "vultron/core/behaviors/case"
_E = "vultron/core/behaviors/embargo"

_Site = tuple[str, str]

# ---------------------------------------------------------------------------
# 5. Received-side calls of the ``to`` comparison outside addressee.py, each a
#    different question from "is this copy addressed to me".
# ---------------------------------------------------------------------------
# permanent: HP-01-012 (each entry asks about the sender, not the receiver)
OTHER_TO_COMPARISONS: frozenset[_Site] = frozenset(
    {
        # Whether the *sender* is an addressee of the request it answers
        # (HP-01-008 positions such as invitee or transferee).
        ("vultron/core/behaviors/sender_entitlement.py", "_confirm_addressee"),
    }
)

# ---------------------------------------------------------------------------
# 1. Which tree passes which exemption: (constant, module, top-level function).
# ---------------------------------------------------------------------------
# permanent: HP-01-005 (each entry is a recorded exemption decision, #4832)
ADDRESSEE_EXEMPTION_USES: frozenset[tuple[str, str, str]] = frozenset(
    {
        # CM-15-002: the report and the Offer are kept before the check.
        (
            "OFFER_REPORT_STORED_FIRST",
            f"{_C}/receive_report_case_tree.py",
            "create_receive_report_case_tree",
        ),
        (
            "OFFER_REPORT_STORED_FIRST",
            f"{_C}/receive_report_case_tree.py",
            "create_offer_received_without_report_tree",
        ),
        # The close arm is a subtree of CloseCaseBT, which runs the guard.
        (
            "ENCLOSING_TREE_ADDRESSEE_CHECK",
            f"{_C}/receive_close_case_tree.py",
            "create_close_case_received_tree",
        ),
        # A misrouted Invite names no single addressee (EP-09-010).
        (
            "MISROUTED_EMBARGO_INVITE",
            f"{_E}/invite_received_tree.py",
            "embargo_invite_fault_tree",
        ),
    }
)

#: The built trees that run no guard at all, and the node standing in for it.
#: A subtree exemption (the close arm) is not here: its enclosing tree, built
#: by the same function, holds the guard.
STAND_INS: dict[_Site, type[py_trees.behaviour.Behaviour]] = {
    (
        f"{_C}/receive_report_case_tree.py",
        "create_receive_report_case_tree",
    ): CheckOfferAddressedToReceiverNode,
    (
        f"{_C}/receive_report_case_tree.py",
        "create_offer_received_without_report_tree",
    ): CheckOfferAddressedToReceiverNode,
    (
        f"{_E}/invite_received_tree.py",
        "embargo_invite_fault_tree",
    ): EmitEmbargoInviteFaultNode,
}


def _branches(value: ast.expr) -> list[ast.expr]:
    """The values *value* may take: both arms of a conditional, recursively."""
    if isinstance(value, ast.IfExp):
        return _branches(value.body) + _branches(value.orelse)
    return [value]


def _exemption_uses() -> frozenset[tuple[str, str, str]]:
    """Each registered exemption constant a received tree passes."""
    uses: set[tuple[str, str, str]] = set()
    for rel, scope, call in _receive_calls():
        for kw in call.keywords:
            if kw.arg != _KEYWORD:
                continue
            for value in _branches(kw.value):
                if isinstance(value, ast.Constant) and value.value is None:
                    continue
                assert isinstance(value, ast.Name), (
                    f"{rel}:{scope}: pass a registered exemption constant"
                    " from addressee.py (or None), not an inline value"
                )
                uses.add((value.id, rel, scope))
    return frozenset(uses)


def _registered_constants() -> dict[str, AddresseeExemption]:
    """The ``AddresseeExemption`` constants ``addressee.py`` defines."""
    return {
        name: value
        for name, value in inspect.getmembers(addressee)
        if isinstance(value, AddresseeExemption)
    }


def _guards(tree: py_trees.behaviour.Behaviour) -> int:
    return sum(
        isinstance(n, ActivityAddressedToReceiverNode) for n in tree.iterate()
    )


@pytest.mark.spec("HP-01-005")
@pytest.mark.spec("HP-01-012")
@pytest.mark.spec("ARCH-18-001")
def test_addressee_exemption_uses_are_pinned() -> None:
    actual = _exemption_uses()
    assert actual == ADDRESSEE_EXEMPTION_USES, (
        f"NEW: {sorted(actual - ADDRESSEE_EXEMPTION_USES)}; a new exemption"
        " use is a decision — pin it here with its reason."
        f" STALE: {sorted(ADDRESSEE_EXEMPTION_USES - actual)}; remove it"
        " (ARCH-18-002)"
    )


@pytest.mark.spec("HP-01-005")
@pytest.mark.spec("HP-01-012")
def test_the_exemption_set_is_closed_and_reasoned() -> None:
    """Every constant is registered, used, and carries its own reason."""
    constants = _registered_constants()
    assert {c.name for c in constants.values()} == set(ADDRESSEE_EXEMPTIONS)
    for exemption in constants.values():
        assert ADDRESSEE_EXEMPTIONS[exemption.name] is exemption
    reasons = [c.reason for c in constants.values()]
    assert len(set(reasons)) == len(reasons), "each exemption has its reason"
    used = {constant for constant, _, _ in ADDRESSEE_EXEMPTION_USES}
    assert used == set(constants), (
        f"registered but unused: {sorted(set(constants) - used)};"
        f" used but not registered: {sorted(used - set(constants))}"
    )


@pytest.mark.spec("HP-01-005")
@pytest.mark.spec("HP-01-012")
@pytest.mark.spec("CLP-10-010")
def test_every_received_tree_carries_the_guard_unless_exempt() -> None:
    trees = built_received_trees()
    unguarded = {site for site, tree in trees.items() if _guards(tree) == 0}
    assert unguarded == set(STAND_INS), (
        f"trees without the addressee guard: {sorted(unguarded)}; expected"
        f" only the exempt {sorted(STAND_INS)}"
    )
    doubled = sorted(site for site, tree in trees.items() if _guards(tree) > 1)
    assert not doubled, f"trees running the guard twice: {doubled}"


@pytest.mark.spec("HP-01-005")
@pytest.mark.spec("HP-01-012")
@pytest.mark.parametrize("site", sorted(STAND_INS), ids=lambda s: s[1])
def test_an_exempt_tree_holds_its_stand_in(site: _Site) -> None:
    tree = built_received_trees()[site]
    stand_in = STAND_INS[site]
    assert any(isinstance(n, stand_in) for n in tree.iterate()), (
        f"{site[1]} is exempt from the addressee guard but holds no"
        f" {stand_in.__name__}"
    )


@pytest.mark.spec("HP-01-005")
@pytest.mark.spec("HP-01-012")
def test_every_routed_message_carries_the_activity_the_guard_reads() -> None:
    """The guard reads ``to`` off the event's activity.

    A registry entry that leaves ``include_activity`` off hands the tree an
    event with no activity, which names no recipient, so every delivery of
    that message would be refused as an unaddressed copy (the ledger
    ``Announce``/``Reject`` were, until #4832).
    """
    missing = {
        entry.semantics
        for entry in SEMANTIC_REGISTRY
        if not entry.include_activity
    }
    # ``UNKNOWN`` refuses in its use case and runs no tree to check.
    assert missing == {MessageSemantics.UNKNOWN}, (
        f"entries without include_activity: {sorted(map(str, missing))}"
    )


@pytest.mark.spec("HP-01-005")
@pytest.mark.spec("HP-01-012")
def test_an_addressed_invite_fault_tree_carries_the_guard() -> None:
    """The fault tree is exempt only for a misrouting (EP-09-010)."""
    tree = embargo_invite_fault_tree(
        "failure-class", "https://example.org/cases/c", addressed=True
    )
    assert _guards(tree) == 1


def _to_comparison_sites() -> frozenset[_Site]:
    """``(module, enclosing function)`` of each received-side ``to`` check."""
    sites: set[_Site] = set()
    for root in _RECEIVED_SIDE:
        for path, tree in _corpus.files_mentioning(_TO_COMPARISON, under=root):
            rel = path.relative_to(_corpus.REPO_ROOT).as_posix()
            if rel == _ADDRESSEE_MODULE:
                continue
            for func in ast.walk(tree):
                if not isinstance(
                    func, (ast.FunctionDef, ast.AsyncFunctionDef)
                ):
                    continue
                for call in ast.walk(func):
                    if (
                        isinstance(call, ast.Call)
                        and _corpus.callee_name(call.func) == _TO_COMPARISON
                    ):
                        sites.add((rel, func.name))
    return frozenset(sites)


@pytest.mark.spec("HP-01-012")
@pytest.mark.spec("CS-22-001")
def test_no_received_side_code_writes_its_own_addressee_check() -> None:
    """The shared definition is the only receiver-addressing comparison."""
    actual = _to_comparison_sites()
    assert actual == OTHER_TO_COMPARISONS, (
        f"NEW: {sorted(actual - OTHER_TO_COMPARISONS)}; read"
        " addressed_to_receiver() / named_in_to() from addressee.py instead"
        " (HP-01-012), or pin a check that asks a different question."
        f" STALE: {sorted(OTHER_TO_COMPARISONS - actual)} (ARCH-18-002)"
    )


@pytest.mark.spec("HP-01-012")
def test_the_retired_addressee_helpers_stay_gone() -> None:
    defined = sorted(
        (path.relative_to(_corpus.REPO_ROOT).as_posix(), node.name)
        for path, tree in _corpus.files_mentioning(
            *_RETIRED_HELPERS, under=_corpus.REPO_ROOT / "vultron"
        )
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in _RETIRED_HELPERS
    )
    assert not defined, f"a per-handler addressee check is back: {defined}"
