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

"""Protocol types for domain model objects used by core use cases.

Both wire-layer types (e.g. VulnerabilityCase) and domain types (e.g.
VultronCase) conform structurally to these Protocols, so use cases can call
methods on DataLayer results without importing wire-layer classes.
"""

from typing import Protocol

from vultron.core.states.rm import RM


class CaseModel(Protocol):
    as_id: str
    case_participants: list
    vulnerability_reports: list
    active_embargo: object
    actor_participant_index: dict
    events: list
    attributed_to: object
    notes: list
    case_statuses: list
    proposed_embargoes: list
    name: str | None

    def set_embargo(self, embargo_id: str) -> None: ...
    def add_participant(self, participant: object) -> None: ...
    def remove_participant(self, participant_id: str) -> None: ...
    def record_event(self, obj_id: str, event_type: str) -> None: ...

    @property
    def current_status(self) -> object: ...


class ParticipantModel(Protocol):
    as_id: str
    accepted_embargo_ids: list
    participant_statuses: list
    attributed_to: object

    def append_rm_state(
        self, rm_state: RM, actor: str, context: str
    ) -> bool: ...
