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
Demonstrates the **negotiated** embargo path: the Reporter proposes embargo
terms *with* the Report submission (EP-04-004, ADR-0096).

Every other demo reaches ``EM.ACTIVE`` by the **default path**: the Reporter
submits without stating terms, which is tacit acceptance of the Receiver's
published default (EP-04-001), so no embargo negotiation is visible at all.
This demo is the one that exercises the other path — the Reporter carries a
proposed ``EmbargoEvent`` on the ``Offer(VulnerabilityReport)`` — and readers
should not mistake it for the default one.  There is still no pre-case
negotiation exchange to watch: ADR-0096 declined a pre-case protocol phase, so
the Reporter states terms once, on the Offer, and the CASE_MANAGER settles the
comparison when it creates the case (EP-04-003, shortest-wins).  What is
visible is the *result* — which terms became active and which were left
pending as ``EM.REVISE``.

Three runs:

1. **Reporter proposes shorter** than the Receiver's actor default (10 vs 30
   days): the Reporter's own terms become the active embargo, identity kept,
   and the Receiver's longer default is registered as a pending revision, so
   the case is created at ``EM.REVISE``.
2. **Reporter proposes longer** (60 vs 30 days): the Receiver's default is the
   active embargo and the Reporter's terms are the pending revision — the
   same ``EmbargoEvent`` the Reporter sent, now about the case rather than
   the report (EP-04-009).
3. **Receiver has no actor default**: the Reporter's terms are the only
   candidate and win outright at their stated length.  The 10-day proposal
   is longer than the protocol default's 5-day ceiling (EP-04-005), so an
   active 10-day embargo shows the proposal was honored (EP-04-007) and the
   protocol default did not compete (EP-04-006).

Whose default is "the Receiver's".  Under ADR-0041 the Receiver does not create
the case: its node's CaseActor does, and the case is attributed to that
CaseActor, so the actor default the comparison reads is the ``EmbargoPolicy``
published by the CaseActor the Receiver's node hosts (``owner_embargo_policies``
on ``case.attributed_to``, EP-04-010).  The demo therefore publishes the
Receiver's policy on that CaseActor, which in single-container mode lives on
the same node as the Receiver.

Puppeteering.  The Reporter is driven through its ``submit-report`` trigger
(``proposed_embargo_end_time``), the Receiver through the embargo-policy
endpoint; no protocol activity is forged.  The Offer is then delivered to the
Receiver's inbox in the way every exchange demo delivers (``exchange/README``).

This corresponds to the workflow documented in
``docs/howto/activitypub/activities/report_vulnerability.md`` § "Submit a
report" and the semantics in ``notes/embargo-default-semantics.md``.
"""

import logging
from datetime import datetime, timedelta
from typing import Callable, Optional, Sequence, Tuple

from vultron.core.models._helpers import from_now_utc
from vultron.core.states.em import EM
from vultron.demo.helpers.embargo import publish_embargo_policy
from vultron.demo.helpers.runner import run_exchange_demos
from vultron.demo.helpers.workflow import (
    reporter_submits_report,
    wait_for_case_by_report,
    wait_for_case_for_offer,
)
from vultron.demo.utils import (  # noqa: F401 — BASE_URL needed for test monkeypatching
    BASE_URL,
    DataLayerClient,
    demo_check,
    demo_gate,
    demo_step,
    seed_case_actor_for_report,
    setup_demo_logging,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

logger = logging.getLogger(__name__)

#: The Receiver's published default in the two contested runs.
RECEIVER_DEFAULT_DAYS = 30
#: A Reporter proposal shorter than the Receiver's default — and longer than
#: the protocol default's 5-day ceiling (EP-04-005), so run 3 can tell the
#: proposal apart from the fallback.
REPORTER_SHORTER_DAYS = 10
#: A Reporter proposal longer than the Receiver's default.
REPORTER_LONGER_DAYS = 60

#: How far the actor default's realised window may drift from the published
#: duration: the CaseActor stamps ``start_time`` and ``end_time`` on two
#: consecutive clock reads at second precision.
_DEFAULT_WINDOW_TOLERANCE = timedelta(minutes=1)
#: The protocol default may be configured no longer than this (EP-04-005).
_PROTOCOL_DEFAULT_CEILING = timedelta(days=5)


# ---------------------------------------------------------------------------
# Reads against the CaseActor's store
# ---------------------------------------------------------------------------


def _provision_receivers_case_actor(client: DataLayerClient) -> as_Actor:
    """Host the CaseActor that will create cases for the Receiver's reports.

    A CaseActor is a role the container wears, one per node rather than one
    per report (#1872), so its id is known before any report exists — which is
    what lets the Receiver publish a policy on it *before* the Reporter
    submits; the helper's ``report_id`` only names the actor.  ``POST
    /actors/`` is idempotent, so the later provisioning inside
    :func:`reporter_submits_report` returns this same actor.
    """
    return seed_case_actor_for_report(client, report_id="(pending)")


def _read_embargo(
    client: DataLayerClient, case_actor_id: str, embargo_id: str
) -> as_EmbargoEvent:
    """Read an ``EmbargoEvent`` from the CaseActor's own store."""
    data = client.get(client.dl_path(embargo_id, actor_id=case_actor_id))
    return as_EmbargoEvent.model_validate(data)


def _window(embargo: as_EmbargoEvent) -> timedelta:
    """The embargo's realised duration, start to end."""
    if embargo.start_time is None:
        raise AssertionError(
            f"Embargo {embargo.id_} carries no start_time, so its window"
            " cannot be measured"
        )
    return embargo.end_time - embargo.start_time


def _assert_about_the_case(
    embargo: as_EmbargoEvent, case: as_VulnerabilityCase
) -> None:
    """EP-04-009: on the case-actor's side every embargo names the case."""
    if embargo.context != case.id_:
        raise AssertionError(
            f"Embargo {embargo.id_} is about {embargo.context!r}, expected"
            f" the case {case.id_!r} (EP-04-009)"
        )


def _assert_window_is(
    embargo: as_EmbargoEvent, expected: timedelta, label: str
) -> None:
    """The embargo's window matches *expected* within the clock tolerance."""
    window = _window(embargo)
    if abs(window - expected) > _DEFAULT_WINDOW_TOLERANCE:
        raise AssertionError(
            f"{label} embargo {embargo.id_} runs {window}, expected"
            f" {expected} (±{_DEFAULT_WINDOW_TOLERANCE})"
        )


# ---------------------------------------------------------------------------
# Verification of the creation-time outcome
# ---------------------------------------------------------------------------


def _verify_reporter_terms_active(
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
    active = _read_embargo(client, case_actor_id, proposal_id)
    with demo_check("Active embargo ends when the Reporter proposed"):
        if active.end_time != proposed_end:
            raise AssertionError(
                f"Active embargo ends {active.end_time.isoformat()}, the"
                f" Reporter proposed {proposed_end.isoformat()}"
            )
    with demo_check("Active embargo is now about the case (EP-04-009)"):
        _assert_about_the_case(active, case)
    logger.info(
        "Reporter's terms are the active embargo: %s ends %s",
        active.id_,
        active.end_time.isoformat(),
    )
    return active


def _verify_receiver_default_active(
    client: DataLayerClient,
    case_actor_id: str,
    case: as_VulnerabilityCase,
    proposal_id: str,
) -> as_EmbargoEvent:
    """The Receiver's default, not the Reporter's event, is the active embargo."""
    active_id = case.active_embargo_id
    with demo_check("Active embargo is not the Reporter's proposed event"):
        if active_id is None or active_id == proposal_id:
            raise AssertionError(
                f"Expected the Receiver's default to be active, found"
                f" active_embargo={active_id!r} (proposal {proposal_id!r})"
            )
    assert active_id is not None
    active = _read_embargo(client, case_actor_id, active_id)
    with demo_check(
        f"Active embargo runs the Receiver's {RECEIVER_DEFAULT_DAYS}-day default"
    ):
        _assert_window_is(
            active, timedelta(days=RECEIVER_DEFAULT_DAYS), "Active"
        )
    logger.info(
        "Receiver's default is the active embargo: %s ends %s",
        active.id_,
        active.end_time.isoformat(),
    )
    return active


def _verify_pending_revision(
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
    revision = _read_embargo(
        client, case_actor_id, case.proposed_embargo_ids[0]
    )
    with demo_check("Pending revision is about the case and ends later"):
        _assert_about_the_case(revision, case)
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


def _verify_uncontested(
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
        if _window(active) <= _PROTOCOL_DEFAULT_CEILING:
            raise AssertionError(
                f"Active embargo runs {_window(active)}, within the protocol"
                f" default ceiling {_PROTOCOL_DEFAULT_CEILING}: the fallback"
                " may have been applied instead of the Reporter's terms"
            )
    logger.info(
        "No actor default competed: %s runs %s, nothing pending",
        active.id_,
        _window(active),
    )


def _verify_receiver_replica_agrees(
    client: DataLayerClient,
    vendor: as_Actor,
    offer_id: str,
    canonical: as_VulnerabilityCase,
) -> None:
    """The Receiver's replica shows the same EM outcome as the canonical case.

    The replica's arrival is a causal effect of the CaseActor's
    ``Create(VulnerabilityCase)`` fan-out (ADR-0058), observed here rather
    than gated: nothing downstream depends on it, so a replica that has not
    landed is a recorded check, not a skipped run (EDF-06-005).
    """
    with demo_check(
        "Receiver's replica carries the same EM state (observed, not gated)"
    ):
        replica = wait_for_case_for_offer(client, offer_id)
        if (
            replica.current_status.em_state
            != canonical.current_status.em_state
        ):
            raise AssertionError(
                f"Receiver {vendor.id_} sees {replica.current_status.em_state},"
                f" the CaseActor holds {canonical.current_status.em_state}"
            )


# ---------------------------------------------------------------------------
# The shared run
# ---------------------------------------------------------------------------


def _run_negotiated_submission(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    *,
    reporter_days: int,
    receiver_default_days: Optional[int],
) -> None:
    """Submit a report with proposed terms and verify the creation-time outcome.

    Args:
        client: The single-container client (bound to the Receiver's replica).
        finder: The Reporter.
        vendor: The Receiver.
        reporter_days: Days from now the Reporter proposes the embargo end.
        receiver_default_days: The Receiver's published default, or ``None``
            to publish nothing.
    """
    case_actor = _provision_receivers_case_actor(client)

    if receiver_default_days is None:
        with demo_step("Step 1: Receiver publishes no embargo policy"):
            logger.info(
                "Receiver %s publishes no EmbargoPolicy: there is no actor"
                " default for the Reporter's terms to compete with",
                vendor.id_,
            )
    else:
        with demo_step(
            f"Step 1: Receiver publishes a {receiver_default_days}-day"
            " embargo policy (actor default)"
        ):
            publish_embargo_policy(
                client, case_actor, timedelta(days=receiver_default_days)
            )

    proposed_end = from_now_utc(timedelta(days=reporter_days))
    with demo_gate(
        f"Step 2: Reporter submits the report proposing a {reporter_days}-day"
        " embargo"
    ):
        report, offer = reporter_submits_report(
            client,
            finder,
            vendor,
            reporter_client=client,
            proposed_embargo_end_time=proposed_end,
        )
        proposal = offer.proposed_embargo
        with demo_check("Offer carries the Reporter's proposed terms"):
            if not isinstance(proposal, as_EmbargoEvent):
                raise AssertionError(
                    "Offer carries no proposedEmbargo; the Reporter's terms"
                    " did not leave the trigger (EP-04-004)"
                )
            if proposal.context != report.id_:
                raise AssertionError(
                    f"Proposed terms are about {proposal.context!r}, not the"
                    f" report {report.id_!r} (EP-04-009)"
                )
        assert isinstance(proposal, as_EmbargoEvent)
        proposal_id = proposal.id_

        with demo_gate(
            "Step 3: CASE_MANAGER creates the case and settles the terms"
        ):
            case = wait_for_case_by_report(
                client, report.id_, actor_id=case_actor.id_
            )
            logger.info(
                "Canonical case %s created at %s",
                case.id_,
                case.current_status.em_state,
            )

            if receiver_default_days is None:
                active = _verify_reporter_terms_active(
                    client, case_actor.id_, case, proposal_id, proposed_end
                )
                _verify_uncontested(case, active)
            elif reporter_days < receiver_default_days:
                active = _verify_reporter_terms_active(
                    client, case_actor.id_, case, proposal_id, proposed_end
                )
                revision = _verify_pending_revision(
                    client, case_actor.id_, case, active
                )
                with demo_check(
                    f"Pending revision runs the Receiver's"
                    f" {receiver_default_days}-day default"
                ):
                    _assert_window_is(
                        revision,
                        timedelta(days=receiver_default_days),
                        "Pending",
                    )
            else:
                active = _verify_receiver_default_active(
                    client, case_actor.id_, case, proposal_id
                )
                revision = _verify_pending_revision(
                    client, case_actor.id_, case, active
                )
                with demo_check(
                    "Pending revision is the Reporter's own event, rewritten"
                    " to the case"
                ):
                    if revision.id_ != proposal_id:
                        raise AssertionError(
                            f"Expected the Reporter's proposal {proposal_id!r}"
                            f" to be the pending revision, found"
                            f" {revision.id_!r}"
                        )
                    if revision.end_time != proposed_end:
                        raise AssertionError(
                            f"Revision ends {revision.end_time.isoformat()},"
                            f" the Reporter proposed {proposed_end.isoformat()}"
                        )

            _verify_receiver_replica_agrees(client, vendor, offer.id_, case)


# ---------------------------------------------------------------------------
# The three runs
# ---------------------------------------------------------------------------


def demo_reporter_proposes_shorter(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    coordinator: Optional[as_Actor] = None,
) -> None:
    """Reporter's shorter terms win; the Receiver's default is the revision."""
    logger.info("=" * 80)
    logger.info(
        "DEMO: Report with Embargo — Reporter proposes shorter (%d vs %d days)",
        REPORTER_SHORTER_DAYS,
        RECEIVER_DEFAULT_DAYS,
    )
    logger.info("=" * 80)
    _run_negotiated_submission(
        client,
        finder,
        vendor,
        reporter_days=REPORTER_SHORTER_DAYS,
        receiver_default_days=RECEIVER_DEFAULT_DAYS,
    )
    logger.info(
        "✅ DEMO COMPLETE: the Reporter's %d-day terms are active; the"
        " Receiver's %d-day default is pending as a revision (EM.REVISE).",
        REPORTER_SHORTER_DAYS,
        RECEIVER_DEFAULT_DAYS,
    )


def demo_reporter_proposes_longer(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    coordinator: Optional[as_Actor] = None,
) -> None:
    """Receiver's shorter default wins; the Reporter's terms are the revision."""
    logger.info("=" * 80)
    logger.info(
        "DEMO: Report with Embargo — Reporter proposes longer (%d vs %d days)",
        REPORTER_LONGER_DAYS,
        RECEIVER_DEFAULT_DAYS,
    )
    logger.info("=" * 80)
    _run_negotiated_submission(
        client,
        finder,
        vendor,
        reporter_days=REPORTER_LONGER_DAYS,
        receiver_default_days=RECEIVER_DEFAULT_DAYS,
    )
    logger.info(
        "✅ DEMO COMPLETE: the Receiver's %d-day default is active; the"
        " Reporter's %d-day terms are pending as a revision (EM.REVISE).",
        RECEIVER_DEFAULT_DAYS,
        REPORTER_LONGER_DAYS,
    )


def demo_receiver_has_no_default(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    coordinator: Optional[as_Actor] = None,
) -> None:
    """No actor default: the Reporter's terms win outright, at their length."""
    logger.info("=" * 80)
    logger.info(
        "DEMO: Report with Embargo — Receiver has no actor default (%d days"
        " proposed)",
        REPORTER_SHORTER_DAYS,
    )
    logger.info("=" * 80)
    _run_negotiated_submission(
        client,
        finder,
        vendor,
        reporter_days=REPORTER_SHORTER_DAYS,
        receiver_default_days=None,
    )
    logger.info(
        "✅ DEMO COMPLETE: the Reporter's %d-day terms are active with nothing"
        " pending; the protocol default did not compete (EP-04-006).",
        REPORTER_SHORTER_DAYS,
    )


_ALL_DEMOS: Sequence[Tuple[str, Callable[..., None]]] = [
    (
        "Demo: Report with Embargo — Reporter proposes shorter",
        demo_reporter_proposes_shorter,
    ),
    (
        "Demo: Report with Embargo — Reporter proposes longer",
        demo_reporter_proposes_longer,
    ),
    (
        "Demo: Report with Embargo — Receiver has no actor default",
        demo_receiver_has_no_default,
    ),
]


def main(
    skip_health_check: bool = False,
    demos: Optional[Sequence] = None,
) -> None:
    """Main entry point for the report-with-embargo demo script."""
    run_exchange_demos(
        _ALL_DEMOS, skip_health_check=skip_health_check, demos=demos
    )


if __name__ == "__main__":
    setup_demo_logging()
    main()
