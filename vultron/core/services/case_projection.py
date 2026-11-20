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

"""Project an actor's replica of a case through a render port (ADR-0219).

The core half of every projection call site: read the case and its ledger
from the actor's own store, cut them by the call site's profile, gather the
inputs the call site passes, and hand both to a
:class:`~vultron.core.ports.case_projection.CaseProjectionPort`.  The
publication pipeline's draft step and the operator's CSAF endpoint both call
:func:`project_case`, each with its own profile and publication status, so
the two cannot cut or date a projection differently.

- **The case is read whole.**  A stored case names most of what it holds by
  id, and a profile cuts what the case holds, so each participant, report,
  vulnerability item, reference, status and register embargo it names by id
  is read first (:func:`case_held_whole`).  The case in the store is not
  changed.
- **The inputs come from the store, never a clock.**  Every document date is
  the commit time of the ledger entry at the case's position
  (:func:`position_committed_at`, ADR-0176); the publisher is the projecting
  actor with the roles it holds in the case; the default credit is the
  case's ``REPORTER`` participants (ADR-0218).
- **It writes nothing.**  No DataLayer write, no ledger entry, no activity:
  a projection is a read of the replica.
"""

from collections.abc import Sequence
from datetime import datetime

from pydantic import JsonValue

from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_projection import (
    ProjectingActor,
    ProjectionCut,
    ProjectionInputs,
    PublicationStatus,
    reporter_acknowledgments,
)
from vultron.core.models.case_projection_profile import ProjectionProfile
from vultron.core.models.case_reference import CaseReference
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.embargo_register.entry import EmbargoRegisterEntry
from vultron.core.models.report import VulnerabilityReport
from vultron.core.models.vulnerability_item import VulnerabilityItem
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.case_projection import CaseProjectionPort
from vultron.core.services.held_references import read_held
from vultron.core.sync_helpers.ledger_reads import sorted_case_ledger_entries
from vultron.enums.roles import CVDRole
from vultron.errors import (
    VultronNotFoundError,
    VultronProjectionError,
    VultronWiringError,
)
from vultron.primitives import same_actor_id


def require_projection_port(port: object) -> CaseProjectionPort:
    """*port*, when it is a :class:`CaseProjectionPort`.

    Raises:
        VultronWiringError: *port* is missing or is no projection port.  A
            projection has no fallback renderer (ADR-0219).
    """
    if not isinstance(port, CaseProjectionPort):
        raise VultronWiringError(
            "case_projection_port not available; core cannot render a case"
            f" projection itself (got {type(port).__name__}, ADR-0219)"
        )
    return port


def _register_held_whole(
    entries: Sequence[EmbargoRegisterEntry], dl: CasePersistence
) -> list[EmbargoRegisterEntry]:
    """*entries* with each embargo named by id read as its object."""
    held: list[EmbargoRegisterEntry] = []
    for entry in entries:
        if not isinstance(entry.embargo, str):
            held.append(entry)
            continue
        refs: list[str | EmbargoEvent] = [entry.embargo]
        (embargo,) = read_held(refs, EmbargoEvent, dl)
        held.append(entry.model_copy(update={"embargo": embargo}))
    return held


def case_held_whole(
    case: VulnerabilityCase, dl: CasePersistence
) -> VulnerabilityCase:
    """A copy of *case* holding inline each object it names by id in *dl*.

    The participants, reports, vulnerability items, references, statuses and
    register embargoes a profile cuts.  *case* is not changed.

    Raises:
        VultronProjectionError: *dl* does not hold an object *case* names.
    """
    try:
        update = {
            "case_participants": read_held(
                list(case.case_participants), CaseParticipant, dl
            ),
            "vulnerability_reports": read_held(
                list(case.vulnerability_reports), VulnerabilityReport, dl
            ),
            "vulnerability_items": read_held(
                list(case.vulnerability_items), VulnerabilityItem, dl
            ),
            "case_references": read_held(
                list(case.case_references), CaseReference, dl
            ),
            "case_statuses": read_held(
                list(case.case_statuses), CaseStatus, dl
            ),
            "embargo_register": _register_held_whole(
                case.embargo_register, dl
            ),
        }
    except VultronNotFoundError as exc:
        raise VultronProjectionError(
            f"case '{case.id_}' names an object this replica does not hold,"
            f" so it cannot be projected: {exc}"
        ) from exc
    return case.model_copy(update=update)


def position_committed_at(
    case: VulnerabilityCase, ledger: Sequence[CaseLedgerEntry]
) -> datetime:
    """The commit time of the entry at *case*'s ledger position.

    Every date a projection's tracking states is this time (CSAF-06-007),
    so the same inputs give the same document (ADR-0176).

    Raises:
        VultronProjectionError: *ledger* holds no entry at the position: a
            case whose ledger is empty, or a replica that holds the case
            file but not yet the entry it reflects.
    """
    position = case.ledger_position
    for entry in ledger:
        if (
            entry.log_index == position.log_index
            and entry.entry_hash == position.entry_hash
        ):
            return entry.published
    raise VultronProjectionError(
        f"case '{case.id_}' is at ledger index {position.log_index}, and"
        " this replica holds no entry there to date a projection by"
        " (CSAF-06-007)"
    )


def _roles_of(case: VulnerabilityCase, actor_id: str) -> tuple[CVDRole, ...]:
    """The roles *actor_id* holds in *case*, in the order the case lists
    them, across every record of the actor (CM-26-001)."""
    roles: dict[CVDRole, None] = {}
    for participant in case.case_participants:
        if not isinstance(participant, CaseParticipant):
            continue
        attributed = participant.attributed_to
        if attributed and same_actor_id(str(attributed), actor_id):
            roles.update(dict.fromkeys(participant.case_roles))
    return tuple(roles)


def projecting_actor(
    case: VulnerabilityCase, actor_id: str, dl: CasePersistence
) -> ProjectingActor:
    """*actor_id* as the publisher of a projection of *case*.

    Its name is the one its record in *dl* states, else its id; its roles
    are the ones it holds in *case*, which must hold its participants
    inline (:func:`case_held_whole`).
    """
    record = dl.read(actor_id)
    name = getattr(record, "name", None)
    return ProjectingActor(
        id_=actor_id,
        name=name if isinstance(name, str) and name.strip() else actor_id,
        roles=_roles_of(case, actor_id),
    )


def case_projection(
    dl: CasePersistence,
    case_id: str,
    actor_id: str,
    profile: ProjectionProfile,
    status: PublicationStatus,
) -> tuple[ProjectionCut, ProjectionInputs]:
    """The cut of *case_id* by *profile* and the inputs its call site passes.

    Args:
        dl: The projecting actor's own store, holding its replica.
        case_id: The case, by full id.
        actor_id: The projecting actor, the document's publisher.
        profile: The call site's profile.
        status: The call site's publication status.

    Raises:
        VultronNotFoundError: *dl* holds no case *case_id*.
        VultronProjectionError: The replica lacks an object the case names,
            or the ledger entry at its position.
        VultronActivityConstructionError: A profile substitution cannot be
            made.
    """
    stored = dl.read_case(case_id)
    if stored is None:
        raise VultronNotFoundError("VulnerabilityCase", case_id)
    case = case_held_whole(stored, dl)
    ledger = sorted_case_ledger_entries(dl, case.id_)
    inputs = ProjectionInputs(
        status=status,
        projecting_actor=projecting_actor(case, actor_id, dl),
        position_committed_at=position_committed_at(case, ledger),
        default_acknowledgments=reporter_acknowledgments(case),
    )
    return ProjectionCut.of(case, ledger, profile), inputs


def project_case(
    dl: CasePersistence,
    case_id: str,
    actor_id: str,
    profile: ProjectionProfile,
    status: PublicationStatus,
    port: object,
) -> dict[str, JsonValue]:
    """The projection of *case_id*, rendered through *port*.

    See :func:`case_projection` for the arguments.

    Raises:
        VultronWiringError: *port* is no :class:`CaseProjectionPort`,
            checked before anything is read.
        VultronNotFoundError: *dl* holds no case *case_id*.
        VultronProjectionError: The replica cannot be projected.
    """
    renderer = require_projection_port(port)
    cut, inputs = case_projection(dl, case_id, actor_id, profile, status)
    return renderer.render(cut, inputs)


__all__ = [
    "case_held_whole",
    "case_projection",
    "position_committed_at",
    "project_case",
    "projecting_actor",
    "require_projection_port",
]
