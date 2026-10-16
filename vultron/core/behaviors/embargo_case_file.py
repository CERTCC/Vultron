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

"""Read and save the part of a case file embargo entries change (ADR-0124).

Shared by the CASE_MANAGER's commit-then-apply helper
(:mod:`vultron.core.behaviors.embargo.copy_commit`) and the replica copy
frame (:mod:`vultron.core.behaviors.sync.nodes.embargo_copy_effect`).  It
sits outside the ``embargo`` package so the replica frame can import it
without loading that package, whose nodes subclass the frame.
"""

from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_apply import (
    EmbargoCaseFile,
    changed_objects,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.errors import VultronNotFoundError


def read_embargo_case_file(
    datalayer: CasePersistence, case_id: str
) -> EmbargoCaseFile:
    """The case *case_id* and the participant records its roster indexes.

    A roster entry whose record this store does not hold is left out, as on a
    partial replica (ADR-0087); a consent-row entry for that actor is then
    refused by the apply function rather than written.

    Raises:
        VultronNotFoundError: *datalayer* holds no such case.
    """
    case = datalayer.read_case(case_id)
    if not isinstance(case, VulnerabilityCase):
        raise VultronNotFoundError("VulnerabilityCase", case_id)
    participants: dict[str, CaseParticipant] = {}
    for actor_id, participant_id in case.actor_participant_index.items():
        record = datalayer.read(participant_id)
        if isinstance(record, CaseParticipant):
            participants[actor_id] = record
    return EmbargoCaseFile(case=case, participants=participants)


def save_case_file(
    datalayer: CasePersistence,
    before: EmbargoCaseFile,
    after: EmbargoCaseFile,
) -> None:
    """Save every object *after* changed from *before*, in one write."""
    objects = changed_objects(before, after)
    if objects:
        datalayer.save_many(list(objects))


__all__ = ["read_embargo_case_file", "save_case_file"]
