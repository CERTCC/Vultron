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
"""Architecture ratchet: every received tree's commit can be fanned out (#4113).

Every received tree that names a case runs a guarded ledger commit
(``create_receive_activity_tree``, CLP-10-006), and the CASE_MANAGER announces
each entry it commits to every active participant (SYNC-02-003).  The commit
reads the ``SyncActivityPort`` off the blackboard, so the port has to travel
the whole way: the inbox port factory gives it, the use case accepts it, and
the use case hands it to the ``BTBridge`` that runs the tree.

A use case that broke the chain at any link used to commit without fan-out,
with only a DEBUG line (``OfferActorToCaseReceivedUseCase`` took no port;
``VALIDATE_REPORT`` and ``REJECT_INVITE_ACTOR_TO_CASE`` were given none).  The
fan-out node now raises a ``VultronWiringError`` instead, and these checks find
the broken link statically, before a demo has to.

"Runs a tree" is approximated by "calls ``BTBridge``": a received use case
that builds a bridge is the one whose commit can be reached, and a bridge
that is not given the port cannot fan out whatever the tree commits.  The
dispatcher-side link (every semantic's factory supplies the port) is pinned in
``test/adapters/driving/fastapi/test_inbox_handler.py``.
"""

import ast
import inspect

import pytest

from test.architecture import _corpus
from vultron.semantic_registry import use_case_map

_RECEIVED_ROOT = (
    _corpus.REPO_ROOT / "vultron" / "core" / "use_cases" / "received"
)


def _calls(matches) -> list[tuple[str, int, ast.Call]]:
    calls: list[tuple[str, int, ast.Call]] = []
    for path, tree in _corpus.all_trees(under=_RECEIVED_ROOT):
        rel = str(path.relative_to(_corpus.REPO_ROOT))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and matches(node.func):
                calls.append((rel, node.lineno, node))
    return calls


def _bridge_calls() -> list[tuple[str, int, ast.Call]]:
    return _calls(
        lambda func: isinstance(func, ast.Name) and func.id == "BTBridge"
    )


def _execute_with_setup_calls() -> list[tuple[str, int, ast.Call]]:
    return _calls(
        lambda func: (
            isinstance(func, ast.Attribute)
            and func.attr == "execute_with_setup"
        )
    )


def _keyword(call: ast.Call, name: str) -> ast.keyword | None:
    return next((kw for kw in call.keywords if kw.arg == name), None)


def test_received_side_builds_bridges():
    """Guard against a vacuous pass: the scan must find the bridges."""
    assert len(_bridge_calls()) > 10


@pytest.mark.spec("SYNC-02-003")
def test_every_received_use_case_accepts_sync_port():
    """The dispatcher calls ``use_case_class(dl, event, **ports)``.

    Every received use case is given the sync port (as it is given the
    ``WireRenderPort``), so a constructor that does not take it fails at
    dispatch with a ``TypeError`` — and one that takes it but drops it is
    caught by the bridge check below.
    """
    missing = sorted(
        uc.__name__
        for uc in set(use_case_map().values())
        if "sync_port" not in inspect.signature(uc).parameters
    )
    assert missing == [], (
        f"received use cases that do not accept sync_port: {missing}"
    )


@pytest.mark.spec("SYNC-02-003")
@pytest.mark.spec("BT-14-001")
def test_every_received_bridge_is_given_the_sync_port():
    """Each ``BTBridge(...)`` under ``received/`` passes ``sync_port=``.

    The value must not be the literal ``None``: a bridge built that way is the
    portless commit this ratchet exists to prevent.
    """
    offenders: list[str] = []
    for rel, lineno, call in _bridge_calls():
        kw = _keyword(call, "sync_port")
        if kw is None or (
            isinstance(kw.value, ast.Constant) and kw.value.value is None
        ):
            offenders.append(f"{rel}:{lineno}")
    assert offenders == [], (
        "BTBridge built without a sync_port; its tree's ledger commit cannot"
        f" be fanned out (SYNC-02-003): {offenders}"
    )


def test_sync_port_travels_by_one_idiom():
    """The port goes to the ``BTBridge`` constructor, never as tree context.

    A context kwarg is written to the blackboard as given, skipping the
    bridge's per-store rebinding (``port_for_store``), and a second idiom is
    a second place for the port to go missing.
    """
    offenders = [
        f"{rel}:{lineno}"
        for rel, lineno, call in _execute_with_setup_calls()
        if _keyword(call, "sync_port") is not None
    ]
    assert offenders == [], (
        "pass sync_port to BTBridge(...), not execute_with_setup(...):"
        f" {offenders}"
    )
