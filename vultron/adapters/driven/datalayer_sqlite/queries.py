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

"""Query and search operations for the SQLite data layer."""

import logging
from typing import Any, cast

from sqlalchemy import func
from sqlmodel import Session, select

from vultron.adapters.driven.db_record import Record
from vultron.core.models.protocols import PersistableModel
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.models.protocols import is_case_model
from vultron.core.ports.datalayer import StorableRecord

from .schema import VultronObjectRecord, matches_short_id

logger = logging.getLogger(__name__)

#: Actor types used by find_actor_by_short_id
_ACTOR_TYPES: frozenset[str] = frozenset(
    {"Actor", "Person", "Organization", "Service", "Application", "Group"}
)
_CASE_TYPES: frozenset[str] = frozenset({"VulnerabilityCase"})


def count_all(
    dl: "Any",  # SqliteDataLayer
) -> dict[str, int]:
    """Return a dict mapping type → record count.

    Args:
        dl: The SqliteDataLayer instance.

    Returns:
        Mapping of ``{type_name: count}``.  Includes a ``"_default"``
        key with value ``0`` (SQLite has no default table concept).
    """
    with Session(dl._engine) as session:
        stmt = dl._scoped(
            select(
                VultronObjectRecord.type_,
                func.count(),  # type: ignore[call-overload]
            ).group_by(VultronObjectRecord.type_)
        )
        rows = session.exec(stmt).all()
    counts: dict[str, int] = {"_default": 0}
    for type_name, count in rows:
        counts[type_name] = count
    return counts


def by_type(
    dl: "Any",  # SqliteDataLayer
    type_: str,
) -> dict[str, dict[str, Any]]:
    """Return all records of a given type as a ``{id_: data_}`` dict.

    Args:
        dl: The SqliteDataLayer instance.
        type_: Object type to query.

    Returns:
        Mapping of ``{id_: data_dict}`` for every record of that type.
    """
    with Session(dl._engine) as session:
        stmt = dl._scoped(
            select(VultronObjectRecord).where(
                VultronObjectRecord.type_ == type_
            )
        )
        rows = session.exec(stmt).all()
    results: dict[str, dict[str, Any]] = {}
    for row in rows:
        results[row.id_] = row.data
    return results


def all(
    dl: "Any",  # SqliteDataLayer
    table: str | None = None,
) -> list[StorableRecord] | dict[str, PersistableModel]:
    """Return all records, optionally filtered by type.

    Args:
        dl: The SqliteDataLayer instance.
        table: When provided, returns a list of ``Record`` objects for
            that type.  When ``None``, returns a dict mapping object
            ``id_`` → reconstituted domain object across all types.

    Returns:
        List of ``StorableRecord`` (when *table* is given) or a dict of
        ``{id_: domain_object}``.
    """
    with Session(dl._engine) as session:
        if table is not None:
            stmt = dl._scoped(
                select(VultronObjectRecord).where(
                    VultronObjectRecord.type_ == table
                )
            )
            rows = session.exec(stmt).all()
            return [
                Record(id_=row.id_, type_=row.type_, data_=row.data)
                for row in rows
            ]

        stmt = dl._scoped(select(VultronObjectRecord))
        rows = session.exec(stmt).all()
        results: dict[str, PersistableModel] = {}
        for row in rows:
            obj = dl._from_row(row)
            if obj is not None:
                results[obj.id_] = obj
        return results


def exists(
    dl: "Any",  # SqliteDataLayer
    table: str,
    id_: str,
) -> bool:
    """Check whether a record exists.

    Args:
        dl: The SqliteDataLayer instance.
        table: Object type.
        id_: Object identifier.

    Returns:
        ``True`` if found; ``False`` otherwise.
    """
    with Session(dl._engine) as session:
        stmt = dl._scoped(
            select(VultronObjectRecord).where(
                VultronObjectRecord.type_ == table,
                VultronObjectRecord.id_ == id_,
            )
        )
        row = session.exec(stmt).first()
        return row is not None


def ping(dl: "Any") -> bool:  # SqliteDataLayer
    """Probe storage; returns ``True`` when the backend is accessible.

    Args:
        dl: The SqliteDataLayer instance.

    Returns:
        ``True`` if storage is accessible.
    """
    with Session(dl._engine) as session:
        session.exec(select(VultronObjectRecord).limit(1)).all()
    return True


def list_objects(
    dl: "Any",  # SqliteDataLayer
    type_key: str,
) -> list[PersistableModel]:
    """Return fully rehydrated domain objects of the given type.

    Unlike :func:`by_type` (which returns raw ``{id_: data_dict}``
    mappings), this function applies the full ``_from_row`` pipeline
    (vocabulary reconstruction → field rehydration →
    semantic-class coercion) and returns typed domain objects.

    Rows that cannot be reconstructed are silently skipped with a
    ``DEBUG`` log entry.

    Args:
        dl: The SqliteDataLayer instance.
        type_key: Object type string (e.g. ``"VulnerabilityCase"``).

    Returns:
        List of rehydrated domain objects of the requested type.
    """
    with Session(dl._engine) as session:
        stmt = dl._scoped(
            select(VultronObjectRecord).where(
                VultronObjectRecord.type_ == type_key
            )
        )
        rows = session.exec(stmt).all()
    results: list[PersistableModel] = []
    for row in rows:
        obj = dl._from_row(row)
        if obj is None:
            logger.debug(
                "list_objects(%r): could not reconstruct row id=%r — skipping",
                type_key,
                row.id_,
            )
            continue
        results.append(obj)
    return results


def find_actor_by_short_id(
    dl: "Any",  # SqliteDataLayer
    short_id: str,
) -> PersistableModel | None:
    """Find an actor by the last path segment of its URI.

    Searches across all actor-type rows (Actor, Person, Organization,
    Service, Application, Group) and returns the first actor whose
    ``id_`` ends with ``/{short_id}`` or equals ``short_id``.

    Args:
        dl: The SqliteDataLayer instance.
        short_id: Short identifier to search for (e.g., ``"vendorco"``).

    Returns:
        Reconstituted actor object, or ``None`` if not found.
    """
    with Session(dl._engine) as session:
        stmt = select(VultronObjectRecord).where(
            VultronObjectRecord.type_.in_(list(_ACTOR_TYPES))  # type: ignore[attr-defined]
        )
        if dl._actor_id:
            stmt = stmt.where(VultronObjectRecord.actor_id == dl._actor_id)
        rows = session.exec(stmt).all()

    matches: list[PersistableModel] = []
    for row in rows:
        if matches_short_id(row.id_, short_id):
            obj = dl._from_row(row)
            if obj is not None:
                matches.append(obj)

    if len(matches) > 1:
        logger.warning(
            "Ambiguous actor surrogate key '%s' matched %d actors",
            short_id,
            len(matches),
        )
        return None
    return matches[0] if matches else None


def find_case_by_short_id(
    dl: "Any",  # SqliteDataLayer
    short_id: str,
) -> PersistableModel | None:
    """Find a case by its URL-safe surrogate key.

    Args:
        dl: The SqliteDataLayer instance.
        short_id: Short identifier to search for.

    Returns:
        Reconstituted case object, or ``None`` if not found.
    """
    with Session(dl._engine) as session:
        stmt = select(VultronObjectRecord).where(
            VultronObjectRecord.type_.in_(list(_CASE_TYPES))  # type: ignore[attr-defined]
        )
        if dl._actor_id:
            stmt = stmt.where(VultronObjectRecord.actor_id == dl._actor_id)
        rows = session.exec(stmt).all()

    matches: list[PersistableModel] = []
    for row in rows:
        if matches_short_id(row.id_, short_id):
            obj = dl._from_row(row)
            if obj is not None:
                matches.append(obj)

    if len(matches) > 1:
        logger.warning(
            "Ambiguous case surrogate key '%s' matched %d cases",
            short_id,
            len(matches),
        )
        return None
    return matches[0] if matches else None


def find_case_by_report_id(
    dl: "Any",  # SqliteDataLayer
    report_id: str,
) -> PersistableModel | None:
    """Find a ``VulnerabilityCase`` referencing the given report ID.

    Each entry in ``vulnerability_reports`` may be stored as either a
    plain string ID or a serialised inline object dict (with an ``id_``
    key).  Both forms are checked.

    Args:
        dl: The SqliteDataLayer instance.
        report_id: Full URI of the ``VulnerabilityReport`` to search for.

    Returns:
        Reconstituted ``VulnerabilityCase``, or ``None`` if not found.
    """
    report_link = dl.read(VultronReportCaseLink.build_id(report_id))
    if isinstance(report_link, VultronReportCaseLink):
        if report_link.case_id is not None:
            linked_case = dl.read(report_link.case_id)
            if is_case_model(linked_case):
                return linked_case

    with Session(dl._engine) as session:
        rows = session.exec(
            dl._scoped(
                select(VultronObjectRecord).where(
                    VultronObjectRecord.type_.in_(list(_CASE_TYPES))  # type: ignore[attr-defined]
                )
            )
        ).all()

    for row in rows:
        reports = row.data.get("vulnerability_reports", [])
        for entry in reports:
            if entry == report_id:
                return cast(PersistableModel | None, dl._from_row(row))
            if isinstance(entry, dict) and entry.get("id_") == report_id:
                return cast(PersistableModel | None, dl._from_row(row))
    return None
