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

"""Read the objects a stored case names by id (DL-08-001).

A stored case lists most of what it holds by id: its participants, reports
and the rest are records of their own.  A reader that needs the objects, not
the ids, reads each one here, so every such reader resolves a reference the
same way and refuses the same missing record.
"""

from vultron.core.ports.case_persistence import CasePersistence
from vultron.errors import VultronNotFoundError


def read_held[T](
    refs: list[str | T], kind: type[T], dl: CasePersistence
) -> list[T]:
    """*refs* with every bare id read from *dl* as a *kind*, in order.

    An entry already held inline is kept as it is.

    Raises:
        VultronNotFoundError: A reference names no *kind* in *dl*.
    """
    resolved: list[T] = []
    for ref in refs:
        if not isinstance(ref, str):
            resolved.append(ref)
            continue
        record = dl.read(ref)
        if not isinstance(record, kind):
            raise VultronNotFoundError(kind.__name__, ref)
        resolved.append(record)
    return resolved


__all__ = ["read_held"]
