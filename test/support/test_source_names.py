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

"""Tests for the name-level source scans the counterpart-lookup ratchets use.

The ratchets only ever assert that nothing is found, so a scan that stopped
seeing a name would pass them silently. These tests plant each form of
reference the scan claims to catch and check that it is reported.
"""

import importlib
import sys
import textwrap
from pathlib import Path
from types import ModuleType

import pytest

from test.support.source_names import package_modules, referenced_names

_PACKAGE = "_source_names_fixture_pkg"


@pytest.fixture
def make_package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Write a throwaway package under *tmp_path* and return an importer.

    Each file maps a path relative to the package root to its source.
    """
    monkeypatch.syspath_prepend(str(tmp_path))

    def _make(files: dict[str, str]) -> ModuleType:
        for relative, source in files.items():
            path = tmp_path / _PACKAGE / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(textwrap.dedent(source))
        importlib.invalidate_caches()
        return importlib.import_module(_PACKAGE)

    yield _make
    for name in [m for m in sys.modules if m.split(".")[0] == _PACKAGE]:
        del sys.modules[name]


_REGISTRY = f"{_PACKAGE}.registry"


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "find_in_vocabulary = None\nfind_in_vocabulary\n",
            "find_in_vocabulary",
        ),
        (f"import {_REGISTRY}\n{_REGISTRY}.VOCABULARY\n", "VOCABULARY"),
        (f"from {_REGISTRY} import VOCABULARY as v  # noqa\n", "VOCABULARY"),
        (f"import {_REGISTRY} as r  # noqa\n", "registry"),
    ],
    ids=["name", "attribute", "from-import-alias", "dotted-import-alias"],
)
def test_referenced_names_reports_each_reference_form(
    make_package, source, expected
):
    module = make_package(
        {
            "__init__.py": "",
            "registry.py": "VOCABULARY: dict = {}\n",
            "target.py": source,
        }
    )
    target = importlib.import_module(f"{module.__name__}.target")

    assert expected in referenced_names(target)


def test_referenced_names_reports_the_imported_name_not_the_alias(
    make_package,
):
    module = make_package(
        {"__init__.py": "from os import getcwd as lookup  # noqa\n"}
    )

    names = referenced_names(module)
    assert "getcwd" in names
    assert "lookup" not in names


def test_package_modules_recurses_into_subpackages(make_package):
    package = make_package(
        {
            "__init__.py": "",
            "top.py": "",
            "sub/__init__.py": "",
            "sub/leaf.py": "",
        }
    )

    assert {m.__name__ for m in package_modules(package)} == {
        _PACKAGE,
        f"{_PACKAGE}.top",
        f"{_PACKAGE}.sub",
        f"{_PACKAGE}.sub.leaf",
    }
