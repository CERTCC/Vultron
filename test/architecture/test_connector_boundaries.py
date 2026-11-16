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
- A module under ``vultron/adapters/connectors/`` imports, from ``vultron``,
  only what translation needs (ARCH-05-002): its own package, the core ports
  it implements (:data:`CONNECTOR_PORTS`), the core models it translates
  into except the hash-chained case ledger, the shared errors and the
  primitives.  This is an allow-list, so a use case, a behavior, a service,
  a sync helper that stores a ledger entry, a dispatcher, a storage or
  delivery port, or any other adapter is refused without being named here.

Deferred, relative, ``TYPE_CHECKING`` and by-name (``import_module``) imports
count (:func:`test.architecture._corpus.import_sites`).
"""

from __future__ import annotations

import ast
import textwrap
from collections.abc import Callable
from pathlib import Path

import pytest

from test.architecture import _corpus
from vultron.adapters.connectors.base import CONNECTOR_PORTS

_CONNECTORS = "vultron.adapters.connectors"
_CORE_ROOT = _corpus.REPO_ROOT / "vultron" / "core"
_CONNECTORS_ROOT = _corpus.REPO_ROOT / "vultron" / "adapters" / "connectors"
_CORE_PROBE = _CORE_ROOT / "_probe.py"
_CONNECTOR_PROBE = _CONNECTORS_ROOT / "example" / "_probe.py"

#: The ``vultron`` modules a connector may import (ARCH-05-002).  A module
#: and everything under it are covered.
_TRANSLATION = (
    _CONNECTORS,
    *sorted({port.__module__ for port in CONNECTOR_PORTS}),
    "vultron.core.models",
    "vultron.errors",
    "vultron.primitives",
)

#: Under an allowed module, still refused: the ledger that commits entries.
_LEDGER = ("vultron.core.models.case_ledger",)


def _under(module: str, prefixes: tuple[str, ...]) -> bool:
    return any(module == p or module.startswith(p + ".") for p in prefixes)


def _is_vultron(module: str) -> bool:
    return _under(module, ("vultron",))


def _core_violation(module: str) -> bool:
    return _under(module, (_CONNECTORS,))


def _connector_violation(module: str) -> bool:
    return _is_vultron(module) and (
        not _under(module, _TRANSLATION) or _under(module, _LEDGER)
    )


def _violations(
    path: Path, tree: ast.AST, violates: Callable[[str], bool]
) -> list[str]:
    """Each import site in *tree* whose module *violates* the boundary."""
    package = _corpus.package_of(path)
    rel = path.relative_to(_corpus.REPO_ROOT).as_posix()
    return [
        f"{rel}:{line} imports {module}"
        for module, line in _corpus.import_sites(tree, package)
        if violates(module)
    ]


@pytest.mark.spec("ARCH-05-001")
def test_core_imports_no_connector_module():
    found: list[str] = []
    for path, tree in _corpus.files_mentioning("connectors", under=_CORE_ROOT):
        found += _violations(path, tree, _core_violation)
    assert found == []


@pytest.mark.spec("ARCH-05-002")
def test_connectors_import_only_what_translation_needs():
    found: list[str] = []
    for path, tree in _corpus.all_trees(_CONNECTORS_ROOT):
        found += _violations(path, tree, _connector_violation)
    assert found == []


def test_the_connector_scan_reads_the_connector_modules():
    scanned = {
        path.name for path, _tree in _corpus.all_trees(_CONNECTORS_ROOT)
    }
    assert {"base.py", "loader.py", "vince.py"} <= scanned


def _flags(
    source: str, path: Path, violates: Callable[[str], bool]
) -> list[str]:
    tree = _corpus.parse_inline(textwrap.dedent(source))
    return _violations(path, tree, violates)


@pytest.mark.parametrize(
    "source",
    [
        "from vultron.adapters.connectors.example import vince",
        "def f():\n    import vultron.adapters.connectors.base",
        "from ..adapters.connectors import base",
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    from vultron.adapters.connectors.base import ConnectorPlugin",
        "import importlib\n"
        "importlib.import_module('vultron.adapters.connectors.loader')",
    ],
)
def test_the_core_check_flags_a_connector_import(source: str):
    assert _flags(source, _CORE_PROBE, _core_violation)


@pytest.mark.parametrize(
    "source",
    [
        "from vultron.core.use_cases.received import x",
        "from vultron.core.behaviors import bridge",
        "from vultron.core.sync_helpers import store_ledger_entry",
        "from vultron.core.ports.datalayer import DataLayer",
        "from vultron.core.ports.sync_activity import SyncActivityPort",
        "from vultron.core.models.case_ledger import ledger",
        "from vultron.adapters.driven import http_delivery",
        "from vultron.adapters.driving.fastapi import main",
        "from vultron.adapters import outbox_dead_letter",
        "from ...driven import http_delivery",
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    from vultron.core.services import case_copy",
        "import importlib\nimportlib.import_module('vultron.core.behaviors')",
    ],
)
def test_the_connector_check_flags_a_case_handling_import(source: str):
    assert _flags(source, _CONNECTOR_PROBE, _connector_violation)


def test_the_connector_check_admits_what_translation_needs():
    source = (
        "import json\n"
        "from pydantic import BaseModel\n"
        "from vultron.core.ports.case_reader import CaseReader\n"
        "from vultron.core.models.case_reading import CaseReading\n"
        "from vultron.core.models.case_ledger_entry import CaseLedgerEntry\n"
        "from vultron.errors import VultronNotFoundError\n"
        "from vultron.primitives import NonEmptyString\n"
        "from .. import base\n"
    )
    assert _flags(source, _CONNECTOR_PROBE, _connector_violation) == []
