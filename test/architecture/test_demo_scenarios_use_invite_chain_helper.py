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

"""Architecture ratchet (DEMOMA-17-001): a scenario joins an invitee through
``run_case_invite_chain``, never by writing the invite chain out by hand.

The chain — a participant triggers the invite, the invitee's DataLayer is
polled for the CASE_MANAGER's Invite, the invitee answers it, and (on an
accept) its case replica is awaited — was hand-nested in
the ``vultron/demo/scenario/*_demo.py`` files, each copy free to drift
(#4192, PR #3886).  ``vultron/demo/helpers/invite_chain.py`` now owns it with
the variants as parameters.

A scenario module that calls any link of the chain directly is re-introducing
a hand-nested copy, so this test fails on the first such call.

Spec: ``specs/multi-actor-demo.yaml`` DEMOMA-17-001.
"""

import ast
from pathlib import Path

import pytest

from test.architecture import _corpus

_SCENARIO_DIR = _corpus.REPO_ROOT / "vultron" / "demo" / "scenario"

#: The links of the invite chain; each is owned by ``invite_chain.py``.
_CHAIN_LINKS = frozenset(
    {
        "invite_actor_to_case",
        "find_case_invite_for_actor",
        "accept_case_invite",
        "reject_case_invite",
    }
)


def _callee_name(call: ast.Call) -> str:
    func = call.func
    if isinstance(func, ast.Attribute):
        return func.attr
    return getattr(func, "id", "")


def _hand_written_chain_links(tree: ast.AST) -> list[tuple[int, str]]:
    """Return ``(line, callee)`` for every direct call to a chain link."""
    return [
        (node.lineno, _callee_name(node))
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and _callee_name(node) in _CHAIN_LINKS
    ]


def _scenario_trees() -> list[tuple[Path, ast.AST]]:
    return list(_corpus.all_trees(_SCENARIO_DIR))


def test_scenario_corpus_is_non_empty() -> None:
    """A zero-target gate proves nothing."""
    assert _scenario_trees(), f"no scenario files under {_SCENARIO_DIR}"


@pytest.mark.parametrize(
    ("path", "tree"), _scenario_trees(), ids=lambda v: getattr(v, "name", "")
)
def test_scenario_does_not_hand_write_the_invite_chain(
    path: Path, tree: ast.AST
) -> None:
    offenders = _hand_written_chain_links(tree)
    assert not offenders, (
        f"{path.name} calls the invite chain directly at "
        + ", ".join(f"line {ln} ({name})" for ln, name in offenders)
        + "; use vultron.demo.helpers.invite_chain.run_case_invite_chain"
        " (DEMOMA-17-001, #4192)."
    )


def test_ratchet_detects_a_hand_nested_chain() -> None:
    """The detector fires on the shape it exists to forbid."""
    source = (
        "def phase(c):\n"
        "    ActorSession(c).invite_actor_to_case(invitee_id=i)\n"
        "    with demo_gate('x'):\n"
        "        invite_id = find_case_invite_for_actor(client=c)\n"
        "        ActorSession(c).accept_case_invite(invite_id=invite_id)\n"
        "        ActorSession(c).reject_case_invite(invite_id=invite_id)\n"
    )
    assert [
        n for _, n in _hand_written_chain_links(_corpus.parse_inline(source))
    ] == [
        "invite_actor_to_case",
        "find_case_invite_for_actor",
        "accept_case_invite",
        "reject_case_invite",
    ]
