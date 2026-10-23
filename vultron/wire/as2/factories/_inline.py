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
"""The object an activity introduces travels inline (AKM-02-004).

Most factories get this from their activity class, whose ``object_`` field is
typed as the full object, so Pydantic refuses a bare id.  A factory that builds
a generic vocabulary activity (``as_Create``) or whose class also admits a URI
for *received* activities (the embargo ``Invite``, ADR-0123) has no such
guard, and would put a bare id on the wire.  :func:`require_inline` is that
guard.
"""

from typing import TypeVar

from vultron.wire.as2.factories.errors import VultronActivityConstructionError

_Introduced = TypeVar("_Introduced")


def require_inline(
    value: object, cls: type[_Introduced], *, factory: str
) -> _Introduced:
    """Return *value* when it is an inline *cls*; refuse anything else.

    Args:
        value: The object the activity introduces.
        cls: The class that object must be.
        factory: The calling factory's name, for the error message.

    Raises:
        VultronActivityConstructionError: When *value* is a bare id, a link,
            or an object of another class.
    """
    if not isinstance(value, cls):
        raise VultronActivityConstructionError(
            f"{factory}: the object an activity introduces travels inline,"
            f" so it must be a {cls.__name__}, got {type(value).__name__}"
            " (AKM-02-004, AKM-03-003)"
        )
    return value
