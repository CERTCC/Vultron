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

"""Carry the objects a new case lists inline in the activity that creates it.

The CASE_MANAGER writes a new case's vulnerability items and case references
with the case (CSAF-03-008, CSAF-03-009), so no recipient holds them yet, and
the ``Create(VulnerabilityCase)`` carries each one in full (AKM-02-004).
"""

from collections.abc import Sequence
from typing import TypeVar

from vultron.core.models.case_reference import CaseReference
from vultron.core.models.vulnerability_item import VulnerabilityItem
from vultron.core.ports.case_persistence import CasePersistence
from vultron.errors import VultronValidationError

#: An object the case lists that the CASE_MANAGER wrote with it.
Owned = TypeVar("Owned", VulnerabilityItem, CaseReference)


def inline_owned(
    dl: CasePersistence,
    case_id: str,
    refs: Sequence[str | Owned],
    cls: type[Owned],
) -> list[str | Owned]:
    """Each of *refs* as the full *cls* object *dl* holds.

    An entry already inline is kept as it is.  The CASE_MANAGER wrote each
    one with the case, so an id *dl* cannot read is a fault: the Create
    would hand its recipient an id it cannot resolve.

    Raises:
        VultronValidationError: an id names no *cls* in *dl*.
    """
    carried: list[str | Owned] = []
    for ref in refs:
        if not isinstance(ref, str):
            carried.append(ref)
            continue
        obj = dl.read(ref)
        if not isinstance(obj, cls):
            raise VultronValidationError(
                f"case '{case_id}' names {cls.__name__} '{ref}', which"
                " this store cannot read, so the Create(VulnerabilityCase)"
                " cannot carry it inline (AKM-02-004)"
            )
        carried.append(obj)
    return carried


__all__ = ["Owned", "inline_owned"]
