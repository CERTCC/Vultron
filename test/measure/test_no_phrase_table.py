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

"""The measure package keeps no event-phrase table of its own (CEH-01-007, DRPT-03-005).

Every phrase is read through ``lookup_entry`` (``test/measure/ledger/
test_labels.py``).  These tests hold the other half: no module under
``vultron/measure/`` defines a mapping from a semantic type to a string, and
no module spells out a registry phrase.
"""

import ast
import importlib
import pkgutil
from collections.abc import Mapping
from pathlib import Path
from types import ModuleType

import pytest

import vultron.measure
from vultron.core.models.events.base import MessageSemantics
from vultron.semantic_registry import SEMANTIC_REGISTRY

_SEMANTIC_VALUES = frozenset(m.value for m in MessageSemantics)
_PHRASES = frozenset(entry.phrase for entry in SEMANTIC_REGISTRY)


def _measure_modules() -> list[ModuleType]:
    modules: list[ModuleType] = [vultron.measure]
    for info in pkgutil.walk_packages(
        vultron.measure.__path__, prefix="vultron.measure."
    ):
        modules.append(importlib.import_module(info.name))
    return modules


def _is_phrase_table(value: object) -> bool:
    """A mapping with a semantic-type key and a string value."""
    if not isinstance(value, Mapping):
        return False
    return any(
        (isinstance(key, MessageSemantics) or key in _SEMANTIC_VALUES)
        and isinstance(item, str)
        for key, item in value.items()
        if isinstance(key, str)
    )


def test_the_detector_finds_a_phrase_table():
    assert _is_phrase_table({MessageSemantics.CREATE_CASE: "created a case"})
    assert _is_phrase_table({"create_case": "created a case"})
    assert not _is_phrase_table({"Note": "note"})
    assert not _is_phrase_table({MessageSemantics.CREATE_CASE: 1})


@pytest.mark.spec("CEH-01-007")
@pytest.mark.spec("DRPT-03-005")
def test_no_measure_module_defines_a_semantic_type_to_phrase_mapping():
    modules = _measure_modules()
    assert len(modules) > 1
    tables = sorted(
        f"{module.__name__}.{name}"
        for module in modules
        for name, value in vars(module).items()
        if _is_phrase_table(value)
    )
    assert not tables, tables


@pytest.mark.spec("CEH-01-007")
def test_no_measure_module_spells_out_a_registry_phrase():
    root = Path(vultron.measure.__file__).parent
    sources = sorted(root.rglob("*.py"))
    assert sources
    copied = sorted(
        f"{path.relative_to(root)}:{node.lineno}"
        for path in sources
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.Constant) and node.value in _PHRASES
    )
    assert not copied, copied
