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

"""The received termination's cause guard (EMB-13-005)."""

from typing import cast

from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerConditionWithPorts
from vultron.core.models.embargo_termination import (
    CASE_MANAGER_ONLY_CAUSE_KINDS,
    EmbargoTermination,
)
from vultron.core.participants.authority import resolve_case_manager_id
from vultron.core.ports.case_persistence import CasePersistence


class TerminationCauseIsAdmissibleNode(DataLayerConditionWithPorts):
    """Guard: a received termination names no cause its sender may not name.

    FAILURE when *termination*'s cause is one only the CASE_MANAGER names
    (``THREAT_SIGNAL``) and *sender_actor_id* is not the case's CASE_MANAGER;
    SUCCESS otherwise, no cause and an owner's ``FIX_READY``,
    ``FIX_DEPLOYED`` or ``OTHER`` claim included (EMB-13-005).  The reason
    directs the sender to a case status update setting ``P``, ``X`` or
    ``A``: that is how a threat signal ends an embargo, after which the
    CASE_MANAGER terminates it with the signals the case carries.  Reading
    the ``Remove`` as that status change instead would commit a status change
    no participant sent.

    It reads the cause, not the sender's standing: the use case's declared
    rule has already admitted the sender to send a ``Remove`` at all
    (HP-01-006).  It runs among the received tree's precondition guards, so a
    refused cause is never committed (CLP-10-006).  At a replica the declared
    rule admits the CASE_MANAGER alone, so this guard always passes there.
    """

    def __init__(
        self,
        case_id: str,
        sender_actor_id: str,
        termination: EmbargoTermination,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self._sender_actor_id = sender_actor_id
        self._termination = termination

    def update(self) -> Status:
        cause = self._termination.cause
        if cause is None or cause.kind not in CASE_MANAGER_ONLY_CAUSE_KINDS:
            return Status.SUCCESS
        if (f := self._require_datalayer()) is not None:
            return f
        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure
        manager_id = resolve_case_manager_id(
            case, cast(CasePersistence, self.datalayer)
        )
        if manager_id is not None and manager_id == self._sender_actor_id:
            return Status.SUCCESS
        self.feedback_message = (
            f"Refused termination on case '{self.case_id}': only the"
            f" CASE_MANAGER's Remove may name a {cause.kind} cause, and"
            f" '{self._sender_actor_id}' is not the CASE_MANAGER.  A threat"
            " signal ends an embargo through a case status update"
            " (Add(CaseStatus)) setting P, X or A; the CASE_MANAGER then"
            " terminates the embargo with the signals the case carries"
            " (EMB-13-005)"
        )
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE
