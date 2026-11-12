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
"""No core model field has a default that reads the clock (ADR-0176).

A core model takes every time from the act that makes it: building one never
reads the clock, so constructing an object cannot move a recording, and its
time cannot disagree with its act.  This test fails when a field of any model
under ``vultron/core/models`` gains a default that reads the clock or yields a
time.

Every ``vultron.core.models`` module is imported, so a new or renamed model is
covered without an edit here (#5535).  Each ``default_factory`` is called with
the clock recorded (``recorded_clock_reads``); a default that yields a
``datetime`` fails even without a recorded read, since a time no act stated is
the defect whatever produced it.  ``test_clock_reads_at_act_edge.py`` refuses
a clock read written anywhere under ``vultron/``; this test is the one that
names the model field.

Spec: CS-13-002, ARCH-10-001 (#5758 AC-1).
"""

import importlib
import pkgutil
from datetime import UTC, datetime
from functools import cache
from typing import Any

import pytest
from pydantic import BaseModel
from pydantic.fields import FieldInfo

import vultron.core.models
from test.support.act_clock import recorded_clock_reads


@cache
def _core_models() -> tuple[type[BaseModel], ...]:
    """Every model class defined under ``vultron.core.models``."""
    package = vultron.core.models
    modules = [package] + [
        importlib.import_module(info.name)
        for info in pkgutil.walk_packages(
            package.__path__, f"{package.__name__}."
        )
    ]
    found: dict[str, type[BaseModel]] = {}
    for module in modules:
        for value in vars(module).values():
            if (
                isinstance(value, type)
                and issubclass(value, BaseModel)
                and value.__module__.startswith(package.__name__)
            ):
                found[f"{value.__module__}.{value.__qualname__}"] = value
    return tuple(found[name] for name in sorted(found))


def _default_of(field: FieldInfo) -> tuple[Any, list[datetime]]:
    """The field's default, and the clock reads producing it took."""
    with recorded_clock_reads() as reads:
        if field.default_factory is None:
            value = field.default
        elif field.default_factory_takes_validated_data:
            value = field.default_factory({})  # type: ignore[call-arg]
        else:
            value = field.default_factory()  # type: ignore[call-arg]
    return value, reads


def clock_defaults(model: type[BaseModel]) -> list[str]:
    """The fields of *model* whose default reads the clock or is a time."""
    found = []
    for name, field in model.model_fields.items():
        if field.is_required():
            continue
        value, reads = _default_of(field)
        if reads or isinstance(value, datetime):
            found.append(name)
    return found


@pytest.mark.spec("CS-13-002")
@pytest.mark.spec("ARCH-10-001")
def test_no_core_model_field_defaults_to_the_clock() -> None:
    offenders = {
        f"{model.__module__}.{model.__qualname__}": fields
        for model in _core_models()
        if (fields := clock_defaults(model))
    }
    assert not offenders, (
        "A core model field defaults to the clock (ADR-0176).  Make the time"
        " required and set it from the act's instant where the object is"
        f" built: {offenders}"
    )


def test_the_scan_covers_the_timed_core_models() -> None:
    """The scan reaches the models whose times were clock defaults."""
    names = {model.__name__ for model in _core_models()}
    assert {
        "CoreObject",
        "CaseStatus",
        "EmbargoEvent",
        "VulnerabilityCase",
    } <= names


def test_the_scan_names_a_clock_default_and_a_time_default() -> None:
    from pydantic import Field

    from vultron.core.models._helpers.clock import now_utc

    class _Clocked(BaseModel):
        stamped: datetime = Field(default_factory=now_utc)
        pinned: datetime = datetime(2026, 1, 1, tzinfo=UTC)
        plain: int = 0
        required: datetime

    assert clock_defaults(_Clocked) == ["stamped", "pinned"]
