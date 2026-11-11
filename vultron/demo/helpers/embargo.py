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

import logging
from datetime import datetime, timedelta

import isodate  # type: ignore[import-untyped]

from vultron.adapters.utils import parse_id
from vultron.core.models._helpers import parse_published
from vultron.core.models.embargo_policy import EmbargoPolicy
from vultron.demo.utils import DataLayerClient
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

logger = logging.getLogger(__name__)


def publish_embargo_policy(
    client: DataLayerClient,
    actor: as_Actor,
    preferred_duration: timedelta,
) -> EmbargoPolicy:
    """Publish *actor*'s embargo policy — its actor default — on *client*.

    ``PUT /actors/{slug}/embargo-policy`` (EP-02) writes the policy into the
    actor's own profile record, in its own store (EP-01-001, EP-01-004).  The
    actor sends that profile inline on every ``Create(CaseProposal)`` it
    makes, which is where the CASE_MANAGER reads the CASE_OWNER's actor
    default from (EP-04-003, CP-01-010).  The actor must be hosted by the
    container *client* addresses.

    Args:
        client: Client connected to the container hosting *actor*.
        actor: The hosted actor publishing the policy.
        preferred_duration: The default embargo length the actor proposes to
            every Reporter (EP-01-002).

    Returns:
        The published policy, as the endpoint returned it.
    """
    slug = parse_id(actor.id_)["object_id"]
    data = client.put(
        f"/actors/{slug}/embargo-policy",
        json={
            "preferred_duration": isodate.duration_isoformat(
                preferred_duration
            )
        },
    )
    policy = EmbargoPolicy.model_validate(data)
    logger.info(
        "Actor %s published embargo policy: preferred %s",
        actor.id_,
        policy.preferred_duration,
    )
    return policy


def case_minted_at(
    client: DataLayerClient, case: as_VulnerabilityCase, holder_id: str
) -> datetime:
    """The instant *case* was minted, as *holder_id*'s stored copy records it.

    The case a demo step holds is often a stub it built itself (see
    ``create_case_via_trigger``), whose ``published`` is the demo's own clock
    read.  This reads the ``published`` the holder's store wrote instead, the
    instant of the act that minted the case, so a demo step that dates
    something it builds for the case reads no clock of its own (ADR-0176).

    Args:
        client: Client connected to the container hosting *holder_id*.
        case: The case, by its id.
        holder_id: The actor whose stored copy of *case* is read, typically
            its CASE_MANAGER.

    Raises:
        ValueError: The stored copy carries no parseable ``published``.
    """
    stored = client.get(client.dl_path(case.id_, actor_id=holder_id))
    # Parsed from the raw stored key, not via ``as_VulnerabilityCase``: the
    # wire model would refuse an absent ``published`` with a schema error
    # rather than name the gap this refuses.
    raw = stored.get("published")
    minted = parse_published(raw)
    if minted is None:
        raise ValueError(
            f"'{holder_id}''s copy of case '{case.id_}' carries no published"
            f" time to date its embargo proposal from (got {raw!r})"
        )
    return minted


def make_embargo_event(
    case: as_VulnerabilityCase,
    *,
    at: datetime,
    days: int = 90,
    seq: int | None = None,
) -> as_EmbargoEvent:
    """Create a deterministic :class:`as_EmbargoEvent` for *case*.

    The event's ``id_`` encodes the duration and end-date so it is unique
    per case/duration pair.  Pass *seq* to distinguish multiple events with
    the same duration within a single case (e.g., in the reject-then-repropose
    demo where two embargo events differ only by sequence number).

    The helper reads no clock: *at* is the caller's instant, so the same
    *at* builds the same event (ADR-0176).

    Args:
        case: The :class:`as_VulnerabilityCase` this embargo event belongs to.
        at: The instant the embargo is proposed at, timezone-aware: its
            ``start_time`` to the minute, and the base its end is counted
            from.
        days: Embargo duration in days (default 90).
        seq: Optional integer sequence suffix appended to the event ID to
            ensure uniqueness within a multi-proposal workflow.  When
            ``None`` the suffix is omitted.

    Returns:
        A new :class:`as_EmbargoEvent` with start/end times set.
    """
    now = at.replace(second=0, microsecond=0)
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
        # Stamped from *at* too, so building the event reads no clock
        # through the stamps' defaults (ADR-0176).
        published=now,
        updated=now,
        content=f"Proposed {days}-day embargo for {case.name}.",
    )
