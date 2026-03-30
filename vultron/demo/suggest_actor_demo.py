#!/usr/bin/env python

#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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
Demonstrates the workflow for suggesting an actor for a case via the Vultron API.

This demo script showcases two suggestion paths:

1. Accept path: finder suggests coordinator → vendor (case owner) accepts →
   vendor sends invitation to coordinator
2. Reject path: finder suggests coordinator → vendor (case owner) rejects →
   no invitation is sent

Each demo starts from an initialized case (report submitted and validated,
case created, finder participant added) so that the suggestion workflow can
be demonstrated in isolation.

This corresponds to the workflow documented in:
    docs/howto/activitypub/activities/suggest_actor.md

When run as a script, this module will:
1. Check if the API server is available
2. Reset the data layer to a clean state
3. Discover actors (finder, vendor, coordinator) via the API
4. Run both demo workflows (accept and reject)
5. Verify side effects in the data layer

Note on direct inbox communication:
This demo uses direct inbox-to-inbox communication between actors, per the
Vultron prototype design. Actors post activities directly to each other's
inboxes.
"""

# Standard library imports
import logging
import sys
from typing import Callable, Optional, Sequence, Tuple

# Vultron imports
from vultron.wire.as2.vocab.activities.actor import (
    AcceptActorRecommendationActivity,
    RecommendActorActivity,
    RejectActorRecommendationActivity,
)
from vultron.wire.as2.vocab.activities.case import (
    AddReportToCaseActivity,
    CreateCaseActivity,
)
from vultron.wire.as2.vocab.activities.case_participant import (
    AddParticipantToCaseActivity,
)
from vultron.wire.as2.vocab.activities.report import (
    RmSubmitReportActivity,
    RmValidateReportActivity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Create
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.case_participant import (
    FinderReporterParticipant,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    VulnerabilityReport,
)
from vultron.demo.utils import (  # noqa: F401 — BASE_URL needed for test monkeypatching
    BASE_URL,
    DataLayerClient,
    check_server_availability,
    demo_check,
    demo_step,
    get_offer_from_datalayer,
    log_case_state,
    logfmt,
    demo_environment,
    post_to_inbox_and_wait,
    verify_object_stored,
)

logger = logging.getLogger(__name__)


def _setup_initialized_case(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
) -> VulnerabilityCase:
    """
    Set up an initialized case as a precondition for the suggest workflow.

    Mirrors the setup helper in invite_actor_demo but returns the
    VulnerabilityCase so subsequent steps can reference it.
    """
    report = VulnerabilityReport(
        attributed_to=finder.id_,
        content="A remote code execution vulnerability in the web framework.",
        name="Remote Code Execution Vulnerability",
    )
    report_offer = RmSubmitReportActivity(
        actor=finder.id_,
        object_=report,
        to=[vendor.id_],
    )
    post_to_inbox_and_wait(client, vendor.id_, report_offer)
    verify_object_stored(client, report.id_)

    offer = get_offer_from_datalayer(client, vendor.id_, report_offer.id_)
    validate_activity = RmValidateReportActivity(
        actor=vendor.id_,
        object_=offer.id_,
        content="Confirmed — remote code execution via unsanitized input.",
    )
    post_to_inbox_and_wait(client, vendor.id_, validate_activity)

    case = VulnerabilityCase(
        attributed_to=vendor.id_,
        name="RCE Case — Web Framework",
        content="Tracking the RCE vulnerability in the web framework.",
    )
    create_case_activity = CreateCaseActivity(
        actor=vendor.id_,
        object_=case,
    )
    post_to_inbox_and_wait(client, vendor.id_, create_case_activity)
    verify_object_stored(client, case.id_)

    add_report_activity = AddReportToCaseActivity(
        actor=vendor.id_,
        object_=report.id_,
        target=case.id_,
    )
    post_to_inbox_and_wait(client, vendor.id_, add_report_activity)

    participant = FinderReporterParticipant(
        attributed_to=finder.id_,
        context=case.id_,
    )
    create_participant_activity = as_Create(
        actor=vendor.id_,
        object_=participant,
        context=case.id_,
    )
    post_to_inbox_and_wait(client, vendor.id_, create_participant_activity)
    verify_object_stored(client, participant.id_)

    add_participant_activity = AddParticipantToCaseActivity(
        actor=vendor.id_,
        object_=participant.id_,
        target=case.id_,
    )
    post_to_inbox_and_wait(client, vendor.id_, add_participant_activity)

    log_case_state(client, case.id_, "after setup")
    logger.info("✓ Setup: Case initialized with report and finder participant")
    return case


def demo_suggest_actor_accept(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    coordinator: as_Actor,
) -> None:
    """
    Demonstrates the accept path of the suggest-actor-to-case workflow.

    Steps:
    1. Setup: initialize case (report submitted + validated, case created,
       finder participant added)
    2. Finder recommends coordinator to vendor (RecommendActor → vendor inbox)
    3. Vendor accepts recommendation (AcceptActorRecommendation → finder inbox)
    4. Verify the acceptance was persisted

    This follows the accept branch in
    docs/howto/activitypub/activities/suggest_actor.md.
    """
    logger.info("=" * 80)
    logger.info("DEMO: Suggest Actor — Accept Path")
    logger.info("=" * 80)

    case = _setup_initialized_case(client, finder, vendor)

    with demo_step("Step 2: Finder recommends coordinator to vendor"):
        recommendation = RecommendActorActivity(
            actor=finder.id_,
            object_=coordinator.id_,
            target=case.id_,
            to=[vendor.id_],
            content=(
                f"I suggest inviting {coordinator.id_} to participate in "
                f"{case.name}."
            ),
        )
        logger.info(f"Sending recommendation: {logfmt(recommendation)}")
        post_to_inbox_and_wait(client, vendor.id_, recommendation)
        with demo_check("Recommendation stored in data layer"):
            verify_object_stored(client, recommendation.id_)

    with demo_step("Step 3: Vendor accepts recommendation"):
        accept = AcceptActorRecommendationActivity(
            actor=vendor.id_,
            object_=recommendation.id_,
            to=[finder.id_],
            content=(
                f"Accepting your suggestion to invite "
                f"{coordinator.id_} to {case.name}."
            ),
        )
        logger.info(f"Sending accept: {logfmt(accept)}")
        post_to_inbox_and_wait(client, finder.id_, accept)
        with demo_check("Acceptance stored in data layer"):
            verify_object_stored(client, accept.id_)
        with demo_check("Case state after accept"):
            log_case_state(client, case.id_, "after accept")

    logger.info(
        "✅ DEMO COMPLETE (accept path): Recommendation accepted. "
        "Vendor should now invite the coordinator."
    )


def demo_suggest_actor_reject(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    coordinator: as_Actor,
) -> None:
    """
    Demonstrates the reject path of the suggest-actor-to-case workflow.

    Steps:
    1. Setup: initialize case (report submitted + validated, case created,
       finder participant added)
    2. Finder recommends coordinator to vendor (RecommendActor → vendor inbox)
    3. Vendor rejects recommendation (RejectActorRecommendation → finder inbox)
    4. Verify no new participant was added

    This follows the reject branch in
    docs/howto/activitypub/activities/suggest_actor.md.
    """
    logger.info("=" * 80)
    logger.info("DEMO: Suggest Actor — Reject Path")
    logger.info("=" * 80)

    case = _setup_initialized_case(client, finder, vendor)

    initial_case = log_case_state(client, case.id_, "initial")
    initial_count = len(initial_case.case_participants) if initial_case else 0

    with demo_step("Step 2: Finder recommends coordinator to vendor"):
        recommendation = RecommendActorActivity(
            actor=finder.id_,
            object_=coordinator.id_,
            target=case.id_,
            to=[vendor.id_],
            content=(
                f"I suggest inviting {coordinator.id_} to participate in "
                f"{case.name}."
            ),
        )
        logger.info(f"Sending recommendation: {logfmt(recommendation)}")
        post_to_inbox_and_wait(client, vendor.id_, recommendation)
        with demo_check("Recommendation stored in data layer"):
            verify_object_stored(client, recommendation.id_)

    with demo_step("Step 3: Vendor rejects recommendation"):
        reject = RejectActorRecommendationActivity(
            actor=vendor.id_,
            object_=recommendation.id_,
            to=[finder.id_],
            content=(
                f"Declining your suggestion to invite "
                f"{coordinator.id_} to {case.name}."
            ),
        )
        logger.info(f"Sending reject: {logfmt(reject)}")
        post_to_inbox_and_wait(client, finder.id_, reject)

    with demo_step("Step 4: Verify coordinator not added as participant"):
        with demo_check("Participant count unchanged after reject"):
            final_case = log_case_state(client, case.id_, "after reject")
            if final_case is None:
                raise ValueError("Could not retrieve case after reject")
            final_count = len(final_case.case_participants)
            if final_count != initial_count:
                raise ValueError(
                    f"Expected participant count to remain {initial_count} after "
                    f"reject, got {final_count}"
                )

    logger.info(
        "✅ DEMO COMPLETE (reject path): Recommendation rejected gracefully."
    )


_ALL_DEMOS: Sequence[Tuple[str, Callable[..., None]]] = [
    ("Demo: Suggest Actor — Accept Path", demo_suggest_actor_accept),
    ("Demo: Suggest Actor — Reject Path", demo_suggest_actor_reject),
]


def main(
    skip_health_check: bool = False,
    demos: Optional[Sequence] = None,
) -> None:
    """
    Main entry point for the suggest_actor demo script.

    Args:
        skip_health_check: Skip server availability check (useful for testing)
        demos: Optional sequence of demo functions to run. Defaults to all.
    """
    client = DataLayerClient()

    if not skip_health_check and not check_server_availability(client):
        logger.error("=" * 80)
        logger.error("ERROR: API server is not available")
        logger.error("=" * 80)
        logger.error(f"Cannot connect to: {client.base_url}")
        logger.error("")
        logger.error("Please ensure the Vultron API server is running:")
        logger.error(
            "  uv run uvicorn vultron.api.main:app --host localhost --port 7999"
        )
        logger.error("=" * 80)
        sys.exit(1)

    selected = (
        _ALL_DEMOS
        if demos is None
        else [(name, fn) for name, fn in _ALL_DEMOS if fn in demos]
    )
    total = len(selected)
    errors = []

    for demo_name, demo_fn in selected:
        try:
            with demo_environment(client) as (finder, vendor, coordinator):
                demo_fn(client, finder, vendor, coordinator)
        except Exception as e:
            logger.error(f"{demo_name} failed: {e}", exc_info=True)
            errors.append((demo_name, str(e)))

    logger.info("=" * 80)
    logger.info("ALL DEMOS COMPLETE")
    logger.info("=" * 80)

    if errors:
        logger.error("")
        logger.error("=" * 80)
        logger.error("ERROR SUMMARY")
        logger.error("=" * 80)
        logger.error(f"Total demos: {total}")
        logger.error(f"Failed demos: {len(errors)}")
        logger.error(f"Successful demos: {total - len(errors)}")
        logger.error("")
        for demo_name, error in errors:
            logger.error(f"{demo_name}:")
            logger.error(f"  {error}")
            logger.error("")
        logger.error("=" * 80)
    else:
        logger.info("")
        logger.info(f"✓ All {total} demos completed successfully!")
        logger.info("")


def _setup_logging():
    """Configure console logging for standalone script execution."""
    logging.getLogger("requests").setLevel(logging.WARNING)
    logger_ = logging.getLogger()
    hdlr = logging.StreamHandler(sys.stdout)
    import logging as _logging

    formatter = _logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    hdlr.setFormatter(formatter)
    logger_.addHandler(hdlr)
    logger_.setLevel(logging.DEBUG)


if __name__ == "__main__":
    _setup_logging()
    main()
