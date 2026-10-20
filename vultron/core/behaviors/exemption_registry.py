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

"""The one check that a received tree's named exemption is a registered one.

``create_receive_activity_tree`` takes several kinds of exemption (replica
emit, addressee, refusal notice), each with a closed registry of named
decisions.  A tree may pass only an exemption its registry holds, so the
registry stays the whole list (CS-22-001).
"""

from collections.abc import Mapping
from typing import Protocol, TypeVar

from vultron.errors import VultronWiringError

__all__ = ["require_registered"]


class _NamedExemption(Protocol):
    @property
    def name(self) -> str: ...


_E = TypeVar("_E", bound=_NamedExemption)


def require_registered(
    exemption: _E,
    registry: Mapping[str, _E],
    *,
    where: str,
    kind: str,
    registry_name: str,
    spec_id: str,
) -> None:
    """Refuse *exemption* unless *registry* holds it under its name.

    Args:
        exemption: The exemption a tree passed.
        registry: The closed registry for that kind of exemption.
        where: The factory call, for the error message.
        kind: The kind of exemption, e.g. ``"addressee"``.
        registry_name: The registry constant's name, for the message.
        spec_id: The requirement the registry serves.

    Raises:
        VultronWiringError: *registry* holds no equal exemption under
            ``exemption.name``.
    """
    if registry.get(exemption.name) != exemption:
        raise VultronWiringError(
            f"{where}: {kind} exemption {exemption.name!r} is not registered"
            f" in {registry_name} ({spec_id})"
        )
