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

"""Every model ``datetime`` field serializes in the one fixed form (CS-13-007).

Pydantic's own JSON form for a ``datetime`` writes a fraction only when the
microseconds are not zero, so a field that falls back to it gives one instant
two string shapes (ADR-0167).  This walks every Pydantic model under
``vultron/`` and dumps each of its ``datetime`` fields with zero microseconds
and without, plainly and under ``serialize_as_any`` (the outbox's dump, which
skips an ``Annotated`` serializer), so a new field with no
:func:`~vultron.core.models._helpers.timestamp_serializer` fails here.
"""

import importlib
import pkgutil
import re
import types
import typing
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import BaseModel

import vultron
from vultron.subclasses import all_subclasses

#: Packages whose models are not this node's serialization: the legacy
#: simulator and the repo tooling (CS-13-002 scopes them out the same way).
_OUT_OF_SCOPE = ("vultron.bt", "vultron.metadata")

_FIXED_FORM = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}[+-]\d{2}:\d{2}$"
)


def _mentions_datetime(annotation: object) -> bool:
    if annotation is datetime:
        return True
    return any(_mentions_datetime(arg) for arg in typing.get_args(annotation))


def _datetime_fields() -> list[tuple[type[BaseModel], str]]:
    for module in pkgutil.walk_packages(vultron.__path__, "vultron."):
        if not module.name.startswith(_OUT_OF_SCOPE):
            importlib.import_module(module.name)
    found = []
    for cls in all_subclasses(BaseModel):
        if not cls.__module__.startswith(
            "vultron."
        ) or cls.__module__.startswith(_OUT_OF_SCOPE):
            continue
        if (
            isinstance(cls, types.GenericAlias)
            or cls.__pydantic_generic_metadata__["parameters"]
        ):
            continue
        for name, field in cls.model_fields.items():
            if _mentions_datetime(field.annotation):
                found.append((cls, name))
    return sorted(found, key=lambda pair: (pair[0].__qualname__, pair[1]))


_FIELDS = _datetime_fields()


def test_the_walk_finds_datetime_fields() -> None:
    """The ratchet below checks something: a broken walk would pass vacuously."""
    names = {(cls.__name__, name) for cls, name in _FIELDS}
    assert ("CoreObject", "published") in names
    assert ("CaseLedgerEntry", "received_at") in names


@pytest.mark.spec("CS-13-007")
@pytest.mark.parametrize("as_any", [False, True], ids=["plain", "as-any"])
@pytest.mark.parametrize(
    "microsecond", [0, 120000], ids=["whole-second", "fractional"]
)
def test_every_model_datetime_field_serializes_in_the_fixed_form(
    microsecond: int, as_any: bool
) -> None:
    instant = datetime(2026, 10, 30, 12, 0, 0, microsecond, tzinfo=UTC)
    bad = []
    for cls, name in _FIELDS:
        values: dict[str, Any] = {name: instant}
        dumped = cls.model_construct(**values).model_dump(
            mode="json",
            include={name},
            warnings=False,
            serialize_as_any=as_any,
        )
        value = dumped.get(name)
        if not (isinstance(value, str) and _FIXED_FORM.match(value)):
            bad.append(
                f"{cls.__module__}.{cls.__qualname__}.{name}: {value!r}"
            )
    assert not bad, (
        "datetime fields not in the fixed six-digit form; give each model a"
        " `timestamp_serializer(...)` for them (CS-13-007):\n  "
        + "\n  ".join(bad)
    )
