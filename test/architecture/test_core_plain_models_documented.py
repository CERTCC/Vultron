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
made, not an accident. This test checks that the docstring is there; review
checks that it gives the reason.

Spec: ARCH-12-020.
"""

import importlib
import inspect
import pkgutil

import pytest
from pydantic import BaseModel

import vultron.core.models
from vultron.core.models.base import CoreRecord


def _plain_core_models() -> list[type[BaseModel]]:
    """Each class defined under ``vultron/core/models/`` on ``BaseModel`` alone."""
    found: list[type[BaseModel]] = []
    for info in pkgutil.walk_packages(
        vultron.core.models.__path__, vultron.core.models.__name__ + "."
    ):
        module = importlib.import_module(info.name)
        for _name, cls in inspect.getmembers(module, inspect.isclass):
            if (
                cls.__module__ == module.__name__
                and issubclass(cls, BaseModel)
                and not issubclass(cls, CoreRecord)
            ):
                found.append(cls)
    return found


def test_the_scan_finds_plain_core_models() -> None:
    """Guard the guard: an empty scan would pass the check below vacuously."""
    assert len(_plain_core_models()) > 10


@pytest.mark.spec("ARCH-12-020")
def test_every_plain_core_model_has_a_docstring() -> None:
    undocumented = sorted(
        f"{cls.__module__}.{cls.__qualname__}"
        for cls in _plain_core_models()
        if not (cls.__dict__.get("__doc__") or "").strip()
    )
    assert not undocumented, (
        "these core classes stay plain BaseModel subclasses but carry no "
        f"docstring saying why (ARCH-12-020): {undocumented}"
    )
