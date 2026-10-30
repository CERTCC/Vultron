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

"""A core class that stays a plain ``BaseModel`` says why (ARCH-12-020).

ARCH-12-007 puts every protocol-significant core class on ``CoreObject`` or
``CoreRecord``; ARCH-12-019 lets a configuration class, a dispatch envelope or
an internal record stay a plain ``BaseModel``. Such a class must carry a
docstring giving its reason, so that leaving the hierarchy is a choice someone
made, not an accident. A subclass of a documented plain base inherits the
reason. This test checks that the docstring is there; review
checks that it gives the reason.

Spec: ARCH-12-020.
"""

import importlib
import inspect
import pkgutil
from typing import TypeGuard

import pytest
from pydantic import BaseModel

import vultron.core
from vultron.core.models.base import CoreRecord


def _is_written_plain_model(
    cls: type, module_name: str
) -> TypeGuard[type[BaseModel]]:
    """Whether *cls* is a plain ``BaseModel`` class written in *module_name*.

    A parametrized generic such as ``TriggerRequest[CaseResult]`` is pydantic's
    product, not a class anyone wrote, so it is left out.
    """
    return (
        cls.__module__ == module_name
        and issubclass(cls, BaseModel)
        and not issubclass(cls, CoreRecord)
        and cls.__pydantic_generic_metadata__["origin"] is None
    )


def _plain_core_models() -> list[type[BaseModel]]:
    """Each class defined under ``vultron/core/`` on ``BaseModel`` alone."""
    found: list[type[BaseModel]] = []
    for info in pkgutil.walk_packages(
        vultron.core.__path__, vultron.core.__name__ + "."
    ):
        module = importlib.import_module(info.name)
        for _name, cls in inspect.getmembers(module, inspect.isclass):
            if _is_written_plain_model(cls, module.__name__):
                found.append(cls)
    return found


def _reason_documented(cls: type[BaseModel]) -> bool:
    """Whether *cls*, or a plain core base it inherits, has a docstring."""
    return any(
        (base.__dict__.get("__doc__") or "").strip()
        for base in cls.__mro__
        if base is not BaseModel
        and issubclass(base, BaseModel)
        and base.__module__.startswith("vultron.core.")
    )


_SYNTHETIC = "vultron.core.synthetic"


def _synthetic(name: str, *bases: type, doc: str | None = None) -> type:
    """A class built as if written in a core module, with *doc* or none."""
    namespace: dict[str, object] = {"__module__": _SYNTHETIC}
    if doc is not None:
        namespace["__doc__"] = doc
    return type(name, bases, namespace)


class _Generic[T](BaseModel):
    """A generic plain model; its parametrizations are pydantic's."""

    value: T


def test_an_undocumented_plain_model_is_flagged() -> None:
    assert _reason_documented(_synthetic("Bare", BaseModel)) is False


def test_a_blank_docstring_is_flagged() -> None:
    assert (
        _reason_documented(_synthetic("Blank", BaseModel, doc="  ")) is False
    )


def test_a_documented_plain_model_passes() -> None:
    cls = _synthetic("Said", BaseModel, doc="Local configuration only.")
    assert _reason_documented(cls) is True


def test_a_subclass_inherits_its_plain_base_reason() -> None:
    base = _synthetic("Base", BaseModel, doc="A transient dispatch envelope.")
    assert _reason_documented(_synthetic("Child", base)) is True


def test_a_docstring_outside_core_gives_no_reason() -> None:
    outside = type("Outside", (BaseModel,), {"__doc__": "Not core."})
    assert _reason_documented(_synthetic("Child", outside)) is False


def test_the_scan_skips_a_parametrized_generic() -> None:
    module_name = _Generic.__module__
    assert _is_written_plain_model(_Generic, module_name) is True
    assert _is_written_plain_model(_Generic[int], module_name) is False


def test_the_scan_skips_core_records_and_imported_classes() -> None:
    assert _is_written_plain_model(CoreRecord, CoreRecord.__module__) is False
    assert _is_written_plain_model(BaseModel, _SYNTHETIC) is False


def test_the_scan_finds_plain_core_models() -> None:
    """Guard the guard: an empty scan would pass the check below vacuously."""
    assert len(_plain_core_models()) > 10


@pytest.mark.spec("ARCH-12-020")
def test_every_plain_core_model_has_a_docstring() -> None:
    undocumented = sorted(
        f"{cls.__module__}.{cls.__qualname__}"
        for cls in _plain_core_models()
        if not _reason_documented(cls)
    )
    assert not undocumented, (
        "these core classes stay plain BaseModel subclasses but carry no "
        f"docstring saying why (ARCH-12-020): {undocumented}"
    )
