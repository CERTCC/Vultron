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
"""Factories for activities that create, update, announce or add to a case.

Spec: ``specs/activity-factories.yaml`` AF-01-001 through AF-04-003.
"""

import logging

from pydantic import ValidationError

from vultron.wire.as2.factories._context import (
    case_target_ref,
    with_case_context,
)
from vultron.wire.as2.factories.errors import VultronActivityConstructionError
from vultron.wire.as2.vocab.activities.case.content import (
    _AddNoteToCaseActivity,
    _AddReportToCaseActivity,
    _AddStatusToCaseActivity,
    _AnnounceVulnerabilityCaseActivity,
    _CreateCaseActivity,
    _UpdateCaseActivity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Add,
    as_Announce,
    as_Create,
    as_Update,
)
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.case_status import as_CaseStatus
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
    as_VulnerabilityCaseRef,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

logger = logging.getLogger(__name__)


def add_report_to_case_activity(
    report: as_VulnerabilityReport,
    target: as_VulnerabilityCaseRef | None = None,
    **kwargs,
) -> as_Add:
    """Build an Add(VulnerabilityReport)[target=VulnerabilityCase].

    Args:
        report: The ``as_VulnerabilityReport`` to add to the case.
        target: The ``as_VulnerabilityCase`` (or its URI) to which the
            report is being added.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``).

    Returns:
        An ``as_Add`` whose ``object_`` is the report and
        ``target`` is the case reference.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _AddReportToCaseActivity(
            object_=report, target=case_target_ref(target), **kwargs
        )
    except ValidationError as exc:
        logger.warning(
            "add_report_to_case_activity: invalid arguments: %s", exc
        )
        raise VultronActivityConstructionError(
            "add_report_to_case_activity: invalid arguments"
        ) from exc


def add_status_to_case_activity(
    status: as_CaseStatus,
    target: as_VulnerabilityCaseRef | None = None,
    **kwargs,
) -> as_Add:
    """Build an Add(CaseStatus)[target=VulnerabilityCase].

    Args:
        status: The ``as_CaseStatus`` to add.
        target: The ``as_VulnerabilityCase`` (or its URI) to which the
            status is being added.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``).

    Returns:
        An ``as_Add`` whose ``object_`` is the status.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _AddStatusToCaseActivity(
            object_=status, target=case_target_ref(target), **kwargs
        )
    except ValidationError as exc:
        logger.warning(
            "add_status_to_case_activity: invalid arguments: %s", exc
        )
        raise VultronActivityConstructionError(
            "add_status_to_case_activity: invalid arguments"
        ) from exc


def create_case_activity(
    case: as_VulnerabilityCase,
    **kwargs,
) -> as_Create:
    """Build a Create(VulnerabilityCase).

    Args:
        case: The ``as_VulnerabilityCase`` being created.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``).

    Returns:
        An ``as_Create`` whose ``object_`` is the case.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _CreateCaseActivity(object_=case, **kwargs)
    except ValidationError as exc:
        logger.warning("create_case_activity: invalid arguments: %s", exc)
        raise VultronActivityConstructionError(
            "create_case_activity: invalid arguments"
        ) from exc


def add_note_to_case_activity(
    note: as_Note,
    target: as_VulnerabilityCaseRef | None = None,
    **kwargs,
) -> as_Add:
    """Build an Add(Note)[target=VulnerabilityCase].

    The note travels inline as the ``Add``'s ``object``: the ``object``
    field takes an ``as_Note`` and refuses a URI or a ``Link``, so this is
    the single message that both brings the note to its receiver and
    attaches it to the case (VAM-07-002, VAM-01-015).  ``context`` defaults
    to the case, so a CASE_MANAGER entry's sealed snapshot carries it
    (CLP-07-007).

    Args:
        note: The ``as_Note`` to add to the case, carried inline.
        target: The ``as_VulnerabilityCase`` (or its URI) to which the
            note is being added.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``).

    Returns:
        An ``as_Add`` whose ``object_`` is the note.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _AddNoteToCaseActivity(
            object_=note,
            target=case_target_ref(target),
            **with_case_context(kwargs, target),
        )
    except ValidationError as exc:
        logger.warning("add_note_to_case_activity: invalid arguments: %s", exc)
        raise VultronActivityConstructionError(
            "add_note_to_case_activity: invalid arguments"
        ) from exc


def update_case_activity(
    case: as_VulnerabilityCase,
    **kwargs,
) -> as_Update:
    """Build an Update(VulnerabilityCase).

    The CASE_MANAGER's ``update_case_owner`` ledger entry naming a new Case
    Owner (CM-21-024, CLP-07-013); no received use case handles it
    (ADR-0140).  ``context`` defaults to the case's URI (CLP-07-007).

    Args:
        case: The updated ``as_VulnerabilityCase``.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``, ``id_``).

    Returns:
        An ``as_Update`` whose ``object_`` is the case.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _UpdateCaseActivity(
            object_=case, **with_case_context(kwargs, case)
        )
    except ValidationError as exc:
        logger.warning("update_case_activity: invalid arguments: %s", exc)
        raise VultronActivityConstructionError(
            "update_case_activity: invalid arguments"
        ) from exc


def announce_vulnerability_case_activity(
    case: as_VulnerabilityCase,
    **kwargs,
) -> as_Announce:
    """Build an Announce(VulnerabilityCase) — sent by the case owner.

    Sent after an ``Accept(Invite)`` is received and the invitee's
    embargo consent has been verified.  The full case object is sent
    inline so the recipient can seed their local DataLayer.

    Args:
        case: The complete ``as_VulnerabilityCase`` being announced.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``).

    Returns:
        An ``as_Announce`` whose ``object_`` is the case.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _AnnounceVulnerabilityCaseActivity(object_=case, **kwargs)
    except ValidationError as exc:
        logger.warning(
            "announce_vulnerability_case_activity: invalid arguments: %s", exc
        )
        raise VultronActivityConstructionError(
            "announce_vulnerability_case_activity: invalid arguments"
        ) from exc
