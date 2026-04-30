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
Factory functions for outbound Vultron report-management activities.

These are the sole public construction API for activities involving
``VulnerabilityReport`` objects.  Internal activity subclasses are
imported here and MUST NOT be imported by callers.

Spec: ``specs/activity-factories.yaml`` AF-01-001, AF-02-001, AF-03-001
through AF-03-006.
"""

from typing import cast

from pydantic import ValidationError

from vultron.wire.as2.factories.errors import VultronActivityConstructionError
from vultron.wire.as2.vocab.activities.report import (
    RmCloseReportActivity,
    RmCreateReportActivity,
    RmInvalidateReportActivity,
    RmReadReportActivity,
    RmSubmitReportActivity,
    RmValidateReportActivity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Create,
    as_Offer,
    as_Read,
    as_Reject,
    as_TentativeReject,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    VulnerabilityReport,
)


def rm_create_report_activity(
    report: VulnerabilityReport,
    **kwargs,
) -> as_Create:
    """Build a Create(VulnerabilityReport) — the reporter creates a report.

    Args:
        report: The ``VulnerabilityReport`` to create.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``).

    Returns:
        An ``as_Create`` whose ``object_`` is the given report.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return RmCreateReportActivity(object_=report, **kwargs)
    except ValidationError as exc:
        raise VultronActivityConstructionError(
            "rm_create_report_activity: invalid arguments"
        ) from exc


def rm_submit_report_activity(
    report: VulnerabilityReport,
    to: as_Actor | str,
    **kwargs,
) -> as_Offer:
    """Build an Offer(VulnerabilityReport) — the RS message when no case exists.

    Args:
        report: The ``VulnerabilityReport`` to submit.
        to: The recipient actor object or actor ID URI string.  The factory
            always normalizes this to a single-element ``to`` list.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``context``).

    Returns:
        An ``as_Offer`` whose ``object_`` is the given report and whose
        ``to`` list contains the given recipient.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return RmSubmitReportActivity(object_=report, to=[to], **kwargs)
    except ValidationError as exc:
        raise VultronActivityConstructionError(
            "rm_submit_report_activity: invalid arguments"
        ) from exc


def rm_read_report_activity(
    report: VulnerabilityReport,
    **kwargs,
) -> as_Read:
    """Build a Read(VulnerabilityReport) — the RK message when no case exists.

    Args:
        report: The ``VulnerabilityReport`` that was read.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``).

    Returns:
        An ``as_Read`` whose ``object_`` is the given report.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return RmReadReportActivity(object_=report, **kwargs)
    except ValidationError as exc:
        raise VultronActivityConstructionError(
            "rm_read_report_activity: invalid arguments"
        ) from exc


def rm_validate_report_activity(
    offer: as_Offer,
    **kwargs,
) -> as_Accept:
    """Build an Accept(Offer) — the RV message when no case exists.

    Signals that the submission offer was reviewed and the report is valid.
    The ``offer`` MUST be the inline typed ``as_Offer`` returned by
    :func:`rm_submit_report_activity`; a plain ``as_Offer`` will fail
    Pydantic validation and raise :exc:`VultronActivityConstructionError`.

    Args:
        offer: The ``RmSubmitReportActivity`` offer being accepted.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``).

    Returns:
        An ``as_Accept`` whose ``object_`` is the given offer.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return RmValidateReportActivity(
            object_=cast(RmSubmitReportActivity, offer), **kwargs
        )
    except ValidationError as exc:
        raise VultronActivityConstructionError(
            "rm_validate_report_activity: invalid arguments"
        ) from exc


def rm_invalidate_report_activity(
    offer: as_Offer,
    **kwargs,
) -> as_TentativeReject:
    """Build a TentativeReject(Offer) — the RI message when no case exists.

    Signals that the submission offer was reviewed and the report is invalid.
    The ``offer`` MUST be the inline typed ``as_Offer`` returned by
    :func:`rm_submit_report_activity`; a plain ``as_Offer`` will fail
    Pydantic validation and raise :exc:`VultronActivityConstructionError`.

    Args:
        offer: The ``RmSubmitReportActivity`` offer being tentatively rejected.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``).

    Returns:
        An ``as_TentativeReject`` whose ``object_`` is the given offer.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return RmInvalidateReportActivity(
            object_=cast(RmSubmitReportActivity, offer), **kwargs
        )
    except ValidationError as exc:
        raise VultronActivityConstructionError(
            "rm_invalidate_report_activity: invalid arguments"
        ) from exc


def rm_close_report_activity(
    offer: as_Offer,
    **kwargs,
) -> as_Reject:
    """Build a Reject(Offer) — the RC message when no case exists.

    Closes the report permanently.  Can only be emitted when the report is
    in the ``RM.INVALID`` state; anything past that will have an associated
    ``VulnerabilityCase`` and closure falls to ``rm_close_case_activity``.
    The ``offer`` MUST be the inline typed ``as_Offer`` returned by
    :func:`rm_submit_report_activity`; a plain ``as_Offer`` will fail
    Pydantic validation and raise :exc:`VultronActivityConstructionError`.

    Args:
        offer: The ``RmSubmitReportActivity`` offer being closed.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``).

    Returns:
        An ``as_Reject`` whose ``object_`` is the given offer.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return RmCloseReportActivity(
            object_=cast(RmSubmitReportActivity, offer), **kwargs
        )
    except ValidationError as exc:
        raise VultronActivityConstructionError(
            "rm_close_report_activity: invalid arguments"
        ) from exc
