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

from pydantic import ValidationError

from vultron.wire.as2.factories.errors import VultronActivityConstructionError
from vultron.wire.as2.vocab.activities.report import (
    _RmCloseReportActivity,
    _RmCreateReportActivity,
    _RmInvalidateReportActivity,
    _RmReadReportActivity,
    _RmSubmitReportActivity,
    _RmValidateReportActivity,
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
        return _RmCreateReportActivity(object_=report, **kwargs)
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
        return _RmSubmitReportActivity(object_=report, to=[to], **kwargs)
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
        return _RmReadReportActivity(object_=report, **kwargs)
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
    The ``offer`` argument may be an ``_RmSubmitReportActivity`` (the typed
    subclass returned by :func:`rm_submit_report_activity`) or a plain
    ``as_Offer`` recovered from the datalayer.  Plain offers are coerced
    to ``_RmSubmitReportActivity`` at runtime; offers whose ``object_`` is
    not a valid ``VulnerabilityReport`` will still fail validation.

    Args:
        offer: The ``_RmSubmitReportActivity`` offer being accepted.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``).

    Returns:
        An ``as_Accept`` whose ``object_`` is the given offer.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        if not isinstance(offer, _RmSubmitReportActivity):
            offer = _RmSubmitReportActivity.model_validate(
                offer.model_dump(by_alias=True)
            )
        return _RmValidateReportActivity(object_=offer, **kwargs)
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
    The ``offer`` argument may be an ``_RmSubmitReportActivity`` (the typed
    subclass returned by :func:`rm_submit_report_activity`) or a plain
    ``as_Offer`` recovered from the datalayer.  Plain offers are coerced
    to ``_RmSubmitReportActivity`` at runtime; offers whose ``object_`` is
    not a valid ``VulnerabilityReport`` will still fail validation.

    Args:
        offer: The ``_RmSubmitReportActivity`` offer being tentatively rejected.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``).

    Returns:
        An ``as_TentativeReject`` whose ``object_`` is the given offer.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        if not isinstance(offer, _RmSubmitReportActivity):
            offer = _RmSubmitReportActivity.model_validate(
                offer.model_dump(by_alias=True)
            )
        return _RmInvalidateReportActivity(object_=offer, **kwargs)
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
    The ``offer`` argument may be an ``_RmSubmitReportActivity`` (the typed
    subclass returned by :func:`rm_submit_report_activity`) or a plain
    ``as_Offer`` recovered from the datalayer.  Plain offers are coerced
    to ``_RmSubmitReportActivity`` at runtime; offers whose ``object_`` is
    not a valid ``VulnerabilityReport`` will still fail validation.

    Args:
        offer: The ``_RmSubmitReportActivity`` offer being closed.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``).

    Returns:
        An ``as_Reject`` whose ``object_`` is the given offer.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        if not isinstance(offer, _RmSubmitReportActivity):
            offer = _RmSubmitReportActivity.model_validate(
                offer.model_dump(by_alias=True)
            )
        return _RmCloseReportActivity(object_=offer, **kwargs)
    except ValidationError as exc:
        raise VultronActivityConstructionError(
            "rm_close_report_activity: invalid arguments"
        ) from exc


def parse_submit_report_offer(
    offer_data: dict | as_Offer,
) -> tuple[VulnerabilityReport, as_Offer]:
    """Parse a submit-report offer from wire data into its component parts.

    Accepts either a raw dict (e.g. from a trigger endpoint JSON response)
    or an ``as_Offer`` instance and coerces it to ``_RmSubmitReportActivity``
    so the embedded ``VulnerabilityReport`` — including its stable ID — is
    preserved.  This is the correct way for the demo and adapter layers to
    extract the report from a trigger response without importing internal
    activity subclasses directly.

    Args:
        offer_data: A dict representation of the submit-report offer, or an
            existing ``as_Offer`` instance.

    Returns:
        A ``(report, offer)`` tuple where *report* is the
        ``VulnerabilityReport`` embedded in the offer and *offer* is the
        coerced ``_RmSubmitReportActivity`` suitable for inbox delivery.

    Raises:
        VultronActivityConstructionError: If the data cannot be validated as
            a submit-report offer containing a ``VulnerabilityReport``.
    """
    try:
        if isinstance(offer_data, dict):
            coerced = _RmSubmitReportActivity.model_validate(offer_data)
        elif isinstance(offer_data, _RmSubmitReportActivity):
            coerced = offer_data
        else:
            coerced = _RmSubmitReportActivity.model_validate(
                offer_data.model_dump(by_alias=True)
            )
        return coerced.object_, coerced
    except (ValidationError, AttributeError) as exc:
        raise VultronActivityConstructionError(
            "parse_submit_report_offer: invalid offer data"
        ) from exc
