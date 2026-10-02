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
pending as ``EM.REVISE`` — and, when the pending terms are the Reporter's,
the Receiver's answer to them: the CASE_MANAGER relays every creation-time
revision to the party whose terms won (EP-04-011).

Three runs:

1. **Reporter proposes shorter** than the Receiver's actor default (10 vs 30
   days): the Reporter's own terms become the active embargo, identity kept,
   and the Receiver's longer default is registered as a pending revision, so
   the case is created at ``EM.REVISE``.
2. **Reporter proposes longer** (60 vs 30 days): the Receiver's default is the
   active embargo at creation and the Reporter's terms — the same
   ``EmbargoEvent`` the Reporter sent, now about the case rather than the
   report (EP-04-009) — are the pending revision, relayed to the Receiver.
   The Receiver is the CASE_OWNER, so its acceptance (the default response
   decision) activates the Reporter's terms and the case settles at
   ``EM.ACTIVE``.  In run 1 the relay goes to the Reporter instead, whose
   acceptance only records consent, so that case stays at ``EM.REVISE``.
3. **Receiver has no actor default**: the Reporter's terms are the only
   candidate and win outright at their stated length.  The 10-day proposal
   is longer than the protocol default's 5-day ceiling (EP-04-005), so an
   active 10-day embargo shows the proposal was honored (EP-04-007) and the
   protocol default did not compete (EP-04-006).

Whose default is "the Receiver's".  The actor default is the policy on the
CASE_OWNER's own actor profile — the Receiver, the actor that received the
report (EP-04-003, CP-09-001).  Step 1 publishes it on the Receiver, which
writes it into the Receiver's profile (EP-01-001); the Receiver then sends
that profile inline as the ``actor`` of its ``Create(CaseProposal)``, and the
CASE_MANAGER reads the default from there and nowhere else (CP-01-010).

Puppeteering.  The Reporter is driven through its ``submit-report`` trigger
(``proposed_embargo_end_time``), the Receiver through the embargo-policy
endpoint; no protocol activity is forged.  The Offer is then delivered to the
Receiver's inbox in the way every exchange demo delivers (``exchange/README``).

This corresponds to the workflow documented in
``docs/howto/activitypub/activities/report_vulnerability.md`` § "Submit a
report" and the semantics in ``notes/embargo-default-semantics.md``.
"""

import logging
from collections.abc import Callable, Sequence
from datetime import timedelta

from vultron.core.models._helpers import from_now_utc
from vultron.demo.helpers.embargo import publish_embargo_policy
from vultron.demo.helpers.embargo_outcome import (
    assert_window_is,
    verify_pending_revision,
    verify_receiver_replica_agrees,
    verify_reporter_terms_active,
    verify_revision_settled,
    verify_uncontested,
    wait_for_revision_activated,
)
from vultron.demo.helpers.runner import run_exchange_demos
from vultron.demo.helpers.workflow import (
    reporter_submits_report,
    wait_for_case_by_report,
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

logger = logging.getLogger(__name__)

#: The Receiver's published default in the two contested runs.
RECEIVER_DEFAULT_DAYS = 30
#: A Reporter proposal shorter than the Receiver's default — and longer than
#: the protocol default's 5-day ceiling (EP-04-005), so run 3 can tell the
#: proposal apart from the fallback.
REPORTER_SHORTER_DAYS = 10
#: A Reporter proposal longer than the Receiver's default.
REPORTER_LONGER_DAYS = 60


# ---------------------------------------------------------------------------
# Provisioning


def _provision_receivers_case_actor(client: DataLayerClient) -> as_Actor:
    """Host the CaseActor that will create cases for the Receiver's reports.

    A CaseActor is a role the container wears, one per node rather than one
    per report (#1872), so its id is known before any report exists and the
    run can read the case from its store once it is created; the helper's
    ``report_id`` only names the actor.  ``POST /actors/`` is idempotent, so
    the later provisioning inside :func:`reporter_submits_report` returns
    this same actor.
    """
    return seed_case_actor_for_report(client, report_id="(pending)")


# ---------------------------------------------------------------------------
# The shared run
# ---------------------------------------------------------------------------


def _run_negotiated_submission(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    *,
    reporter_days: int,
    receiver_default_days: int | None,
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
            " embargo policy (actor default) on its own profile"
        ):
            publish_embargo_policy(
                client, vendor, timedelta(days=receiver_default_days)
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
                raise AssertionError(  # noqa: TRY004 — demo_check assertion, not a type error
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
                active = verify_reporter_terms_active(
                    client, case_actor.id_, case, proposal_id, proposed_end
                )
                verify_uncontested(case, active)
            elif reporter_days < receiver_default_days:
                active = verify_reporter_terms_active(
                    client, case_actor.id_, case, proposal_id, proposed_end
                )
                revision = verify_pending_revision(
                    client, case_actor.id_, case, active
                )
                with demo_check(
                    f"Pending revision runs the Receiver's"
                    f" {receiver_default_days}-day default"
                ):
                    assert_window_is(
                        revision,
                        timedelta(days=receiver_default_days),
                        "Pending",
                    )
            else:
                # The Receiver's shorter default won at creation and the
                # Reporter's terms were registered as a revision and relayed
                # to the Receiver, the CASE_OWNER (EP-04-011).  Its default
                # response decision accepts, and an owner's acceptance
                # activates the revision — so the settled outcome is the
                # Reporter's terms, reached through the Receiver's answer.
                with demo_gate(
                    "Step 4: Receiver answers the relayed revision Invite"
                ):
                    case = wait_for_revision_activated(
                        client, case_actor.id_, case.id_, proposal_id
                    )
                    verify_reporter_terms_active(
                        client, case_actor.id_, case, proposal_id, proposed_end
                    )
                    verify_revision_settled(case)

            verify_receiver_replica_agrees(client, vendor, offer.id_, case)


# ---------------------------------------------------------------------------
# The three runs
# ---------------------------------------------------------------------------


def demo_reporter_proposes_shorter(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    coordinator: as_Actor | None = None,
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
    coordinator: as_Actor | None = None,
) -> None:
    """Receiver's default wins; it then accepts the Reporter's longer revision."""
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
        "✅ DEMO COMPLETE: the Receiver's %d-day default won at creation;"
        " it accepted the Reporter's relayed %d-day revision, now active"
        " (EM.ACTIVE).",
        RECEIVER_DEFAULT_DAYS,
        REPORTER_LONGER_DAYS,
    )


def demo_receiver_has_no_default(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    coordinator: as_Actor | None = None,
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


_ALL_DEMOS: Sequence[tuple[str, Callable[..., None]]] = [
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
    demos: Sequence | None = None,
) -> None:
    """Main entry point for the report-with-embargo demo script."""
    run_exchange_demos(
        _ALL_DEMOS, skip_health_check=skip_health_check, demos=demos
    )


if __name__ == "__main__":
    setup_demo_logging()
    main()
