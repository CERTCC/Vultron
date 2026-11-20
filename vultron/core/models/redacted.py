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

"""The ``Redacted`` marker: a preview's value, withheld (ADR-0193, ADR-0217).

A preview is a limited view of an object for a recipient not yet entitled to
the whole of it.  A sender that builds one may put a marker where a value
would be, to say there is a value it withholds from this recipient::

    {"type": "Redacted", "summary": "Embargo pending"}

The marker carries no field but ``type`` and an optional ``summary`` giving
the reason (MV-12-003).  This class refuses any other field when it is built,
so a sender cannot put the value it withholds in the marker (MV-12-005).  A
received marker's other keys are set aside at the parse edge like any unknown
key (MV-11-003), so the receiver reads a clean marker.  It has no ``id``,
because it is a value, not an object of its own.

A preview reads a marker anywhere inside it, at any depth (MV-12-001), and a
marker outside a preview is refused (MV-12-002).  :data:`Redactable` is how a
preview's field admits one.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from vultron.core.models.base import ValidatedAssignmentMixin
from vultron.primitives import NonEmptyString

#: The wire ``type`` of a redaction marker.
REDACTED_TYPE: Literal["Redacted"] = "Redacted"


class Redacted(ValidatedAssignmentMixin, BaseModel):
    """A value withheld from the recipient of a preview (MV-12-003).

    A value object: it has no ``id`` and no clock stamps, and two markers with
    the same reason are equal.  ``extra="forbid"`` refuses every field but
    ``type`` and ``summary`` (MV-12-005), including the AS2 object properties,
    such as ``id``, ``name`` or ``content``, that could carry the withheld
    value.

    Fields:
        type_: Always ``Redacted`` (wire ``type``).
        summary: Why the value is withheld, if the sender says.  It is AS2
            ``summary``, so it needs no Vultron term.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        extra="forbid",
        frozen=True,
    )

    type_: Literal["Redacted"] = Field(
        default=REDACTED_TYPE,
        validation_alias="type",
        serialization_alias="type",
    )
    summary: NonEmptyString | None = Field(
        default=None,
        description="Why the value is withheld from the recipient.",
    )


#: A preview's value or the marker that withholds it (ADR-0217).  A preview
#: field ``name: Redactable[NonEmptyString] | None`` holds a name, a marker, or
#: nothing.
type Redactable[T] = T | Redacted
