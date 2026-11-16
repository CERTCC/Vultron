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


"""Connector plugins and core stay apart (ARCH-05-001, ARCH-05-002).

Two import boundaries, each read from the source of every module:

- No module under ``vultron/core/`` imports from
  ``vultron/adapters/connectors/`` (ARCH-05-001).  Core declares the ports a
  connector implements and never names a connector.
- No module under ``vultron/adapters/connectors/`` imports a module that
  handles cases, decides authorization, manages the case ledger, or stores
  or sends anything (ARCH-05-002).  A connector imports the port it
  implements and the core types it translates into, and nothing that would
  let it act on a case.

Deferred imports and imports by name (``import_module``) count
(:func:`test.architecture._corpus.import_sites`).
"""

from __future__ import annotations

import ast
import textwrap
from pathlib import Path

import pytest

from test.architecture import _corpus

_CONNECTORS = "vultron.adapters.connectors"
_CORE_ROOT = _corpus.REPO_ROOT / "vultron" / "core"
_CONNECTORS_ROOT = _corpus.REPO_ROOT / "vultron" / "adapters" / "connectors"

#: What a connector must not import (ARCH-05-002), by what it would let the
#: connector do.  A module and everything under it are covered.
_CASE_HANDLING = (
    # Case handling logic.
    "vultron.core.use_cases",
    "vultron.core.behaviors",
    "vultron.core.services",
    "vultron.core.dispatcher",
    "vultron.core.trigger_dispatcher",
    # Authorization: who may act, who is told.
    "vultron.core.participants",
    # Case ledger management: the hash-chained ledger that commits entries.
    "vultron.core.models.case_ledger",
    # Storing or sending: the ports and the adapters that implement them.
    "vultron.core.ports.datalayer",
    "vultron.core.ports.case_persistence",
    "vultron.core.ports.case_outbox",
    "vultron.core.ports.emitter",
    "vultron.adapters.driven",
)


def _names(module: str, prefixes: tuple[str, ...]) -> bool:
    return any(module == p or module.startswith(p + ".") for p in prefixes)


def _forbidden_imports(
    path: Path, tree: ast.AST, prefixes: tuple[str, ...]
) -> list[str]:
    """Each import site in *tree* that names a module under *prefixes*."""
    package = _corpus.package_of(path)
    rel = path.relative_to(_corpus.REPO_ROOT).as_posix()
    return [
        f"{rel}:{line} imports {module}"
        for module, line in _corpus.import_sites(tree, package)
        if _names(module, prefixes)
    ]


def _core_imports_of_connectors() -> list[str]:
    found: list[str] = []
    for path, tree in _corpus.files_mentioning(
        _CONNECTORS, "connectors", under=_CORE_ROOT
    ):
        found += _forbidden_imports(path, tree, (_CONNECTORS,))
    return found


def _connector_case_handling_imports() -> list[str]:
    found: list[str] = []
    for path, tree in _corpus.all_trees(_CONNECTORS_ROOT):
        found += _forbidden_imports(path, tree, _CASE_HANDLING)
    return found


@pytest.mark.spec("ARCH-05-001")
def test_core_imports_no_connector_module():
    assert _core_imports_of_connectors() == []


@pytest.mark.spec("ARCH-05-002")
def test_connectors_import_no_case_handling_module():
    assert _connector_case_handling_imports() == []


def test_the_connector_scan_reads_the_connector_modules():
    scanned = {
        path.name for path, _tree in _corpus.all_trees(_CONNECTORS_ROOT)
    }
    assert {"base.py", "loader.py", "vince.py"} <= scanned


@pytest.mark.parametrize(
    ("source", "prefixes"),
    [
        (
            "from vultron.adapters.connectors.example import vince",
            (_CONNECTORS,),
        ),
        (
            "def f():\n    import vultron.adapters.connectors.base",
            (_CONNECTORS,),
        ),
        ("from vultron.core.use_cases.received import x", _CASE_HANDLING),
        ("from vultron.core.models.case_ledger import ledger", _CASE_HANDLING),
        (
            "import importlib\nimportlib.import_module('vultron.core.behaviors')",
            _CASE_HANDLING,
        ),
    ],
)
def test_the_boundary_check_flags_a_forbidden_import(
    source: str, prefixes: tuple[str, ...]
):
    tree = _corpus.parse_inline(textwrap.dedent(source))
    path = _CORE_ROOT / "_probe.py"
    assert _forbidden_imports(path, tree, prefixes)


def test_the_boundary_check_admits_what_a_connector_may_import():
    source = (
        "from vultron.core.ports.case_reader import CaseReader\n"
        "from vultron.core.models.case_reading import CaseReading\n"
        "from vultron.core.models.case_ledger_entry import CaseLedgerEntry\n"
    )
    tree = _corpus.parse_inline(source)
    path = _CONNECTORS_ROOT / "_probe.py"
    assert _forbidden_imports(path, tree, _CASE_HANDLING) == []
