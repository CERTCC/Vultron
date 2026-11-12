#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""The authoritative case-state model never reaches the legacy one.

``vultron/core/states/`` is the case-state model the protocol runs on;
``vultron/core/case_states/`` is a reference model and the test oracle for
its invariants, never a protocol path (ADR-0060, ``notes/case-state-model.md``
§ "Where the CS Rules Live").  So no module under ``vultron/core/states/``
imports the legacy package, at module level or deferred, and importing
``vultron.core.states`` leaves the legacy package unloaded (#6328).

The source scan names the offending file; the fresh-interpreter probe also
catches an indirect import through a module outside ``vultron/core/states/``.
"""

import ast

from test.architecture import _corpus
from test.support.fresh_imports import loaded_under

_LEGACY = "vultron.core.case_states"

_STATES_ROOT = _corpus.REPO_ROOT / "vultron" / "core" / "states"


def _module_name(path) -> str:
    relative = path.relative_to(_corpus.REPO_ROOT).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _imported_names(path, tree: ast.AST) -> set[str]:
    """Every module *tree* imports, relative imports resolved against *path*."""
    package = _module_name(path).split(".")
    if path.name != "__init__.py":
        package.pop()
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = (
                package[: len(package) - node.level + 1] if node.level else []
            )
            module = ".".join([*base, *(node.module or "").split(".")]).strip(
                "."
            )
            found.add(module)
            found.update(f"{module}.{alias.name}" for alias in node.names)
    return found


def _is_legacy(name: str) -> bool:
    return name == _LEGACY or name.startswith(f"{_LEGACY}.")


def test_no_states_module_imports_the_legacy_case_state_package():
    trees = list(_corpus.all_trees(_STATES_ROOT))
    assert trees, f"found no modules under {_STATES_ROOT}"
    offending = sorted(
        path.relative_to(_corpus.REPO_ROOT).as_posix()
        for path, tree in trees
        if any(_is_legacy(name) for name in _imported_names(path, tree))
    )
    assert offending == []


def test_relative_imports_resolve_to_the_legacy_package():
    """The check above sees a relative import of the legacy package too."""
    path = _STATES_ROOT / "cs" / "parsing.py"
    tree = ast.parse(
        "from ...case_states.validations import ensure_valid_state"
    )
    assert any(_is_legacy(name) for name in _imported_names(path, tree))


def test_importing_states_loads_no_legacy_case_state_module():
    """Indirect imports count too, so ask a fresh interpreter."""
    assert loaded_under(["vultron.core.states"], [_LEGACY]) == []
