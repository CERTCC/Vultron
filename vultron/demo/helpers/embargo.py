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

"""Embargo object factory helpers shared across demo scenarios."""

from datetime import datetime, timedelta
from typing import Optional

from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)


def make_embargo_event(
    case: as_VulnerabilityCase,
    days: int = 90,
    seq: Optional[int] = None,
) -> as_EmbargoEvent:
    """Create a deterministic :class:`as_EmbargoEvent` for *case*.

    The event's ``id_`` encodes the duration and end-date so it is unique
    per case/duration pair.  Pass *seq* to distinguish multiple events with
    the same duration within a single case (e.g., in the reject-then-repropose
    demo where two embargo events differ only by sequence number).

    Args:
        case: The :class:`as_VulnerabilityCase` this embargo event belongs to.
        days: Embargo duration in days (default 90).
        seq: Optional integer sequence suffix appended to the event ID to
            ensure uniqueness within a multi-proposal workflow.  When
            ``None`` the suffix is omitted.

    Returns:
        A new :class:`as_EmbargoEvent` with start/end times set.
    """
    now = datetime.now().astimezone()
    now = now.replace(second=0, microsecond=0)
    end_at = (now + timedelta(days=days)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    end_date_str = end_at.strftime("%Y-%m-%d")
    suffix = f"-{seq}" if seq is not None else ""
    return as_EmbargoEvent(
        id_=f"{case.id_}/embargo_events/{days}d-{end_date_str}{suffix}",
        name=f"Embargo for {case.name}",
        context=case.id_,
        start_time=now,
        end_time=end_at,
        content=f"Proposed {days}-day embargo for {case.name}.",
    )
