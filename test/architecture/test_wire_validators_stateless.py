#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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

"""Wire-branch validators check a message's own form, never stored state.

ARCH-12-004 forbids a wire-branch validator a rule that depends on case state
or stored data; ARCH-12-021 permits one that checks the form of the message
itself, such as CP-01-012 or SYNC-16-028.  A validator can reach stored data
or case state only through the DataLayer ports, the adapters, or the core
code that runs on them, so two structural checks hold the line:

1. no module that defines a wire-branch class with a validator imports from
   those packages, and
2. no validator function names the store, the case-status record or its
   per-dimension state.

The subjects are discovered: every ``as_Base`` subclass under
``vultron.wire`` that declares a field or model validator.
"""

import ast
import inspect
import sys
import textwrap
from types import ModuleType

import pytest

from test.support.core_vocab import import_all_core_models
from vultron.subclasses import all_subclasses
from vultron.wire.as2.vocab.base.base import as_Base

#: Packages through which code reaches stored data or case state.
_STATEFUL_PACKAGES = (
    "vultron.adapters",
    "vultron.core.ports",
    "vultron.core.behaviors",
    "vultron.core.use_cases",
    "vultron.core.services",
)

#: Names a validator would use to read the store or case state.
_STATEFUL_NAMES = frozenset(
    {
        "dl",
        "datalayer",
        "DataLayer",
        "get_datalayer",
        "CasePersistence",
        "read_case",
        "current_status",
        "case_statuses",
        "participant_statuses",
    }
)


def _wire_classes_with_validators() -> list[type[as_Base]]:
    import_all_core_models()
    import vultron.wire.as2.vocab.activities
    import vultron.wire.as2.vocab.objects  # noqa: F401

    found: list[type[as_Base]] = []
    for cls in all_subclasses(as_Base):
        if not cls.__module__.startswith("vultron.wire"):
            continue
        if _validator_functions(cls):
            found.append(cls)
    return found


def _validator_functions(cls: type[as_Base]) -> list[object]:
    decorators = cls.__pydantic_decorators__
    return [
        *(d.func for d in decorators.field_validators.values()),
        *(d.func for d in decorators.model_validators.values()),
    ]


def _imported_modules(module: ModuleType) -> set[str]:
    tree = ast.parse(inspect.getsource(module))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _names_in(func: object) -> set[str]:
    raw = getattr(func, "__func__", func)
    tree = ast.parse(textwrap.dedent(inspect.getsource(raw)))  # type: ignore[arg-type]
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    return names


def test_discovery_finds_the_parse_edge_validators() -> None:
    """Guard the guard: the walk reaches the form checks ARCH-12-021 permits."""
    names = {cls.__name__ for cls in _wire_classes_with_validators()}
    assert {"as_CaseProposal", "as_Reject", "as_Question"} <= names


@pytest.mark.spec("ARCH-12-004")
def test_no_wire_validator_module_imports_stateful_code() -> None:
    offenders = sorted(
        f"{cls.__module__} imports {imported}"
        for cls in _wire_classes_with_validators()
        for imported in _imported_modules(sys.modules[cls.__module__])
        if imported.startswith(_STATEFUL_PACKAGES)
    )
    assert offenders == []


@pytest.mark.spec("ARCH-12-004")
def test_no_wire_validator_names_the_store_or_case_state() -> None:
    offenders = sorted(
        f"{cls.__qualname__}.{getattr(func, '__name__', func)} names"
        f" {sorted(_names_in(func) & _STATEFUL_NAMES)}"
        for cls in _wire_classes_with_validators()
        for func in _validator_functions(cls)
        if _names_in(func) & _STATEFUL_NAMES
    )
    assert offenders == []
