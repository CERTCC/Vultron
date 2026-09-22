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
"""Architecture boundary test: wire-branch field annotations must not name CoreObject subclasses.

Spec: ARCH-23-006

``as_ObjectRef`` carried ``| CoreObject``, added in PR #730 as a migration
convenience.  It made a core-side validation guard unsafe to enforce loudly:
``VultronValidationError`` is not a ``ValueError`` subclass, so a guard firing
while Pydantic resolves that union escapes the whole operation rather than being
absorbed as a failed union branch.

That union-escape defect is the whole of the remaining justification. This test
also cited ARCH-22-001 ("wire MUST NOT import core"), which ADR-0099 repealed —
and ADR-0099 goes further and *inverts* this rule, since under one object model a
wire field annotation is supposed to name the core class. Fixing the union-escape
defect is therefore the prerequisite for inverting this test, tracked as AC-2 of
#3491. Do not invert it first.

This test asserts that no wire-branch class (``as_Base`` subclass registered in
``VOCABULARY``) has a field annotation that names a ``CoreObject`` subclass.
The AS2-faithful reference union (``as_Object | as_Link | str``) is permitted.
"""

import typing

import pytest

import vultron.wire.as2.vocab.activities  # noqa: F401 — trigger dynamic discovery
import vultron.wire.as2.vocab.objects  # noqa: F401

from vultron.core.models.base import CoreObject
from vultron.wire.as2.vocab.base.base import as_Base
from vultron.wire.as2.vocab.base.registry import VOCABULARY


def _hint_contains_core_object(hint: typing.Any) -> bool:
    """Return True if *hint* is or transitively contains a CoreObject subclass."""
    if isinstance(hint, type) and issubclass(hint, CoreObject):
        return True
    args = getattr(hint, "__args__", None)
    if args:
        return any(_hint_contains_core_object(a) for a in args)
    return False


@pytest.mark.spec("ARCH-23-006")
def test_no_wire_field_annotation_names_core_object_subclass() -> None:
    """No wire-branch field annotation names a CoreObject subclass.

    Spec: ARCH-23-006

    Checks every class registered in ``VOCABULARY`` (wire-branch classes only).
    The AS2-faithful union ``as_Object | as_Link | str | None`` is permitted.
    A core type (``CoreObject`` subclass) in a wire field annotation is forbidden.
    """
    violations: list[str] = []

    for _type_name, cls in VOCABULARY.items():
        if not (isinstance(cls, type) and issubclass(cls, as_Base)):
            continue
        try:
            hints = typing.get_type_hints(cls, include_extras=True)
        except Exception:
            continue
        for field_name, hint in hints.items():
            if _hint_contains_core_object(hint):
                violations.append(f"{cls.__name__}.{field_name}: {hint!r}")

    assert not violations, (
        "Wire-branch field annotations name a CoreObject subclass (ARCH-23-006):\n"
        + "\n".join(f"  {v}" for v in sorted(violations))
        + "\n\nThe AS2-faithful reference union (as_Object | as_Link | str) is "
        "permitted. Remove CoreObject (and its subclasses) from wire field "
        "annotations — assign a wire projection instead."
    )
