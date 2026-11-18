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
"""Ratchet: no constructor or factory under ``behaviors/`` takes a per-act value.

A per-act value varies with the act a tree runs for: a case, report,
embargo or actor id, or a carried object (BTND-01-008).  A node reads each one
from a key of the vocabulary, and neither a node constructor nor a tree
factory takes one as a parameter (BTND-01-009).

The check reads, under ``vultron/core/behaviors/``, every ``__init__`` written
in a top-level class and every module-level function, and lists each
parameter whose name names a per-act value (:func:`names_a_per_act_value`).
Each site is keyed ``<path>::<qualname>::<parameter>``.  The sites that
predate the rule are in :data:`~test.architecture._per_act_parameter_sites.KNOWN_PER_ACT_PARAMETERS`,
each tagged with the migration Task that removes it.  A new site fails; a
listed site that is gone fails until its entry is removed, so the list only
shrinks.  The close-out Task (#6593) asserts it is empty.

The reading is by parameter name, so it can miss a per-act value passed under
a name it does not know (``case``, ``report``); it cannot invent one.  A
``**kwargs`` parameter is not read here; the one-channel check
(``test_act_key_one_channel.py``) fails closed on it for a node with an
act-key port.
"""

import ast
import re
from collections.abc import Iterator
from pathlib import Path

import pytest

from test.architecture import _corpus
from test.architecture._per_act_parameter_sites import (
    KNOWN_PER_ACT_PARAMETERS,
)
from vultron.core.behaviors.act_keys import ACT_KEYS

_BEHAVIORS = _corpus.REPO_ROOT / "vultron" / "core" / "behaviors"

#: A parameter name ending in one of these names an id, a list of ids, a URI,
#: a carried object or its content (``case_id``, ``report_ids``,
#: ``owner_uri``, ``case_obj``, ``note_content``).
_PER_ACT_SUFFIX = re.compile(r"_(?:id|ids|uri|obj|content)$")

#: Further names that carry a per-act value: the act itself, a carried
#: object, record or field of one, or a time the act names.  A bare domain
#: name (``case``, ``participant``, ``status``) is not listed: it is most
#: often a record a node read at tick time and hands to a helper, which no
#: tree builds in.
_PER_ACT_NAMES: frozenset[str] = frozenset(
    {
        "activity",
        "attributed_to",
        "case_name",
        "content",
        "embargo",
        "embargo_data",
        "end_time",
        "entry",
        "in_reply_to",
        "inline_report",
        "note",
        "note_name",
        "object_data",
        "proposal_dict",
        "refused_entry",
        "request",
        "snapshot",
        "status_obj_fallback",
        "terminated_at",
    }
)


def names_a_per_act_value(parameter: str) -> bool:
    """Whether a parameter named *parameter* carries a per-act value.

    Every key of the vocabulary counts, and so does every name
    :data:`_PER_ACT_SUFFIX` or :data:`_PER_ACT_NAMES` matches.
    """
    return (
        parameter in ACT_KEYS
        or parameter in _PER_ACT_NAMES
        or _PER_ACT_SUFFIX.search(parameter) is not None
    )


def _named_parameters(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    """*fn*'s named parameters, without ``*args`` and ``**kwargs``."""
    variadic = {fn.args.vararg, fn.args.kwarg}
    return [p.arg for p in _corpus.parameters_of(fn) if p not in variadic]


def _definitions(
    module: ast.Module,
) -> Iterator[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
    """Each ``(qualname, function)`` the check reads in *module*.

    A module-level function is read under its own name, and a top-level
    class's ``__init__`` under the class's name.
    """
    for node in module.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node.name, node
        elif isinstance(node, ast.ClassDef):
            for member in node.body:
                if (
                    isinstance(member, ast.FunctionDef)
                    and member.name == "__init__"
                ):
                    yield node.name, member


def per_act_sites_in(module: ast.Module, path: str) -> set[str]:
    """The ``<path>::<qualname>::<parameter>`` sites *module* holds."""
    return {
        f"{path}::{qualname}::{parameter}"
        for qualname, fn in _definitions(module)
        for parameter in _named_parameters(fn)
        if names_a_per_act_value(parameter)
    }


def _relative(path: Path) -> str:
    return path.relative_to(_corpus.REPO_ROOT).as_posix()


def _head_sites() -> set[str]:
    found: set[str] = set()
    for path, tree in _corpus.all_trees(_BEHAVIORS):
        assert isinstance(tree, ast.Module)
        found |= per_act_sites_in(tree, _relative(path))
    return found


@pytest.mark.spec("BTND-01-008")
@pytest.mark.spec("BTND-01-009")
def test_no_new_constructor_or_factory_takes_a_per_act_value() -> None:
    new = sorted(_head_sites() - KNOWN_PER_ACT_PARAMETERS.keys())
    assert new == [], (
        "These constructors or factories take a per-act value as a parameter."
        "  Read the value from its vocabulary key (behaviors/act_keys.py)"
        " through an input port, declare it in the tree's inputs, and seed it"
        " from the act; until the factory loses the parameter, seed the node"
        " with with_act_keys (BTND-01-008, BTND-01-009, ADR-0207):\n"
        + "\n".join(f"  {site}" for site in new)
    )


@pytest.mark.spec("BTND-01-008")
@pytest.mark.spec("BTND-01-009")
def test_every_known_site_still_exists() -> None:
    """The list only shrinks: a removed site's entry is removed with it."""
    stale = sorted(KNOWN_PER_ACT_PARAMETERS.keys() - _head_sites())
    assert stale == [], (
        "These sites no longer take a per-act value; remove their entries"
        " from KNOWN_PER_ACT_PARAMETERS in"
        " test/architecture/_per_act_parameter_sites.py:\n"
        + "\n".join(f"  {site}" for site in stale)
    )


def test_every_entry_is_tagged_with_an_issue() -> None:
    """Each entry names the Task that removes it, as a positive number."""
    untagged = sorted(
        site
        for site, owner in KNOWN_PER_ACT_PARAMETERS.items()
        if not isinstance(owner, int) or owner <= 0
    )
    assert untagged == []


def test_every_entry_is_keyed_path_qualname_parameter() -> None:
    malformed = sorted(
        site
        for site in KNOWN_PER_ACT_PARAMETERS
        if not re.fullmatch(
            r"vultron/core/behaviors/[\w/]+\.py::\w+::\w+", site
        )
    )
    assert malformed == []


def test_the_scan_reads_the_behaviors_tree() -> None:
    """Guards the two checks above against passing vacuously.

    Asserted on definitions that take no per-act value, so it holds once
    the list is empty too.
    """
    read = {
        f"{_relative(path)}::{qualname}"
        for path, tree in _corpus.all_trees(_BEHAVIORS)
        if isinstance(tree, ast.Module)
        for qualname, _ in _definitions(tree)
    }
    assert {
        "vultron/core/behaviors/act_inputs.py::seed_act_inputs",
        "vultron/core/behaviors/act_key_scope.py::ActKeyScope",
    } <= read


_EXAMPLE = """
def factory(case_id, name, *args, report_ids=(), **kwargs):
    pass

async def positional_only(owner_uri, /, child, *, note_content):
    pass

class Node:
    def __init__(self, invitee_id, child, case_obj, request):
        pass

    def update(self, case_id):
        pass

class NoInit:
    pass
"""


def test_the_reading_covers_every_parameter_kind() -> None:
    module = _corpus.parse_inline(_EXAMPLE)
    assert isinstance(module, ast.Module)
    assert per_act_sites_in(module, "p.py") == {
        "p.py::factory::case_id",
        "p.py::factory::report_ids",
        "p.py::positional_only::owner_uri",
        "p.py::positional_only::note_content",
        "p.py::Node::invitee_id",
        "p.py::Node::case_obj",
        "p.py::Node::request",
    }


@pytest.mark.parametrize(
    ("parameter", "expected"),
    [
        ("case_id", True),
        ("owner_profile", True),
        ("sender_proposed_embargo", True),
        ("report_ids", True),
        ("proposer_uri", True),
        ("status_obj", True),
        ("activity", True),
        ("name", False),
        ("child", False),
        ("role", False),
        ("case_id_key", False),
        ("idle", False),
    ],
)
def test_which_names_carry_a_per_act_value(
    parameter: str, expected: bool
) -> None:
    assert names_a_per_act_value(parameter) is expected
