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
"""The one place a test builds an object that carries its author's time.

A core object, a wire object, a case status and an embargo carry the time
their author made them (``published``, ``updated``, an embargo's
``start_time``).  A core model takes that time from the act and never reads
the clock (ADR-0176), so a test states it.  :func:`make` states it once, for
every time the caller leaves out, and a test that means another time passes
it.

The time ``make`` states is the wall clock's, read once per object through
``now_utc`` and shared by every time left out, so ``published`` and
``updated`` are equal where the model's defaults read the clock once per
field.  ``test/support/act_runner.py`` opens a test's act at the same wall
clock, so an object a test builds is never older than the act that judges it
(CLP-14-008).  A test that
pins its act at :data:`~test.support.act_clock.ACT_AT` passes that time.

Tests build these models through :func:`make` rather than calling the class:
``test/architecture/test_tests_build_timed_objects_through_make.py`` fails on
a direct call anywhere else under ``test/``.

Spec: CS-13-002 (time enters at the act's edge).
"""

from datetime import datetime
from functools import cache
from typing import Any

from pydantic import BaseModel
from pydantic.fields import FieldInfo

from vultron.core.models._helpers.clock import now_utc

#: The fields that carry an object's author's time.
AUTHOR_TIMES: tuple[str, ...] = ("published", "updated", "start_time")


def authored_at() -> datetime:
    """The time a test's object or outbound activity is authored at.

    One wall-clock read per call: the same clock
    ``test/support/act_runner.py`` opens a test's act at, read separately.
    :func:`make` supplies it for every time left out, and a test passes it
    as ``at=`` to a factory or a trigger-activity port method, which author
    an activity at the act's instant (ADR-0176).  Pinning tests
    to :data:`~test.support.act_clock.ACT_AT` is a change here and in the
    runner, nowhere else.
    """
    return now_utc()


def stamped_times(cls: type[BaseModel]) -> tuple[str, ...]:
    """The author's times :func:`make` supplies for *cls*; empty if none.

    A time is one of :data:`AUTHOR_TIMES` that *cls* would otherwise take
    from the clock.  A model whose time is absent until stated (a case
    status's ``updated``, CM-29-006; a consent row's times) gets none.
    """
    fields = cls.model_fields
    return tuple(
        name
        for name in AUTHOR_TIMES
        if name in fields and fields[name].default_factory is now_utc
    )


def _spellings(info: FieldInfo, name: str) -> frozenset[str]:
    """Every key a caller may pass a field under: its name and its aliases."""
    spellings = {name}
    if info.alias:
        spellings.add(info.alias)
    if isinstance(info.validation_alias, str):
        spellings.add(info.validation_alias)
    return frozenset(spellings)


@cache
def _time_spellings(
    cls: type[BaseModel],
) -> tuple[tuple[str, frozenset[str]], ...]:
    fields = cls.model_fields
    return tuple(
        (name, _spellings(fields[name], name)) for name in stamped_times(cls)
    )


def make[M: BaseModel](cls: type[M], /, **fields: Any) -> M:
    """Build *cls* from *fields*, with one wall-clock reading shared by
    every time left out.

    A time the caller passes under any spelling, ``None`` included, is kept
    as passed.
    """
    missing = [
        name
        for name, spellings in _time_spellings(cls)
        if spellings.isdisjoint(fields)
    ]
    if missing:
        at = authored_at()
        fields.update(dict.fromkeys(missing, at))
    return cls(**fields)
