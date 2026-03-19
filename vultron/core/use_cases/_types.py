"""Protocol types for DataLayer-retrieved objects used by core use cases.

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
    ) -> None: ...
