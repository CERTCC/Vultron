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

"""Creation-time embargo outcome checks for the negotiated path (EP-04-003).

The read and verification steps the ``report-with-embargo`` exchange demo
runs against the CaseActor's store once the case exists: which
``EmbargoEvent`` became active, which was left pending as a revision, that
every event is about the case (EP-04-009), and that the Receiver's replica
agrees.  They live here rather than in the demo module so that the module
stays a script of runs (CS-18-001) and a second negotiated-path scenario can
reuse the checks instead of copying them (DEMOMA-17-001).

Each check is a ``demo_check`` block: a failed assertion is recorded and the
run continues, so one wrong outcome does not hide the others.
"""

import logging
from datetime import datetime, timedelta

from vultron.core.states.em import EM
from vultron.demo.helpers.polling import _poll_until
from vultron.demo.helpers.workflow import find_case_for_offer
from vultron.demo.utils import DataLayerClient, demo_check
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

logger = logging.getLogger(__name__)

#: How far an actor default's realised window may drift from the published
#: duration: the CaseActor stamps ``start_time`` and ``end_time`` on two
#: consecutive clock reads at second precision.
WINDOW_TOLERANCE = timedelta(minutes=1)
#: The protocol default may be configured no longer than this (EP-04-005).
PROTOCOL_DEFAULT_CEILING = timedelta(days=5)
#: How long to wait for an effect another actor's answer causes: the relayed
#: revision's Accept, or the replica catching up with it.
ANSWER_TIMEOUT_SECONDS = 20.0


# ---------------------------------------------------------------------------


def read_embargo(
    client: DataLayerClient, case_actor_id: str, embargo_id: str
) -> as_EmbargoEvent:
    """Read an ``EmbargoEvent`` from the CaseActor's own store."""
    data = client.get(client.dl_path(embargo_id, actor_id=case_actor_id))
    return as_EmbargoEvent.model_validate(data)


def embargo_window(embargo: as_EmbargoEvent) -> timedelta:
    """The embargo's realised duration, start to end."""
    if embargo.start_time is None:
        raise AssertionError(
            f"Embargo {embargo.id_} carries no start_time, so its window"
            " cannot be measured"
        )
    return embargo.end_time - embargo.start_time


def assert_about_the_case(
    embargo: as_EmbargoEvent, case: as_VulnerabilityCase
) -> None:
    """EP-04-009: on the case-actor's side every embargo names the case."""
    if embargo.context != case.id_:
        raise AssertionError(
            f"Embargo {embargo.id_} is about {embargo.context!r}, expected"
            f" the case {case.id_!r} (EP-04-009)"
        )


def assert_window_is(
    embargo: as_EmbargoEvent, expected: timedelta, label: str
) -> None:
    """The embargo's window matches *expected* within the clock tolerance."""
    window = embargo_window(embargo)
    if abs(window - expected) > WINDOW_TOLERANCE:
        raise AssertionError(
            f"{label} embargo {embargo.id_} runs {window}, expected"
            f" {expected} (±{WINDOW_TOLERANCE})"
        )


# ---------------------------------------------------------------------------
# Verification of the creation-time outcome
# ---------------------------------------------------------------------------


def verify_reporter_terms_active(
    client: DataLayerClient,
    case_actor_id: str,
    case: as_VulnerabilityCase,
    proposal_id: str,
    proposed_end: datetime,
) -> as_EmbargoEvent:
    """The Reporter's own event is the active embargo, identity kept."""
    active_id = case.active_embargo_id
    with demo_check("Active embargo is the Reporter's proposed event"):
        if active_id != proposal_id:
            raise AssertionError(
                f"Expected the Reporter's proposal {proposal_id!r} to be the"
                f" active embargo, found {active_id!r}"
            )
    active = read_embargo(client, case_actor_id, proposal_id)
    with demo_check("Active embargo ends when the Reporter proposed"):
        if active.end_time != proposed_end:
            raise AssertionError(
                f"Active embargo ends {active.end_time.isoformat()}, the"
                f" Reporter proposed {proposed_end.isoformat()}"
            )
    with demo_check("Active embargo is now about the case (EP-04-009)"):
        assert_about_the_case(active, case)
    logger.info(
        "Reporter's terms are the active embargo: %s ends %s",
        active.id_,
        active.end_time.isoformat(),
    )
    return active


def verify_pending_revision(
    client: DataLayerClient,
    case_actor_id: str,
    case: as_VulnerabilityCase,
    active: as_EmbargoEvent,
) -> as_EmbargoEvent:
    """Exactly one longer proposal is pending and the case sits at REVISE."""
    with demo_check("Case is at EM.REVISE — the longer terms are pending"):
        if case.current_status.em_state != EM.REVISE:
            raise AssertionError(
                f"Expected EM.REVISE with a revision pending, found"
                f" {case.current_status.em_state}"
            )
    with demo_check("Exactly one revision is registered on the case"):
        if len(case.proposed_embargo_ids) != 1:
            raise AssertionError(
                "Expected exactly one pending revision, found"
                f" {case.proposed_embargo_ids}"
            )
    revision = read_embargo(
        client, case_actor_id, case.proposed_embargo_ids[0]
    )
    with demo_check("Pending revision is about the case and ends later"):
        assert_about_the_case(revision, case)
        if revision.end_time <= active.end_time:
            raise AssertionError(
                f"Revision {revision.id_} ends {revision.end_time.isoformat()},"
                " not after the active embargo's"
                f" {active.end_time.isoformat()} — shortest-wins would have"
                " activated it instead (EP-04-003)"
            )
    logger.info(
        "Shortest-wins: active %s ends %s; revision %s ends %s",
        active.id_,
        active.end_time.isoformat(),
        revision.id_,
        revision.end_time.isoformat(),
    )
    return revision


def verify_uncontested(
    case: as_VulnerabilityCase, active: as_EmbargoEvent
) -> None:
    """No default competed: ACTIVE, nothing pending, and not the fallback."""
    with demo_check("Case is at EM.ACTIVE with nothing pending"):
        if case.current_status.em_state != EM.ACTIVE:
            raise AssertionError(
                f"Expected EM.ACTIVE, found {case.current_status.em_state}"
            )
        if case.proposed_embargo_ids:
            raise AssertionError(
                "Expected no pending revision with no actor default, found"
                f" {case.proposed_embargo_ids}"
            )
    with demo_check(
        "Active window exceeds the protocol default ceiling — the proposal"
        " was honored (EP-04-006, EP-04-007)"
    ):
        if embargo_window(active) <= PROTOCOL_DEFAULT_CEILING:
            raise AssertionError(
                f"Active embargo runs {embargo_window(active)}, within the protocol"
                f" default ceiling {PROTOCOL_DEFAULT_CEILING}: the fallback"
                " may have been applied instead of the Reporter's terms"
            )
    logger.info(
        "No actor default competed: %s runs %s, nothing pending",
        active.id_,
        embargo_window(active),
    )


def verify_receiver_replica_agrees(
    client: DataLayerClient,
    vendor: as_Actor,
    offer_id: str,
    canonical: as_VulnerabilityCase,
) -> None:
    """The Receiver's replica shows the same EM outcome as the canonical case.

    The replica's arrival is a causal effect of the CaseActor's
    ``Create(VulnerabilityCase)`` fan-out (ADR-0058), and its EM state of the
    ledger entries that follow it — an accepted revision reaches the replica
    after the case does.  Both are observed here rather than gated: nothing
    downstream depends on them, so a replica that has not caught up within
    the wait is a recorded check, not a skipped run (EDF-06-005).
    """
    with demo_check(
        "Receiver's replica carries the same EM state (observed, not gated)"
    ):
        expected = canonical.current_status.em_state
        seen: dict[str, EM] = {}

        def _agrees() -> bool:
            replica = find_case_for_offer(client, offer_id)
            if replica is None:
                return False
            seen["em"] = replica.current_status.em_state
            return seen["em"] == expected

        try:
            _poll_until(_agrees, ANSWER_TIMEOUT_SECONDS)
        except AssertionError as exc:
            raise AssertionError(
                f"Receiver {vendor.id_} sees {seen.get('em')}, the CaseActor"
                f" holds {expected}"
            ) from exc
