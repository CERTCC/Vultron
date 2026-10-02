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

"""
Case-owner SIGNATORY seeding for the creation-time embargo (CM-14-003).

A leaf of ``InitializeDefaultEmbargoNode``'s creation arm, split from
the sibling ``embargo.py`` to keep both leaves under the BTND-07-004 size cap.
``embargo.py`` re-exports it.
"""

from py_trees.common import Status

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.states.participant_embargo_consent import PEC, PEC_Trigger


class SeedOwnerAsSignatoryNode(DataLayerActionWithPorts):
    """Seed the case-owner participant as SIGNATORY (CM-14-003).

    The owner is read from the case — ``attributed_to``, the CASE_OWNER
    (CM-02-008, CP-09-001) — never from the actor running the tree.  On the
    CASE_MANAGER's creation path those differ: the CASE_MANAGER runs the tree
    and the proposing actor owns the case.  Keying on the executing actor
    seeds nobody there, so the owner comes from the case and every creation
    path shares this one seeding node.

    The owner's participant record is created before the embargo is
    initialized (CM-14-002), so a missing record — or a case naming no owner
    — is a broken precondition: the node fails rather than report a seed it
    did not make (ARCH-15).
    """

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "case_id": PortInformation(data_type=str, required=True),
        "default_embargo_initialized": PortInformation(
            data_type=object, required=True
        ),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "case_id": "/case_id",
            "default_embargo_initialized": "/default_embargo_initialized",
        }

    def initialise(self) -> None:
        super().initialise()
        self.bb_case_id: str = self.get_input("case_id")
        self.embargo_initialized = self.get_input(
            "default_embargo_initialized"
        )

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case_id = self.bb_case_id
        embargo_initialized = self.embargo_initialized
        if embargo_initialized is False:
            return Status.SUCCESS

        stored_case, failure = self._require_case(case_id)
        if failure is not None:
            return failure  # Regime 1 (ADR-0087)

        owner_id = _as_id(stored_case.attributed_to)
        participant_id = (
            stored_case.actor_participant_index.get(owner_id)
            if owner_id is not None
            else None
        )
        participant = (
            self.datalayer.read(participant_id, raise_on_missing=False)
            if participant_id
            else None
        )
        if not isinstance(participant, CaseParticipant):
            self.feedback_message = (
                f"case owner '{owner_id}' has no participant record in case"
                f" '{case_id}' — cannot seed SIGNATORY (CM-14-002 creates it"
                " first)"
            )
            self.logger.error("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        embargo_id = _as_id(stored_case.active_embargo)
        if participant.embargo_consent_state not in (
            PEC.SIGNATORY,
            PEC.DECLINED,
        ):
            participant.apply_pec_transition(PEC_Trigger.ACCEPT)
        if embargo_id:
            participant.add_accepted_embargo(embargo_id)
        self.datalayer.save(participant)
        self.logger.info(
            "Seeded case-owner participant '%s' (actor '%s') as SIGNATORY"
            " for embargo in case '%s' (CM-14-003)",
            participant_id,
            owner_id,
            case_id,
        )
        return Status.SUCCESS
