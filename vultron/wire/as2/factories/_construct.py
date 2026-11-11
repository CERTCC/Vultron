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
"""The one place an outbound factory builds its activity.

Every factory in :mod:`vultron.wire.as2.factories` builds its activity
through :func:`build_activity`, so the rule each one keeps is written once:
a validation failure is logged and raised as
:class:`~vultron.errors.VultronActivityConstructionError`, chained to its
cause (AF-04).

The fields are passed as a callable, not as a mapping, so the argument
expressions run inside the helper's scope.  Some of them refuse on purpose:
``_named_case`` and ``as_answered`` raise ``ValidationError`` when a case
or a held activity is not the kind the factory answers, and that refusal
must reach the caller as a construction error too.
"""

import logging
from collections.abc import Callable, Mapping
from typing import Any

from pydantic import ValidationError

from vultron.errors import VultronActivityConstructionError

logger = logging.getLogger(__name__)


def build_activity[A](
    label: str,
    cls: Callable[..., A],
    fields: Callable[[], Mapping[str, Any]],
    *,
    also: tuple[type[Exception], ...] = (),
) -> A:
    """Build ``cls(**fields())`` for the factory named *label*.

    Args:
        label: The factory's name, which starts the error message.
        cls: The activity class (or a callable that builds one).
        fields: Returns the constructor's keyword arguments.  It runs inside
            the guarded scope, so an argument expression that raises
            ``ValidationError`` is reported like a constructor failure.
        also: Further exception types to report the same way, for a factory
            whose argument parsing raises another error (``parse_activity``
            raises ``VultronParseError``).

    Raises:
        VultronActivityConstructionError: When building the fields or the
            activity raises ``ValidationError`` or one of *also*.
    """
    caught: tuple[type[Exception], ...] = (ValidationError, *also)
    try:
        return cls(**fields())
    except caught as exc:
        logger.warning("%s: invalid arguments: %s", label, exc)
        raise VultronActivityConstructionError(
            f"{label}: invalid arguments"
        ) from exc


__all__ = ["build_activity"]
