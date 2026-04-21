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

from typing import Any, Mapping, Protocol, TypeGuard

from vultron.core.states.cs import CS_pxa, CS_vfd
from vultron.core.states.em import EM
from vultron.core.states.rm import RM


class PersistableModel(Protocol):
    @property
    def id_(self) -> str: ...

    @property
    def type_(self) -> str: ...

    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]: ...

    def model_copy(
        self, *, update: Mapping[str, Any] | None = None, deep: bool = False
    ) -> "PersistableModel": ...


class CaseStatusModel(Protocol):
    em_state: EM
    pxa_state: CS_pxa


class ParticipantStatusModel(Protocol):
    rm_state: RM
    vfd_state: CS_vfd


class CaseModel(PersistableModel, Protocol):
    case_participants: list
    vulnerability_reports: list
    active_embargo: object
    actor_participant_index: dict[str, str]
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
    def current_status(self) -> CaseStatusModel: ...


class ParticipantModel(PersistableModel, Protocol):
    accepted_embargo_ids: list
    embargo_consent_state: str
    participant_statuses: list[ParticipantStatusModel]
    attributed_to: object
    case_roles: list

    def append_rm_state(
        self, rm_state: RM, actor: str, context: str
    ) -> bool: ...


class OutboxCollectionModel(Protocol):
    items: list[object]


class ActorModel(PersistableModel, Protocol):
    inbox: OutboxCollectionModel
    outbox: OutboxCollectionModel


def is_case_model(obj: PersistableModel | None) -> TypeGuard[CaseModel]:
    return bool(
        obj is not None
        and getattr(obj, "type_", None) == "VulnerabilityCase"
        and hasattr(obj, "case_participants")
        and hasattr(obj, "record_event")
    )


def is_participant_model(
    obj: PersistableModel | object | None,
) -> TypeGuard[ParticipantModel]:
    return bool(
        obj is not None
        and getattr(obj, "type_", None) == "CaseParticipant"
        and hasattr(obj, "participant_statuses")
        and hasattr(obj, "append_rm_state")
    )


def has_outbox(obj: PersistableModel | None) -> TypeGuard[ActorModel]:
    return bool(obj is not None and hasattr(obj, "outbox"))


class LogEntryModel(PersistableModel, Protocol):
    """Protocol for a persisted canonical case log entry.

    Satisfied by :class:`~vultron.core.models.case_log_entry.VultronCaseLogEntry`.
    Used by the receive-side use case without importing from wire layer.
    """

    case_id: str
    log_index: int
    disposition: str
    term: int | None
    log_object_id: str
    event_type: str
    payload_snapshot: dict
    prev_log_hash: str
    entry_hash: str
    received_at: Any
    reason_code: str | None
    reason_detail: str | None


def is_log_entry_model(obj: object | None) -> TypeGuard[LogEntryModel]:
    """Return True if *obj* satisfies the :class:`LogEntryModel` protocol."""
    return bool(
        obj is not None
        and getattr(obj, "type_", None) == "CaseLogEntry"
        and hasattr(obj, "case_id")
        and hasattr(obj, "log_index")
        and hasattr(obj, "prev_log_hash")
        and hasattr(obj, "entry_hash")
    )
