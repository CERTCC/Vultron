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
"""Factories for the RM case messages: engage, defer, close, and declining a close.

Spec: ``specs/activity-factories.yaml`` AF-01-001 through AF-04-003.
"""

from datetime import datetime
from typing import cast

from vultron.wire.as2.factories._construct import build_activity
from vultron.wire.as2.factories.case._named import _named_case
from vultron.wire.as2.vocab.activities.case.rm import (
    _RmCloseCaseActivity,
    _RmDeferCaseActivity,
    _RmEngageCaseActivity,
    _RmRejectCloseCaseActivity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Ignore,
    as_Join,
    as_Leave,
    as_Reject,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)


def rm_engage_case_activity(
    case: as_VulnerabilityCase | str,
    *,
    at: datetime,
    **kwargs,
) -> as_Join:
    """Build a Join(VulnerabilityCase) — the RA message.

    Signals that the actor is now actively working on the case
    (``RM.ACCEPTED`` state).

    Args:
        case: The case being engaged, as the sender holds it or by its
            URI.  Only its id travels, as a typed reference (ADR-0165).
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``).

    Returns:
        An ``as_Join`` whose ``object_`` is the case's typed reference.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    return build_activity(
        "rm_engage_case_activity",
        _RmEngageCaseActivity,
        at,
        lambda: {"object_": _named_case(case), **kwargs},
    )


def rm_defer_case_activity(
    case: as_VulnerabilityCase | str,
    *,
    at: datetime,
    **kwargs,
) -> as_Ignore:
    """Build an Ignore(VulnerabilityCase) — the RD message.

    Signals that the actor is deferring work on the case
    (``RM.DEFERRED`` state).

    Args:
        case: The case being deferred, as the sender holds it or by its
            URI.  Only its id travels, as a typed reference (ADR-0165).
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``).

    Returns:
        An ``as_Ignore`` whose ``object_`` is the case's typed reference.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    return build_activity(
        "rm_defer_case_activity",
        _RmDeferCaseActivity,
        at,
        lambda: {"object_": _named_case(case), **kwargs},
    )


def rm_close_case_activity(
    case: as_VulnerabilityCase | str,
    *,
    at: datetime,
    **kwargs,
) -> as_Leave:
    """Build a Leave(VulnerabilityCase) — the RC message.

    Signals permanent closure / departure from the case.

    Args:
        case: The case being closed, as the sender holds it or by its
            URI.  Only its id travels, as a typed reference (ADR-0165).
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``).

    Returns:
        An ``as_Leave`` whose ``object_`` is the case's typed reference.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    return build_activity(
        "rm_close_case_activity",
        _RmCloseCaseActivity,
        at,
        lambda: {"object_": _named_case(case), **kwargs},
    )


def reject_close_case_activity(
    leave: as_Leave,
    *,
    at: datetime,
    **kwargs,
) -> as_Reject:
    """Build a Reject(_RmCloseCaseActivity) — declines an owner close (CM-23-011).

    Per ActivityStreams convention the Case Actor rejects the
    ``Leave(VulnerabilityCase)`` activity itself.  The ``leave`` MUST be the
    value returned by :func:`rm_close_case_activity`; a plain ``as_Leave``
    will fail validation.

    Args:
        leave: The ``_RmCloseCaseActivity`` (the Leave) being declined.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``, ``in_reply_to``).

    Returns:
        An ``as_Reject`` whose ``object_`` is the leave.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    return build_activity(
        "reject_close_case_activity",
        _RmRejectCloseCaseActivity,
        at,
        lambda: {"object_": cast(_RmCloseCaseActivity, leave), **kwargs},
    )
