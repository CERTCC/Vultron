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

"""Architecture ratchet: a ledger dump route key is derived, never a literal.

A ``LedgerDumpTarget``'s ``route_key`` selects the *store* the ledger is read
from (ADR-0072); it is no longer decoration on a path into a store the whole
container shares.  A literal key therefore names whichever actor happens to be
hosted under that slug, which is the actor this run used only while the scenario
seeds deterministic named ids.  The moment an id is generated, the dump reports
"No case ledger entries for actor='finder'" while the finder's real store holds
the whole exchange — and the ledger is the only evidence a failed run leaves
behind, so the loss is silent and total.

The route key must come from something that knows which actor was used:
:func:`~vultron.demo.helpers.ledger_dump.replica_route_key` (from the client's
``actor_id``), :func:`~vultron.demo.helpers.ledger_dump.resolve_case_actor_route_key`
(from the case's participant index), or ``strip_id_prefix`` on an actor object.

Like ``test_demo_case_actor_clients_are_bound.py``, this reads the scenario
sources rather than running them: every test under ``test/demo/`` is marked
``integration`` and deselected by default, so a regression here would otherwise
only surface in the containerized Demo Integration tier.

Issue: #2484 (phase8-literal-ledger-keys-0)
"""

import ast
from pathlib import Path

import pytest

from test.architecture import _corpus
from vultron.demo.helpers.ledger_dump import replica_route_key
from vultron.demo.utils import DataLayerClient

_SCENARIO_DIR = _corpus.REPO_ROOT / "vultron" / "demo" / "scenario"

#: The one route key a literal may legitimately spell.  A dedicated CaseActor
#: container hosts exactly one actor, ``case-actor`` (CP-08-002), so the slug is
#: fixed by the deployment rather than by what this run happened to seed.
_ALLOWED_LITERAL_KEYS = frozenset({"case-actor"})

#: Scenario ASTs from the shared corpus, keyed by path (TB-13-003).  Built at
#: import time so ``parametrize`` can enumerate the scenarios by name.
_SCENARIO_TREES = {
    path: tree
    for path, tree in _corpus.all_trees(under=_SCENARIO_DIR)
    if path.name != "__init__.py"
}


def _route_key_arg(call: ast.Call) -> ast.expr | None:
    """Return the ``route_key`` argument node of a ``LedgerDumpTarget`` call."""
    for kw in call.keywords:
        if kw.arg == "route_key":
            return kw.value
    # Positional: (actor_name, client, route_key, ...)
    if len(call.args) >= 3:
        return call.args[2]
    return None


def _literal_route_keys(tree: ast.AST) -> list[tuple[int, str]]:
    """Return ``(lineno, key)`` for each ``LedgerDumpTarget`` with a literal key."""
    offenders: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        callee = (
            func.attr
            if isinstance(func, ast.Attribute)
            else getattr(func, "id", "")
        )
        if callee != "LedgerDumpTarget":
            continue
        arg = _route_key_arg(node)
        if not isinstance(arg, ast.Constant) or not isinstance(arg.value, str):
            continue
        if arg.value in _ALLOWED_LITERAL_KEYS:
            continue
        offenders.append((node.lineno, arg.value))
    return offenders


@pytest.mark.parametrize(
    "scenario", sorted(_SCENARIO_TREES), ids=lambda p: p.name
)
def test_ledger_route_keys_are_not_literals(scenario: Path) -> None:
    """Every ``LedgerDumpTarget`` route key must be derived, not hard-coded."""
    offenders = _literal_route_keys(_SCENARIO_TREES[scenario])
    assert not offenders, (
        f"{scenario.relative_to(_corpus.REPO_ROOT)} passes literal route key(s)"
        f" {offenders} to LedgerDumpTarget. The route key selects the store"
        " (ADR-0072), so a literal reads whichever actor is hosted under that"
        " slug and the dump silently reports an empty ledger. Derive it:"
        " replica_route_key(client, <fallback>)."
    )


def test_the_check_can_actually_fail() -> None:
    """Guard the guard: a literal key must be detected.

    A source-reading ratchet that matches nothing is worse than no ratchet,
    because it reports success.
    """
    tree = _corpus.parse_inline(
        'targets = [LedgerDumpTarget("finder", finder_client, "finder")]\n'
    )
    assert _literal_route_keys(tree) == [(1, "finder")]


def test_derived_and_allowed_keys_are_accepted() -> None:
    """A derived key, and the fixed ``case-actor`` slug, must not be flagged."""
    tree = _corpus.parse_inline(
        "targets = [\n"
        '    LedgerDumpTarget("finder", c, replica_route_key(c, "finder")),\n'
        '    LedgerDumpTarget("case-actor", ca, "case-actor"),\n'
        '    LedgerDumpTarget("v", v, route_key=derived),\n'
        "]\n"
    )
    assert _literal_route_keys(tree) == []


class TestReplicaRouteKey:
    """Unit tests for the derivation helper itself."""

    def test_uses_the_clients_own_actor_id(self) -> None:
        client = DataLayerClient(
            base_url="http://finder:7999/api/v2",
            actor_id="http://finder:7999/api/v2/actors/finder-9f3a",
        )
        assert replica_route_key(client, "finder") == "finder-9f3a"

    def test_ignores_the_fallback_when_the_client_is_bound(self) -> None:
        """The fallback must not win over a real, differing actor id.

        This is the whole point: a generated id and a seed-name literal disagree,
        and the id is the one whose store holds the ledger.
        """
        client = DataLayerClient(
            base_url="http://vendor:7999/api/v2",
            actor_id="http://vendor:7999/api/v2/actors/vendor-2",
        )
        assert replica_route_key(client, "vendor") == "vendor-2"

    def test_falls_back_when_the_client_is_unbound(self) -> None:
        """An unbound client keeps today's behaviour rather than raising.

        The dump runs in scenario teardown, where the ledger is the last
        evidence available; a best-effort read beats an exception.
        """
        client = DataLayerClient(base_url="http://finder:7999/api/v2")
        assert replica_route_key(client, "finder") == "finder"
