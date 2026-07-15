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

"""Import-graph invariant tests for the ``vultron.enums`` and ``vultron.config``
neutral layers.

Enforces the bottom-of-stack constraints from
``docs/adr/0031-vultron-enums-neutral-layer.md`` and
``specs/configuration.yaml`` CFG-07-006:

- ``vultron.enums`` MUST NOT import from ``vultron.core``, ``vultron.config``,
  or ``vultron.adapters``.
- ``vultron.config`` MUST NOT import from ``vultron.core`` or
  ``vultron.adapters``.
"""

import ast
import pathlib

import pytest

_REPO_ROOT = pathlib.Path(__file__).parents[2]


def _assert_no_forbidden_imports(
    source_dir: pathlib.Path, layer: str, forbidden_prefix: str
) -> None:
    """Raise AssertionError if any .py file under *source_dir* imports from *forbidden_prefix*."""
    violations: list[str] = []
    for py_file in source_dir.rglob("*.py"):
        tree = ast.parse(py_file.read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                module = (
                    node.module if isinstance(node, ast.ImportFrom) else None
                )
                if module and module.startswith(forbidden_prefix):
                    violations.append(
                        f"{py_file.relative_to(source_dir.parent)}: "
                        f"imports from {module}"
                    )
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith(forbidden_prefix):
                            violations.append(
                                f"{py_file.relative_to(source_dir.parent)}: "
                                f"imports {alias.name}"
                            )
    assert (
        not violations
    ), f"{layer} MUST NOT import from {forbidden_prefix}:\n" + "\n".join(
        violations
    )


class TestEnumsLayerImportGraph:
    """``vultron.enums`` must be the bottom of the import stack."""

    @pytest.fixture(autouse=True)
    def _import_enums(self) -> None:
        import vultron.enums  # noqa: F401 — side-effect: populates sys.modules
        import vultron.enums.roles  # noqa: F401

    def test_enums_does_not_import_vultron_core(self) -> None:
        """``vultron.enums`` MUST NOT import from ``vultron.core``."""
        _assert_no_forbidden_imports(
            _REPO_ROOT / "vultron" / "enums", "vultron.enums", "vultron.core"
        )

    def test_enums_does_not_import_vultron_config(self) -> None:
        """``vultron.enums`` MUST NOT import from ``vultron.config``."""
        _assert_no_forbidden_imports(
            _REPO_ROOT / "vultron" / "enums",
            "vultron.enums",
            "vultron.config",
        )

    def test_enums_does_not_import_vultron_adapters(self) -> None:
        """``vultron.enums`` MUST NOT import from ``vultron.adapters``."""
        _assert_no_forbidden_imports(
            _REPO_ROOT / "vultron" / "enums",
            "vultron.enums",
            "vultron.adapters",
        )


class TestConfigLayerImportGraph:
    """``vultron.config`` must not import from core or adapters."""

    def test_config_does_not_import_vultron_core(self) -> None:
        """``vultron.config`` MUST NOT import from ``vultron.core``."""
        _assert_no_forbidden_imports(
            _REPO_ROOT / "vultron" / "config",
            "vultron.config",
            "vultron.core",
        )

    def test_config_does_not_import_vultron_adapters(self) -> None:
        """``vultron.config`` MUST NOT import from ``vultron.adapters``."""
        _assert_no_forbidden_imports(
            _REPO_ROOT / "vultron" / "config",
            "vultron.config",
            "vultron.adapters",
        )
