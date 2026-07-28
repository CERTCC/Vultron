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

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vultron.core.models.case import VulnerabilityCase


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


def has_case_statuses(case: VulnerabilityCase) -> bool:
    """Return True when *case* has at least one CaseStatus entry.

    Use this as the single shared predicate wherever code must distinguish
    "no status history yet" from "at least one status recorded" — in both
    BT condition nodes and plain use-case guards (LST-05 / AC-5).
    """
    return bool(case.case_statuses)


def _report_phase_status_id(
    actor_id: str, report_id: str, rm_state: str
) -> str:
    """Return a deterministic URN for a report-phase participant status record.

    Uses UUID v5 (name-based) so the same (actor, report, rm_state) triple
    always produces the same ID, enabling idempotent DataLayer creation.
    """
    name = f"{actor_id}|{report_id}|{rm_state}"
    return f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, name)}"
