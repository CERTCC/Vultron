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
"""Find the state-bearing records in one entry's payload snapshot (CEH-04).

What an entry records is its activity's carried ``object``: the record a
``Create(CaseParticipant)`` seats, the status an ``Add(ParticipantStatus)``
adds, the row a ``Create`` or ``Update(EmbargoConsent)`` writes, and the whole
case a ``Create`` or ``Update(VulnerabilityCase)`` carries.  Nothing else in the
snapshot is read: an ``Add``'s ``target`` holds the participant as stored when
the snapshot was taken, which can already hold the statuses that the *next*
entries add, as a ``Leave``'s cascade does (CM-23-022).

Every state-bearing record in the object is collected, in the order the object
records it, except two kinds of copy that are not the record's own state:

* anything inside an ``Offer``.  A recommendation or a proposed transfer
  carries a participant object for an actor not yet in the case, at
  ``RM.START`` (CEH-04-014), and an ownership offer carries a copy of the case.
* a case status nested in a participant status.  That is the participant's
  report of the case's public state; the case's own public state changes only
  when the CASE_MANAGER adopts it in its own case status (CEH-03-012).
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import datetime
from enum import StrEnum
from typing import Any, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from vultron.core.models._helpers import parse_published
from vultron.core.predicates.type_terms import first_named
from vultron.measure.ledger import actor_uri, first_present

#: The activity type whose whole subtree is a recommendation or an offer.
_OFFER = "Offer"

#: Activity fields that name where the act lands, not what it records: an
#: Invite's ``target`` is a case stub whose status says nothing true about the
#: case (``VulnerabilityCaseStub``).
_PLACE_KEYS = frozenset({"target", "origin"})


_E = TypeVar("_E", bound=StrEnum)


def member_of(enum: type[_E], value: object) -> _E | None:
    """The member of *enum* that *value* spells, or ``None``."""
    if not isinstance(value, str):
        return None
    try:
        return enum(value)
    except ValueError:
        return None


def parse_time(value: object) -> datetime | None:
    """Parse an ISO 8601 timestamp as UTC, or return ``None`` when it is not one.

    A time with no offset is read as UTC, so any two times the history holds
    compare (the shared ``parse_published`` rule, CS-22-001).
    """
    return parse_published(value)


def roles_of(*values: object) -> set[str]:
    """The upper-cased role names in any of *values* that is a list."""
    return {
        role.upper()
        for value in values
        if isinstance(value, list)
        for role in value
        if isinstance(role, str) and role
    }


class ParticipantRecord(BaseModel):
    """A ``CaseParticipant`` as one snapshot records it.

    Fields:
        actor: The participant's actor.
        joined: ``False`` for an inert participant; ``None`` when unstated.
        roles: Its case roles, upper-cased.
        statuses: Its participant statuses, in recorded order.
        consents: Its embargo consent rows, in recorded order.
    """

    model_config = ConfigDict(frozen=True)

    actor: str
    joined: bool | None = None
    roles: set[str] = Field(default_factory=set)
    statuses: list[dict[str, Any]] = Field(default_factory=list)
    consents: list[dict[str, Any]] = Field(default_factory=list)


class SnapshotRecords(BaseModel):
    """The state-bearing records of one payload snapshot, in recorded order.

    Fields:
        participants: Every participant record outside an offer.
        loose_statuses: Every participant status outside a participant
            record and outside an offer.
        case_statuses: Every case status outside a participant status and
            outside an offer.
        consents: Every consent row outside a participant record and outside
            an offer.
        register_entries: Every embargo register entry of a carried case.
        nameless_participants: How many participant records named no actor.
    """

    model_config = ConfigDict(frozen=True)

    participants: list[ParticipantRecord] = Field(default_factory=list)
    loose_statuses: list[dict[str, Any]] = Field(default_factory=list)
    case_statuses: list[dict[str, Any]] = Field(default_factory=list)
    consents: list[dict[str, Any]] = Field(default_factory=list)
    register_entries: list[dict[str, Any]] = Field(default_factory=list)
    nameless_participants: int = 0


def _dicts(value: object) -> list[dict[str, Any]]:
    """The dict items of *value* when it is a list, else none."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _walk(
    node: object, parents: tuple[str, ...]
) -> Iterator[tuple[dict[str, Any], tuple[str, ...]]]:
    """Yield every dict under *node* outside an offer, with its ancestor types."""
    if isinstance(node, list):
        for item in node:
            yield from _walk(item, parents)
        return
    if not isinstance(node, dict):
        return
    node_type = _node_type(node)
    if node_type == _OFFER:
        return
    yield node, parents
    here = (*parents, node_type)
    for key, child in node.items():
        if key not in _PLACE_KEYS and isinstance(child, (dict, list)):
            yield from _walk(child, here)


#: The node types this reader tells apart.
_READ_TYPES: frozenset[str] = frozenset(
    {
        _OFFER,
        "CaseParticipant",
        "ParticipantStatus",
        "CaseStatus",
        "EmbargoConsent",
        "VulnerabilityCase",
    }
)


def _node_type(node: Mapping[str, Any]) -> str:
    """The one of :data:`_READ_TYPES` *node*'s ``type`` names, else ``""``.

    A received ``type`` may be a list, kept as it arrived (ADR-0196).
    """
    return first_named(node.get("type"), _READ_TYPES) or ""


def _participant_record(node: Mapping[str, Any]) -> ParticipantRecord | None:
    """Read one ``CaseParticipant`` node, or ``None`` when it names no actor."""
    actor = actor_uri(first_present(node, "attributedTo", "attributed_to"))
    if actor is None:
        return None
    joined = node.get("joined")
    return ParticipantRecord(
        actor=actor,
        joined=joined if isinstance(joined, bool) else None,
        roles=roles_of(first_present(node, "caseRoles", "case_roles")),
        statuses=_dicts(
            first_present(node, "participantStatuses", "participant_statuses")
        ),
        consents=_dicts(
            first_present(node, "embargoConsents", "embargo_consents")
        ),
    )


def snapshot_records(snapshot: Mapping[str, Any]) -> SnapshotRecords:
    """Collect the state-bearing records *snapshot*'s activity carries.

    Only the activity's ``object`` is read, and nothing under an ``Offer``
    (module docstring).  A snapshot that is itself an ``Offer`` records none.
    """
    participants: list[ParticipantRecord] = []
    loose: list[dict[str, Any]] = []
    case_statuses: list[dict[str, Any]] = []
    consents: list[dict[str, Any]] = []
    register: list[dict[str, Any]] = []
    nameless = 0
    if _node_type(snapshot) == _OFFER:
        return SnapshotRecords()
    for node, parents in _walk(snapshot.get("object"), ()):
        node_type = _node_type(node)
        in_participant = "CaseParticipant" in parents
        if node_type == "CaseParticipant":
            record = _participant_record(node)
            if record is None:
                nameless += 1
            else:
                participants.append(record)
        elif node_type == "ParticipantStatus" and not in_participant:
            loose.append(node)
        elif node_type == "CaseStatus" and "ParticipantStatus" not in parents:
            case_statuses.append(node)
        elif node_type == "EmbargoConsent" and not in_participant:
            consents.append(node)
        elif node_type == "VulnerabilityCase":
            register.extend(
                _dicts(
                    first_present(node, "embargoRegister", "embargo_register")
                )
            )
    return SnapshotRecords(
        participants=participants,
        loose_statuses=loose,
        case_statuses=case_statuses,
        consents=consents,
        register_entries=register,
        nameless_participants=nameless,
    )
