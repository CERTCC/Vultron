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
from typing import Callable, Optional, Sequence, Tuple

# Vultron imports
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.demo.helpers.runner import run_exchange_demos
from vultron.demo.helpers.workflow import setup_initialized_case
from vultron.demo.utils import (  # noqa: F401 — BASE_URL needed for test monkeypatching
    BASE_URL,
    DataLayerClient,
    demo_check,
    demo_step,
    log_case_state,
    logfmt,
    post_to_inbox_and_wait,
    verify_object_stored,
    setup_demo_logging,
)
from vultron.wire.as2.factories import (
    accept_case_participant_offer_activity,
    offer_case_participant_activity,
    recommend_actor_activity,
    reject_case_participant_offer_activity,
)

logger = logging.getLogger(__name__)


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

    case = setup_initialized_case(client, finder, vendor)

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

    case = setup_initialized_case(client, finder, vendor)

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
    """Main entry point for the suggest_actor demo script."""
    run_exchange_demos(
        _ALL_DEMOS, skip_health_check=skip_health_check, demos=demos
    )


if __name__ == "__main__":
    setup_demo_logging()
    main()
