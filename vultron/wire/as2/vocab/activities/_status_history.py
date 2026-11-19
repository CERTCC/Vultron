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

"""The shape both status ``Add`` activities share (ADR-0204).

A status ``Add`` names the status history it extends in ``target`` and its
case in ``context``.  The case's own status ``Add`` extends that case's
history, ``<case>/statuses``.
"""

from vultron.core.models.status_history import (
    is_status_history_id,
    status_history_id,
)
from vultron.wire.as2.context_agreement import cases_named_by_context


def require_status_history_add(
    activity: object, *, case_history: bool
) -> None:
    """Refuse a status ``Add`` that names no history or no single case.

    Args:
        activity: The status ``Add`` being validated.
        case_history: ``True`` for ``Add(CaseStatus)``, whose ``target``
            must be the history of the case its ``context`` names.

    Raises:
        ValueError: When ``target`` is not a status history id, ``context``
            names no case or more than one, or a case status ``Add`` names
            another case's history.
    """
    target = getattr(activity, "target", None)
    if not is_status_history_id(target):
        raise ValueError(
            f"a status Add's target must be a status history"
            f" '<record>/statuses', got {target!r} (ADR-0204)"
        )
    cases = cases_named_by_context(activity)
    if len(cases) != 1:
        raise ValueError(
            "a status Add's context must name its one case, got"
            f" {sorted(cases) or 'none'} (ADR-0204)"
        )
    (case_id,) = cases
    if case_history and target != status_history_id(case_id):
        raise ValueError(
            f"an Add(CaseStatus) extends its case's history"
            f" '{status_history_id(case_id)}', not {target!r} (ADR-0204)"
        )


__all__ = ["require_status_history_add"]
