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

This demo script showcases two suggestion paths per ADR-0026 (CaseActor-routed):

1. Accept path:
   - Finder → CaseActor inbox: Offer(Actor, Case)
   - CaseActor → Case Owner inbox: Offer(as_CaseParticipant{actor, roles}, Case)
   - Case Owner → CaseActor inbox: Accept(Offer(as_CaseParticipant))
   - CaseActor → Finder inbox: AcceptActorRecommendation
   - CaseActor → Coordinator inbox: Invite(CaseStub+embargo+roles)

2. Reject path:
   - Finder → CaseActor inbox: Offer(Actor, Case)
   - CaseActor → Case Owner inbox: Offer(as_CaseParticipant{actor, roles}, Case)
   - Case Owner → CaseActor inbox: Reject(Offer(as_CaseParticipant))
   - CaseActor → Finder inbox: RejectActorRecommendation

In this single-process prototype, vendor acts as both Case Owner and
CaseActor so the recommendation routes through vendor's inbox in both roles.
A full multi-process deployment would have a distinct CaseActor service URI.

Each demo starts from an initialized case (report submitted and validated,
case created, finder participant added) so that the suggestion workflow can
be demonstrated in isolation.
"""

# Standard library imports
import logging
import sys
from typing import Callable, Optional, Sequence, Tuple

# Vultron imports
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Create
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.case_participant import (
    as_CaseParticipant,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
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
    setup_demo_logging,
)
from vultron.wire.as2.factories import (
    accept_case_participant_offer_activity,
    add_participant_to_case_activity,
    add_report_to_case_activity,
    create_case_activity,
    offer_case_participant_activity,
    recommend_actor_activity,
    reject_case_participant_offer_activity,
    rm_submit_report_activity,
    rm_validate_report_activity,
)

logger = logging.getLogger(__name__)


def _setup_initialized_case(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
) -> as_VulnerabilityCase:
    """
    Set up an initialized case as a precondition for the suggest workflow.

    Mirrors the setup helper in invite_actor_demo but returns the
    as_VulnerabilityCase so subsequent steps can reference it.
    """
    report = as_VulnerabilityReport(
        attributed_to=finder.id_,
        content="A remote code execution vulnerability in the web framework.",
        name="Remote Code Execution Vulnerability",
    )
    report_offer = rm_submit_report_activity(
        report, actor=finder.id_, to=vendor.id_
    )
    post_to_inbox_and_wait(client, vendor.id_, report_offer)
    verify_object_stored(client, report.id_)

    offer = get_offer_from_datalayer(client, vendor.id_, report_offer.id_)
    validate_activity = rm_validate_report_activity(
        offer,
        actor=vendor.id_,
        content="Confirmed — remote code execution via unsanitized input.",
    )
    post_to_inbox_and_wait(client, vendor.id_, validate_activity)

    case = as_VulnerabilityCase(
        attributed_to=vendor.id_,
        name="RCE Case — Web Framework",
        content="Tracking the RCE vulnerability in the web framework.",
    )
    create_case_act = create_case_activity(case, actor=vendor.id_)
    post_to_inbox_and_wait(client, vendor.id_, create_case_act)
    verify_object_stored(client, case.id_)

    add_report_activity = add_report_to_case_activity(
        report, actor=vendor.id_, target=case.id_
    )
    post_to_inbox_and_wait(client, vendor.id_, add_report_activity)

    participant = as_CaseParticipant(
        case_roles=[CVDRole.FINDER, CVDRole.REPORTER],
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

    add_participant_activity = add_participant_to_case_activity(
        participant, actor=vendor.id_, target=case.id_
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
    """Demonstrates the accept path of the suggest-actor-to-case workflow.

    ADR-0026 CaseActor-routed protocol:

    1. Setup: initialize case
    2. Finder → CaseActor inbox: Offer(Actor, Case)
    3. CaseActor → Case Owner inbox: Offer(as_CaseParticipant{actor,roles}, Case)
    4. Case Owner → CaseActor inbox: Accept(Offer(as_CaseParticipant))
    5. Verify acceptance persisted

    In this single-process prototype vendor acts as CaseActor.
    """
    logger.info("=" * 80)
    logger.info("DEMO: Suggest Actor — Accept Path (ADR-0026)")
    logger.info("=" * 80)

    case = _setup_initialized_case(client, finder, vendor)

    with demo_step(
        "Step 2: Finder sends Offer(Actor, Case) to CaseActor inbox"
    ):
        # Per ADR-0026/CM-16-001: recommendation routes to CaseActor inbox.
        # In this prototype vendor.id_ is the CaseActor identity.
        recommendation = recommend_actor_activity(
            coordinator,
            actor=finder.id_,
            target=case.id_,
            to=[vendor.id_],
            content=(
                f"I suggest inviting {coordinator.id_} to participate in "
                f"{case.name}."
            ),
        )
        logger.info(f"Sending Offer(Actor,Case): {logfmt(recommendation)}")
        post_to_inbox_and_wait(client, vendor.id_, recommendation)
        with demo_check("Offer(Actor,Case) stored in data layer"):
            verify_object_stored(client, recommendation.id_)

    with demo_step(
        "Step 3: CaseActor transforms to Offer(as_CaseParticipant) → Case Owner"
    ):
        # Per ADR-0026/CM-16-004: CaseActor transforms and forwards with
        # origin=original-offer-id.
        cp_offer = offer_case_participant_activity(
            coordinator,
            target=case.id_,
            actor=vendor.id_,
            to=[vendor.id_],
            origin=recommendation.id_,
            content=(
                f"Recommending {coordinator.id_} for case participation "
                f"(roles: VENDOR). Origin: {recommendation.id_}"
            ),
        )
        logger.info(f"Sending Offer(as_CaseParticipant): {logfmt(cp_offer)}")
        post_to_inbox_and_wait(client, vendor.id_, cp_offer)
        with demo_check("Offer(as_CaseParticipant) stored in data layer"):
            verify_object_stored(client, cp_offer.id_)

    with demo_step(
        "Step 4: Case Owner sends Accept(Offer(as_CaseParticipant)) to CaseActor"
    ):
        # Per ADR-0026/CM-16-006: Accept routes to CaseActor inbox.
        accept = accept_case_participant_offer_activity(
            cp_offer,
            actor=vendor.id_,
            to=[vendor.id_],
            content=(
                f"Accepting recommendation to add "
                f"{coordinator.id_} to {case.name}."
            ),
        )
        logger.info(
            f"Sending Accept(Offer(as_CaseParticipant)): {logfmt(accept)}"
        )
        post_to_inbox_and_wait(client, vendor.id_, accept)
        with demo_check("Accept stored in data layer"):
            verify_object_stored(client, accept.id_)
        with demo_check("Case state after accept"):
            log_case_state(client, case.id_, "after accept")

    logger.info(
        "✅ DEMO COMPLETE (accept path): CaseActor should now send "
        "AcceptActorRecommendation to finder and Invite to coordinator."
    )


def demo_suggest_actor_reject(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    coordinator: as_Actor,
) -> None:
    """Demonstrates the reject path of the suggest-actor-to-case workflow.

    ADR-0026 CaseActor-routed protocol:

    1. Setup: initialize case
    2. Finder → CaseActor inbox: Offer(Actor, Case)
    3. CaseActor → Case Owner inbox: Offer(as_CaseParticipant{actor,roles}, Case)
    4. Case Owner → CaseActor inbox: Reject(Offer(as_CaseParticipant))
    5. Verify no new participant was added
    """
    logger.info("=" * 80)
    logger.info("DEMO: Suggest Actor — Reject Path (ADR-0026)")
    logger.info("=" * 80)

    case = _setup_initialized_case(client, finder, vendor)

    initial_case = log_case_state(client, case.id_, "initial")
    initial_count = len(initial_case.case_participants) if initial_case else 0

    with demo_step(
        "Step 2: Finder sends Offer(Actor, Case) to CaseActor inbox"
    ):
        recommendation = recommend_actor_activity(
            coordinator,
            actor=finder.id_,
            target=case.id_,
            to=[vendor.id_],
            content=(
                f"I suggest inviting {coordinator.id_} to participate in "
                f"{case.name}."
            ),
        )
        logger.info(f"Sending Offer(Actor,Case): {logfmt(recommendation)}")
        post_to_inbox_and_wait(client, vendor.id_, recommendation)
        with demo_check("Offer(Actor,Case) stored in data layer"):
            verify_object_stored(client, recommendation.id_)

    with demo_step(
        "Step 3: CaseActor transforms to Offer(as_CaseParticipant) → Case Owner"
    ):
        cp_offer = offer_case_participant_activity(
            coordinator,
            target=case.id_,
            actor=vendor.id_,
            to=[vendor.id_],
            origin=recommendation.id_,
            content=(
                f"Recommending {coordinator.id_} for case participation "
                f"(roles: VENDOR). Origin: {recommendation.id_}"
            ),
        )
        logger.info(f"Sending Offer(as_CaseParticipant): {logfmt(cp_offer)}")
        post_to_inbox_and_wait(client, vendor.id_, cp_offer)
        with demo_check("Offer(as_CaseParticipant) stored in data layer"):
            verify_object_stored(client, cp_offer.id_)

    with demo_step(
        "Step 4: Case Owner sends Reject(Offer(as_CaseParticipant)) to CaseActor"
    ):
        reject = reject_case_participant_offer_activity(
            cp_offer,
            actor=vendor.id_,
            to=[vendor.id_],
            content=(
                f"Declining recommendation to add "
                f"{coordinator.id_} to {case.name}."
            ),
        )
        logger.info(
            f"Sending Reject(Offer(as_CaseParticipant)): {logfmt(reject)}"
        )
        post_to_inbox_and_wait(client, vendor.id_, reject)

    with demo_step("Step 5: Verify coordinator not added as participant"):
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


if __name__ == "__main__":
    setup_demo_logging()
    main()
