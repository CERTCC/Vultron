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
"""The star imports in ``vocab_examples.py`` never shadow a name (CS-03-001).

``vultron/wire/as2/vocab/examples/vocab_examples.py`` aggregates its sibling
example modules for the docs pages, and it is the one module that may use
``from module import *``.  A later star import silently replaces a name an
earlier one bound, so these tests import each star-imported submodule and fail
when two of them bind one public name to different objects.  The same object
reached through two submodules (a shared ``_base`` import) is not a conflict.

Each such import carries a ``# noqa: F403`` marker that cites CS-03-001
(CS-03-005).
"""

import ast
import importlib
from collections.abc import Mapping
from types import ModuleType

from test.architecture import _corpus

_AGGREGATOR = (
    _corpus.REPO_ROOT / "vultron/wire/as2/vocab/examples/vocab_examples.py"
)


def star_imported_modules(tree: ast.AST) -> list[str]:
    """The dotted names of the modules *tree* star-imports, in source order."""
    return [
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module is not None
        and any(alias.name == "*" for alias in node.names)
    ]


def public_names(module: ModuleType) -> list[str]:
    """The names ``from module import *`` binds: ``__all__``, else no ``_`` names."""
    exported = getattr(module, "__all__", None)
    if exported is not None:
        return list(exported)
    return [name for name in vars(module) if not name.startswith("_")]


def star_import_conflicts(modules: Mapping[str, ModuleType]) -> list[str]:
    """Each public name two of *modules* bind to different objects.

    *modules* maps a module name to its module, in star-import order.  One
    line per conflict names the name and both modules.
    """
    first: dict[str, tuple[str, object]] = {}
    conflicts: list[str] = []
    for module_name, module in modules.items():
        for name in public_names(module):
            value = getattr(module, name)
            if name not in first:
                first[name] = (module_name, value)
            elif first[name][1] is not value:
                conflicts.append(
                    f"{name}: {first[name][0]} and {module_name} bind "
                    "different objects"
                )
    return conflicts


def _module(name: str, **bindings: object) -> ModuleType:
    module = ModuleType(name)
    for key, value in bindings.items():
        setattr(module, key, value)
    return module


def test_vocab_examples_star_imports_bind_each_name_once() -> None:
    names = star_imported_modules(_corpus.tree_of(_AGGREGATOR))
    assert names, "vocab_examples.py star-imports no module"
    modules = {name: importlib.import_module(name) for name in names}
    assert star_import_conflicts(modules) == []


def test_checker_reports_one_name_bound_to_two_objects() -> None:
    modules = {
        "first": _module("first", shared=object()),
        "second": _module("second", shared=object()),
    }
    assert star_import_conflicts(modules) == [
        "shared: first and second bind different objects"
    ]


def test_checker_allows_one_object_reached_through_two_modules() -> None:
    shared = object()
    modules = {
        "first": _module("first", shared=shared),
        "second": _module("second", shared=shared, _private=object()),
        "third": _module("third", _private=object()),
    }
    assert star_import_conflicts(modules) == []


def test_checker_reads_all_when_a_module_declares_it() -> None:
    modules = {
        "first": _module("first", shared=object()),
        "second": _module(
            "second", __all__=["other"], shared=object(), other=object()
        ),
    }
    assert star_import_conflicts(modules) == []


def test_each_star_import_cites_cs_03_001() -> None:
    lines = _corpus.source_of(_AGGREGATOR).splitlines()
    tree = _corpus.tree_of(_AGGREGATOR)
    star_lines = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and any(alias.name == "*" for alias in node.names)
    ]
    uncited = [
        lines[number - 1]
        for number in star_lines
        if "# noqa: F403  # CS-03-001" not in lines[number - 1]
    ]
    assert star_lines
    assert uncited == []
