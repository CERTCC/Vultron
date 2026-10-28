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

"""The answer to a stamped ledger position is a factory default, run once.

``create_receive_activity_tree`` places the CASE_MANAGER's answer to the
``ledgerPosition`` a received activity stamps
(:func:`~vultron.core.behaviors.sync.ledger_position_stage.create_ledger_position_stage`,
SYNC-18-004, SYNC-18-005, SYNC-18-007) in every tree whose sender guard
names its sender and case; a tree goes without it only by naming a
registered ``LedgerPositionExemption`` (CLP-10-005).  These checks keep that
so:

1. **Pinned exemption set** ``LEDGER_POSITION_EXEMPTION_USES``: which tree
   passes each exemption (ARCH-18-001, ARCH-18-002).
2. The registry is the module's whole list, each entry with its reason.
3. Every received tree, built as it runs, holds the answer at most once,
   right after its door guards; no tree module composes it itself.
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
from vultron.core.behaviors.case.receive_activity_tree import (
    ReceivedActivityTree,
)
from vultron.core.behaviors.sync.ledger_position_stage import (
    LEDGER_POSITION_GATE_NAME,
)
from vultron.core.behaviors.sync.nodes import ledger_position
from vultron.core.behaviors.sync.nodes.ledger_position import (
    LEDGER_POSITION_EXEMPTIONS,
    LedgerPositionAnswer,
    LedgerPositionExemption,
)

_KEYWORD = "ledger_position_exemption"
_STAGE_BUILDER = "create_ledger_position_stage"
_FACTORY = "vultron/core/behaviors/case/receive_stages/decisions.py"

# permanent: SYNC-18-007 (each entry is a recorded exemption decision)
LEDGER_POSITION_EXEMPTION_USES: frozenset[tuple[str, str, str]] = frozenset(
    {
        # A Read(CaseLedgerEntry) is a position statement; its own tree
        # answers it, and a split one with nothing sent (SYNC-17-005).
        (
            "STATED_POSITION_ANSWERED_BY_TREE",
            "vultron/core/behaviors/sync/read_tree.py",
            "create_read_log_entry_tree",
        ),
    }
)


def _exemption_uses() -> frozenset[tuple[str, str, str]]:
    uses: set[tuple[str, str, str]] = set()
    for rel, scope, call in _receive_calls():
        for kw in call.keywords:
            if kw.arg != _KEYWORD:
                continue
            assert isinstance(kw.value, ast.Name), (
                f"{rel}:{scope}: pass a registered exemption constant from"
                " ledger_position.py, not an inline value"
            )
            uses.add((kw.value.id, rel, scope))
    return frozenset(uses)


def _stages(
    tree: py_trees.behaviour.Behaviour,
) -> list[py_trees.behaviour.Behaviour]:
    return [n for n in tree.iterate() if isinstance(n, LedgerPositionAnswer)]


@pytest.mark.spec("SYNC-18-007")
@pytest.mark.spec("ARCH-18-001")
def test_ledger_position_exemption_uses_are_pinned() -> None:
    actual = _exemption_uses()
    expected = LEDGER_POSITION_EXEMPTION_USES
    assert actual == expected, (
        f"NEW: {sorted(actual - expected)}; a new exemption use is a"
        " decision — pin it here with its reason."
        f" STALE: {sorted(expected - actual)}; remove it (ARCH-18-002)"
    )


@pytest.mark.spec("SYNC-18-007")
def test_the_exemption_set_is_closed_and_reasoned() -> None:
    constants = {
        name: value
        for name, value in inspect.getmembers(ledger_position)
        if isinstance(value, LedgerPositionExemption)
    }
    assert {c.name for c in constants.values()} == set(
        LEDGER_POSITION_EXEMPTIONS
    )
    for exemption in constants.values():
        assert LEDGER_POSITION_EXEMPTIONS[exemption.name] is exemption
    used = {constant for constant, _, _ in LEDGER_POSITION_EXEMPTION_USES}
    assert used == set(constants)


@pytest.mark.spec("CLP-10-005")
@pytest.mark.spec("SYNC-18-007")
def test_every_received_tree_answers_the_position_at_most_once() -> None:
    """A tree nesting a factory-built subtree (the close arm) still runs the
    answer once: the subtree has no sender guard of its own."""
    twice = {
        f"{rel}:{scope}": len(_stages(tree))
        for (rel, scope), tree in built_received_trees().items()
        if len(_stages(tree)) > 1
    }
    assert twice == {}


@pytest.mark.spec("SYNC-18-004")
@pytest.mark.spec("CLP-10-010")
def test_the_answer_follows_the_door_guards() -> None:
    """It runs once the delivery is admitted and before anything judges the
    act, so the act's outcome cannot decide whether it runs."""
    misplaced: list[str] = []
    placed = 0
    for (rel, scope), tree in built_received_trees().items():
        for received in tree.iterate():
            if not isinstance(received, ReceivedActivityTree):
                continue
            names = [child.name for child in received.children]
            if LEDGER_POSITION_GATE_NAME not in names:
                continue
            placed += 1
            index = names.index(LEDGER_POSITION_GATE_NAME)
            doors = len(received.door_guards)
            if index != doors or received.children[index - 1] not in (
                received.door_guards
            ):
                misplaced.append(f"{rel}:{scope} [{received.name}]")
    assert placed, "no received tree answers a stamped ledger position"
    assert misplaced == []


@pytest.mark.spec("CLP-10-005")
def test_only_the_factory_composes_the_answer() -> None:
    callers = {
        path.relative_to(_corpus.REPO_ROOT).as_posix()
        for path, tree in _corpus.files_mentioning(
            _STAGE_BUILDER, under=_corpus.REPO_ROOT / "vultron"
        )
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == _STAGE_BUILDER
    }
    assert callers == {_FACTORY}
