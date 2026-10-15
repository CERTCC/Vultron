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

"""Hold the ``EmbargoEvent`` a ledger entry names, from the copy it carries.

A path that changes an embargo register entry must hold that embargo's record
in the same store (EMB-18-003).  A canonical entry carries the
``EmbargoEvent`` inline, so a replica stores it from there rather than
fetching it from the proposer (CLP-10-017); a bare id is enough when the
record is already here.  Shared by the replica slots that replay an embargo
act.
"""

from typing import Any

from pydantic import ValidationError

from vultron.core.models._helpers import project_wire_snapshot_to_core
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.ports.case_persistence import CasePersistence


def store_carried_embargo(
    datalayer: CasePersistence, embargo_data: Any, embargo_id: str
) -> str | None:
    """Store the entry's inline ``EmbargoEvent`` unless *datalayer* holds it.

    Returns ``None`` when the record is held (already, or now), else the
    reason it cannot be: the entry names it by id only, or its inline copy
    is malformed.
    """
    if datalayer.read(embargo_id) is not None:
        return None
    if not isinstance(embargo_data, dict):
        return (
            f"embargo '{embargo_id}' is not stored here and the entry names"
            " it by id only, so it cannot be reconstructed"
        )
    try:
        embargo = EmbargoEvent.model_validate(
            project_wire_snapshot_to_core(EmbargoEvent, embargo_data)
        )
    except ValidationError as exc:
        return f"embargo '{embargo_id}' in the entry is malformed: {exc}"
    datalayer.create(embargo)
    return None


__all__ = ["store_carried_embargo"]
