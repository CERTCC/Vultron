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

"""Shared helper utilities for core domain model types."""

import uuid
from datetime import datetime, timezone
from typing import Any


def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _new_urn() -> str:
    return f"urn:uuid:{uuid.uuid4()}"


def _as_id(obj: Any) -> str | None:
    """Return the ActivityStreams id of *obj* as a plain string.

    - If *obj* is ``None``, returns ``None``.
    - If *obj* has an ``id_`` attribute, returns ``obj.id_``.
    - Otherwise returns ``str(obj)``.

    This handles the mixed ``str | <wire-type>`` collections that arise when
    the DataLayer stores plain string IDs alongside rehydrated objects.
    """
    if obj is None:
        return None
    id_ = getattr(obj, "id_", None)
    if isinstance(id_, str):
        return id_
    return str(obj)


def _report_phase_status_id(
    actor_id: str, report_id: str, rm_state: str
) -> str:
    """Return a deterministic URN for a report-phase participant status record.

    Uses UUID v5 (name-based) so the same (actor, report, rm_state) triple
    always produces the same ID, enabling idempotent DataLayer creation.
    """
    name = f"{actor_id}|{report_id}|{rm_state}"
    return f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, name)}"


def report_phase_context(dl: Any, report_id: str) -> str:
    """Return the ``context`` URI for a report-phase ``ParticipantStatus``.

    CLP-07-007 requires the case URI once a case exists for the report; the
    report URI is the correct context only *before* the report→case promotion
    has happened in this actor's own store.

    This is the single canonical copy of that selection (ARCH-15-004).  It
    exists for the RM states that a participant can legitimately reach with no
    case at all — ``RM.INVALID`` and ``RM.CLOSED``, which a receiver may declare
    on a bare report it never promoted.  States that are *case-scoped* must not
    use it: they require the case to be present in this actor's store and should
    resolve it once via
    :class:`~vultron.core.behaviors.case.nodes.case_lookup.RequireCaseForReport`,
    which publishes ``/case_id`` and fails when the case is absent.

    Args:
        dl: Any object exposing ``find_case_by_report_id`` (the
            ``CasePersistence`` port).  Duck-typed so this helper stays at the
            ``models/`` layer.
        report_id: URI of the ``VulnerabilityReport``.

    Returns:
        The case URI when a case for *report_id* is in this store, else
        *report_id*.
    """
    from vultron.core.models.case import VulnerabilityCase

    case = dl.find_case_by_report_id(report_id)
    if isinstance(case, VulnerabilityCase):
        return case.id_
    return report_id
