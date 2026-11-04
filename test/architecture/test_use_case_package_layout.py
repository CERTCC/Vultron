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

"""Use-case classes sit in the subpackage their kind names (UCORG-01).

A use case is a class defined under ``vultron/core/use_cases/`` whose ``execute``
method, its own or inherited, returns a ``UseCaseResult`` subtype.  Its result type
says its kind: a ``HandlerResult`` answers a received message, a
``TriggerResult`` reports an actor-initiated behavior, and any other
``UseCaseResult`` is a read-only query result.  The subjects are discovered
by walking the package, never listed.
"""

import importlib
import inspect
import pkgutil
import typing
from pathlib import Path

import pytest

import vultron.core.use_cases as use_cases_pkg
from vultron.core.models.use_case_result import (
    HandlerResult,
    TriggerResult,
    UseCaseResult,
)

_ROOT = Path(use_cases_pkg.__file__).parent
_SUBPACKAGES = frozenset({"query", "received", "triggers"})


def _use_case_classes() -> list[tuple[str, type, type]]:
    """Every use-case class defined in the package: (module, class, result)."""
    found: list[tuple[str, type, type]] = []
    for info in pkgutil.walk_packages(
        use_cases_pkg.__path__, prefix=f"{use_cases_pkg.__name__}."
    ):
        module = importlib.import_module(info.name)
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if cls.__module__ != module.__name__:
                continue
            execute = getattr(cls, "execute", None)
            if execute is None:
                continue
            result = typing.get_type_hints(execute).get("return")
            bound = getattr(result, "__bound__", None)
            result = bound if bound is not None else result
            if inspect.isclass(result) and issubclass(result, UseCaseResult):
                found.append((module.__name__, cls, result))
    return found


def _subpackage(module_name: str) -> str | None:
    """The first package segment under ``use_cases``, or ``None`` at the root."""
    rest = module_name.removeprefix(f"{use_cases_pkg.__name__}.").split(".")
    return rest[0] if len(rest) > 1 else None


def _expected_subpackage(result: type) -> str:
    if issubclass(result, HandlerResult):
        return "received"
    if issubclass(result, TriggerResult):
        return "triggers"
    return "query"


def test_use_case_discovery_finds_every_kind() -> None:
    """Guard the guard: the walk finds a use case of each kind."""
    kinds = {
        _expected_subpackage(result) for _, _, result in _use_case_classes()
    }
    assert kinds == _SUBPACKAGES


@pytest.mark.spec("UCORG-01-001")
@pytest.mark.spec("UCORG-01-002")
@pytest.mark.spec("UCORG-01-004")
def test_each_use_case_sits_in_the_subpackage_its_kind_names() -> None:
    misplaced = [
        f"{cls.__qualname__} in {module} returns {result.__name__}: belongs in"
        f" {_expected_subpackage(result)}/"
        for module, cls, result in _use_case_classes()
        if _subpackage(module) != _expected_subpackage(result)
    ]
    assert misplaced == []


@pytest.mark.spec("UCORG-01-003")
def test_the_package_root_holds_only_its_allowed_entries() -> None:
    allowed_files = {"__init__.py", "README.md"}
    unexpected = sorted(
        entry.name
        for entry in _ROOT.iterdir()
        if entry.name != "__pycache__"
        and not (entry.is_dir() and entry.name in _SUBPACKAGES)
        and entry.name not in allowed_files
        and not (
            entry.is_file()
            and entry.name.startswith("_")
            and entry.suffix == ".py"
        )
    )
    assert unexpected == [], (
        "vultron/core/use_cases/ holds only __init__.py, README.md, the"
        f" {sorted(_SUBPACKAGES)} subpackages and private helper modules"
    )
