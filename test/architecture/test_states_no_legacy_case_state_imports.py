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

import pytest

from test.architecture import _corpus
from test.support.fresh_imports import loaded_under

_LEGACY = "vultron.core.case_states"

_STATES_ROOT = _corpus.REPO_ROOT / "vultron" / "core" / "states"


def _imports_legacy(tree: ast.AST, package: str) -> bool:
    return any(
        name == _LEGACY or name.startswith(f"{_LEGACY}.")
        for name in _corpus.imported_modules(tree, package)
    )


#: A module inside ``vultron/core/states/cs/`` and the package's own
#: ``__init__``, the two places a relative import resolves from.
_IN_CS = "vultron.core.states.cs"
_IN_STATES = "vultron.core.states"


@pytest.mark.parametrize(
    ("source", "package"),
    [
        ("import vultron.core.case_states", _IN_CS),
        ("import vultron.core.case_states.validations as v", _IN_CS),
        (
            "from vultron.core.case_states.validations import is_valid_state",
            _IN_CS,
        ),
        ("from vultron.core import case_states", _IN_CS),
        (
            "def f():\n    from vultron.core.case_states import patterns\n",
            _IN_CS,
        ),
        ("from ...case_states.validations import ensure_valid_state", _IN_CS),
        ("from ... import case_states", _IN_CS),
        ("from ..case_states import validations", _IN_STATES),
        ("from .. import case_states", _IN_STATES),
    ],
)
def test_the_detector_catches_each_import_shape(source, package):
    assert _imports_legacy(_corpus.parse_inline(source), package)


@pytest.mark.parametrize(
    ("source", "package"),
    [
        ("import vultron.core.case_states_other", _IN_CS),
        ("from vultron.core import case_statesx", _IN_CS),
        ("x = 'vultron.core.case_states'", _IN_CS),
        ("from .. import case_states", _IN_CS),
        ("from . import case_states", _IN_STATES),
    ],
)
def test_the_detector_ignores_near_misses(source, package):
    assert not _imports_legacy(_corpus.parse_inline(source), package)


def test_no_states_module_imports_the_legacy_case_state_package():
    trees = list(_corpus.all_trees(_STATES_ROOT))
    assert trees, f"found no modules under {_STATES_ROOT}"
    offending = sorted(
        path.relative_to(_corpus.REPO_ROOT).as_posix()
        for path, tree in trees
        if _imports_legacy(tree, _corpus.package_of(path))
    )
    assert offending == []


def test_importing_states_loads_no_legacy_case_state_module():
    """Indirect imports count too, so ask a fresh interpreter."""
    assert loaded_under(["vultron.core.states"], [_LEGACY]) == []
