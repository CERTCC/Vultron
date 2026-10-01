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
"""Ratchet: case-content recipients come from one shared selection.

CM-10-007 puts the active-participant check (CM-10-004, ADR-0114) in the
shared recipient selection that every case-content send uses, so no send
site can forget it.  A site that builds its recipient list by iterating the
roster's actor IDs (``case.actor_participant_index``) itself bypasses that
check: such a list is the whole roster, inert participants included.

The scan covers ``vultron/core/`` and flags three shapes (see
:func:`_flagged_nodes`): iterating the roster's actor IDs, collecting them
with ``list``/``set``/``sorted``, and a loop over participant records
(``.values()``, ``.items()``, ``iter_case_participants``) that collects each
record's ``attributed_to``.  A record loop that only looks something up is
not recipient selection and is not flagged.  The
shared selection's own module is the one exemption; if the implementation
moves it, move the exemption with it.  The retired roster-wide helper
``case_addressees`` must not come back under any import path.  See
``notes/case-joining.md`` and #4046.
"""

import ast

import pytest

from test.architecture import _corpus

#: Where the shared recipient selection lives.
_SHARED_SELECTION = {"vultron/core/participants/recipients.py"}

#: The retired roster-wide addressee helper (#4046).
_RETIRED_HELPER = "case_addressees"


#: Builtins that turn the roster mapping into a list of its actor IDs.
_COLLECTING_CALLS = {"list", "set", "frozenset", "tuple", "sorted"}

#: Iterables that yield participant records (or ids) rather than actor IDs.
_RECORD_ITERATORS = {"values", "items"}
_RECORD_HELPER = "iter_case_participants"


def _is_index(node: ast.expr) -> bool:
    """True for ``x.actor_participant_index`` or its ``getattr`` spelling."""
    if isinstance(node, ast.Attribute):
        return node.attr == "actor_participant_index"
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "getattr"
        and len(node.args) >= 2
        and isinstance(node.args[1], ast.Constant)
        and node.args[1].value == "actor_participant_index"
    )


def _index_method(node: ast.expr, names: set[str]) -> bool:
    """True for ``<index>.<name>()`` with *name* in *names*."""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in names
        and _is_index(node.func.value)
    )


def _iterates_roster_ids(node: ast.expr) -> bool:
    """True when iterating *node* yields roster actor IDs.

    The index itself, its ``getattr`` spelling, or its ``.keys()``.
    """
    return _is_index(node) or _index_method(node, {"keys"})


def _iterates_records(node: ast.expr) -> bool:
    """True when iterating *node* yields participant records or their ids."""
    if _index_method(node, _RECORD_ITERATORS):
        return True
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == _RECORD_HELPER
    )


def _reads_actor_id(node: ast.AST) -> bool:
    """True when *node* reads a participant's ``attributed_to`` (its actor ID)."""
    for sub in ast.walk(node):
        if isinstance(sub, ast.Attribute) and sub.attr == "attributed_to":
            return True
        if (
            isinstance(sub, ast.Call)
            and isinstance(sub.func, ast.Name)
            and sub.func.id == "getattr"
            and len(sub.args) >= 2
            and isinstance(sub.args[1], ast.Constant)
            and sub.args[1].value == "attributed_to"
        ):
            return True
    return False


def _appends(nodes: list[ast.stmt]) -> bool:
    return any(
        isinstance(sub, ast.Call)
        and isinstance(sub.func, ast.Attribute)
        and sub.func.attr in {"append", "add", "extend"}
        for stmt in nodes
        for sub in ast.walk(stmt)
    )


def _flagged_nodes(tree: ast.AST) -> list[ast.AST]:
    """Every node in *tree* that builds a list of roster actor IDs itself.

    Three shapes:

    - a loop or comprehension over the roster's actor IDs (the index, its
      ``getattr`` spelling, or ``.keys()``);
    - ``list``/``set``/``sorted``/… of the same;
    - a loop or comprehension over participant records (index ``.values()``
      or ``.items()``, or ``iter_case_participants``) that collects each
      record's ``attributed_to`` — the actor ID — into a list.  A record
      loop that reads a role, a status, or returns one match is a lookup,
      not addressing, and is not flagged.
    """
    flagged: list[ast.AST] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.For, ast.AsyncFor)):
            if _iterates_roster_ids(node.iter) or (
                _iterates_records(node.iter)
                and _appends(node.body)
                and any(_reads_actor_id(stmt) for stmt in node.body)
            ):
                flagged.append(node.iter)
        elif isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp)):
            for gen in node.generators:
                if _iterates_roster_ids(gen.iter) or (
                    _iterates_records(gen.iter) and _reads_actor_id(node.elt)
                ):
                    flagged.append(gen.iter)
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in _COLLECTING_CALLS
            and node.args
            and _iterates_roster_ids(node.args[0])
        ):
            flagged.append(node)
    return flagged


def _roster_iteration_sites() -> list[str]:
    sites: list[str] = []
    for path, tree in _corpus.files_mentioning(
        "actor_participant_index",
        _RECORD_HELPER,
        under=_corpus.REPO_ROOT / "vultron" / "core",
    ):
        rel = path.relative_to(_corpus.REPO_ROOT).as_posix()
        if rel in _SHARED_SELECTION:
            continue
        sites.extend(
            f"{rel}:{_corpus.node_line(node)}" for node in _flagged_nodes(tree)
        )
    return sites


def _retired_helper_sites() -> list[str]:
    sites: list[str] = []
    for path, tree in _corpus.files_mentioning(
        _RETIRED_HELPER, under=_corpus.REPO_ROOT / "vultron"
    ):
        rel = path.relative_to(_corpus.REPO_ROOT).as_posix()
        for node in ast.walk(tree):
            named = (
                (isinstance(node, ast.Name) and node.id == _RETIRED_HELPER)
                or (
                    isinstance(node, ast.Attribute)
                    and node.attr == _RETIRED_HELPER
                )
                or (
                    isinstance(node, ast.FunctionDef)
                    and node.name == _RETIRED_HELPER
                )
                or (
                    isinstance(node, ast.alias)
                    and node.name == _RETIRED_HELPER
                )
            )
            if named:
                sites.append(f"{rel}:{getattr(node, 'lineno', '?')}")
    return sites


@pytest.mark.spec("CM-10-007")
def test_no_send_site_builds_recipients_from_the_raw_roster() -> None:
    """No code in ``vultron/core/`` lists roster actor IDs outside the shared selection."""
    sites = _roster_iteration_sites()
    assert sites == [], (
        "recipient list built from the raw roster, bypassing the shared"
        " active-participant selection (CM-10-007): " + ", ".join(sites)
    )


@pytest.mark.spec("CM-10-007")
def test_retired_roster_wide_addressee_helper_is_not_used() -> None:
    """``case_addressees`` (the whole roster, inert included) is gone from ``vultron/``."""
    sites = _retired_helper_sites()
    assert sites == [], (
        f"{_RETIRED_HELPER} selects the whole roster, inert participants"
        " included; use vultron.core.participants.recipients (CM-10-007): "
        + ", ".join(sites)
    )


def test_ratchet_flags_a_raw_roster_loop() -> None:
    """The roster-iteration detector is not vacuous, and spares lookups."""
    flagged_source = (
        "for a in case.actor_participant_index: pass\n"
        "x = [a for a in getattr(case, 'actor_participant_index', {})]\n"
        "for a in case.actor_participant_index.keys(): pass\n"
        "y = list(case.actor_participant_index)\n"
        "z = sorted(case.actor_participant_index.keys())\n"
        "for pid in case.actor_participant_index.values():\n"
        "    p = dl.read(pid)\n"
        "    uris.append(p.attributed_to)\n"
        "w = [p.attributed_to for p in iter_case_participants(case, dl)]\n"
    )
    assert len(_flagged_nodes(_corpus.parse_inline(flagged_source))) == 7

    lookup_source = (
        "for pid in case.actor_participant_index.values():\n"
        "    if dl.read(pid) is None: return False\n"
        "for p in iter_case_participants(case, dl):\n"
        "    if role in p.roles: return p.attributed_to\n"
        "ids = [a for a, pid in case.actor_participant_index.items()"
        " if pid == target]\n"
    )
    assert _flagged_nodes(_corpus.parse_inline(lookup_source)) == []
