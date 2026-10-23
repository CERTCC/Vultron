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

The scan covers ``vultron/core/`` and flags four shapes (see
:func:`_flagged_nodes`): iterating or ``*``-unpacking the roster's actor IDs
(directly or through a name bound to the index), collecting them with
``list``/``set``/``sorted``, collecting the actor-ID key of an ``.items()``
loop, and a loop over participant records (``.values()``, ``.items()``,
``case_participants``, ``iter_case_participants``) that collects each
record's ``attributed_to``.  A loop that only looks something up (it
matches one participant ID, or collects something other than actor IDs) is
not recipient selection and is not flagged.  The shared selection's own
module is the one exemption; if the implementation moves it, move the
exemption with it.  The retired roster-wide helper ``case_addressees`` must
not come back under any import path.  See
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

#: Index methods that yield participant records (or ids) rather than actor IDs.
_RECORD_ITERATORS = {"values", "items"}
_RECORD_HELPER = "iter_case_participants"
#: The case attribute that lists participant records (or their ids).
_RECORD_LIST = "case_participants"


def _index_aliases(tree: ast.AST) -> set[str]:
    """Names bound to the roster index anywhere in *tree* (``idx = c.index``)."""
    aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and _is_index(node.value, set()):
            aliases.update(
                t.id for t in node.targets if isinstance(t, ast.Name)
            )
        elif (
            isinstance(node, (ast.AnnAssign, ast.NamedExpr))
            and node.value is not None
            and _is_index(node.value, set())
            and isinstance(node.target, ast.Name)
        ):
            aliases.add(node.target.id)
    return aliases


def _is_index(node: ast.expr, aliases: set[str]) -> bool:
    """True for ``x.actor_participant_index``, its ``getattr`` spelling, or an alias."""
    if isinstance(node, ast.Name):
        return node.id in aliases
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


def _index_method(node: ast.expr, names: set[str], aliases: set[str]) -> bool:
    """True for ``<index>.<name>()`` with *name* in *names*."""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in names
        and _is_index(node.func.value, aliases)
    )


def _iterates_roster_ids(node: ast.expr, aliases: set[str]) -> bool:
    """True when iterating *node* yields roster actor IDs.

    The index itself, its ``getattr`` spelling, an alias, or its ``.keys()``.
    """
    return _is_index(node, aliases) or _index_method(node, {"keys"}, aliases)


def _iterates_records(node: ast.expr, aliases: set[str]) -> bool:
    """True when iterating *node* yields participant records or their ids."""
    if _index_method(node, _RECORD_ITERATORS, aliases):
        return True
    if isinstance(node, ast.Attribute) and node.attr == _RECORD_LIST:
        return True
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "getattr"
        and len(node.args) >= 2
        and isinstance(node.args[1], ast.Constant)
        and node.args[1].value == _RECORD_LIST
    ):
        return True
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == _RECORD_HELPER
    )


def _items_key(
    target: ast.expr, iter_: ast.expr, aliases: set[str]
) -> tuple[str, str | None] | None:
    """The ``(key, value)`` names of ``for <key>, <pid> in <index>.items()``.

    *key* is the actor ID; *value* (the participant ID) is ``None`` when it
    is not a plain name.
    """
    if (
        _index_method(iter_, {"items"}, aliases)
        and isinstance(target, ast.Tuple)
        and len(target.elts) == 2
        and isinstance(target.elts[0], ast.Name)
    ):
        value = target.elts[1]
        return target.elts[0].id, (
            value.id if isinstance(value, ast.Name) else None
        )
    return None


def _matches_value(tests: list[ast.expr], value: str | None) -> bool:
    """True when a test compares the participant ID for equality.

    ``[a for a, pid in index.items() if pid == target]`` is a reverse
    lookup — the actor of one participant — not a recipient list.
    """
    if value is None:
        return False
    return any(
        isinstance(sub, ast.Compare)
        and all(isinstance(op, (ast.Eq, ast.Is)) for op in sub.ops)
        and any(
            isinstance(side, ast.Name) and side.id == value
            for side in [sub.left, *sub.comparators]
        )
        for test in tests
        for sub in ast.walk(test)
    )


def _names(node: ast.AST, name: str) -> bool:
    return any(
        isinstance(sub, ast.Name) and sub.id == name for sub in ast.walk(node)
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


def _actor_id_names(nodes: list[ast.stmt]) -> set[str]:
    """Names assigned a value that reads ``attributed_to`` in *nodes*."""
    return {
        target.id
        for stmt in nodes
        for sub in ast.walk(stmt)
        if isinstance(sub, ast.Assign) and _reads_actor_id(sub.value)
        for target in sub.targets
        if isinstance(target, ast.Name)
    }


def _collects_actor_id(calls: list[ast.Call], derived: set[str]) -> bool:
    """True when a collecting call's argument is an actor ID."""
    return any(
        _reads_actor_id(arg) or any(_names(arg, name) for name in derived)
        for call in calls
        for arg in call.args
    )


def _if_tests(nodes: list[ast.stmt]) -> list[ast.expr]:
    return [
        sub.test
        for stmt in nodes
        for sub in ast.walk(stmt)
        if isinstance(sub, ast.If)
    ]


def _collect_calls(nodes: list[ast.stmt]) -> list[ast.Call]:
    return [
        sub
        for stmt in nodes
        for sub in ast.walk(stmt)
        if isinstance(sub, ast.Call)
        and isinstance(sub.func, ast.Attribute)
        and sub.func.attr in {"append", "add", "extend"}
    ]


def _flagged_nodes(tree: ast.AST) -> list[ast.AST]:
    """Every node in *tree* that builds a list of roster actor IDs itself.

    Four shapes:

    - a loop, comprehension or ``*``-unpacking over the roster's actor IDs
      (the index, its ``getattr`` spelling, a name bound to it, or
      ``.keys()``);
    - ``list``/``set``/``sorted``/… of the same;
    - a loop or comprehension over the index's ``.items()`` that collects
      the actor-ID key;
    - a loop or comprehension over participant records (index ``.values()``
      or ``.items()``, ``case_participants``, or ``iter_case_participants``)
      that collects each record's ``attributed_to`` — the actor ID — into a
      list.  A record loop that reads a role, a status, or returns one match
      is a lookup, not addressing, and is not flagged.
    """
    aliases = _index_aliases(tree)
    flagged: list[ast.AST] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.For, ast.AsyncFor)):
            calls = _collect_calls(node.body)
            items = _items_key(node.target, node.iter, aliases)
            if (
                _iterates_roster_ids(node.iter, aliases)
                or (
                    items is not None
                    and _collects_actor_id(calls, {items[0]})
                    and not _matches_value(_if_tests(node.body), items[1])
                )
                or (
                    _iterates_records(node.iter, aliases)
                    and _collects_actor_id(calls, _actor_id_names(node.body))
                )
            ):
                flagged.append(node.iter)
        elif isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp)):
            for gen in node.generators:
                items = _items_key(gen.target, gen.iter, aliases)
                if (
                    _iterates_roster_ids(gen.iter, aliases)
                    or (
                        items is not None
                        and _names(node.elt, items[0])
                        and not _matches_value(gen.ifs, items[1])
                    )
                    or (
                        _iterates_records(gen.iter, aliases)
                        and _reads_actor_id(node.elt)
                    )
                ):
                    flagged.append(gen.iter)
        elif (
            isinstance(node, ast.Starred)
            and _iterates_roster_ids(node.value, aliases)
        ) or (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in _COLLECTING_CALLS
            and node.args
            and _iterates_roster_ids(node.args[0], aliases)
        ):
            flagged.append(node)
    return flagged


def _roster_iteration_sites() -> list[str]:
    sites: list[str] = []
    for path, tree in _corpus.files_mentioning(
        "actor_participant_index",
        _RECORD_HELPER,
        _RECORD_LIST,
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
        "for ref in case.case_participants:\n"
        "    aid = _as_id(dl.read(ref).attributed_to)\n"
        "    uris.append(aid)\n"
        "w = [p.attributed_to for p in iter_case_participants(case, dl)]\n"
        "v = [a for a, _ in case.actor_participant_index.items() if a != me]\n"
        "for a, pid in case.actor_participant_index.items():\n"
        "    r.append(a)\n"
        "idx = case.actor_participant_index\n"
        "u = [a for a in idx]\n"
        "t = [*case.actor_participant_index]\n"
        "s = [p.attributed_to for p in case.case_participants]\n"
    )
    assert len(_flagged_nodes(_corpus.parse_inline(flagged_source))) == 13

    lookup_source = (
        "for pid in case.actor_participant_index.values():\n"
        "    if dl.read(pid) is None: return False\n"
        "for p in iter_case_participants(case, dl):\n"
        "    if role in p.roles: return p.attributed_to\n"
        "pid = next(p for a, p in case.actor_participant_index.items()"
        " if a == target)\n"
        "gone = [a for a, pid in case.actor_participant_index.items()"
        " if pid == target]\n"
        "ids = [_as_id(p) for p in case.case_participants]\n"
        "for ref in case.case_participants:\n"
        "    p = dl.read(ref)\n"
        "    if _as_id(p.attributed_to) == actor: found.append(ref)\n"
    )
    assert _flagged_nodes(_corpus.parse_inline(lookup_source)) == []
