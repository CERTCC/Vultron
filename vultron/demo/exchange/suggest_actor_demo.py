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

1. Accept path, each act through its actor's trigger (#5438):
   - Reporter → CASE_MANAGER: Offer(Actor, Case) (``suggest-actor-to-case``)
   - CASE_MANAGER → Case Owner: Offer(as_CaseParticipant{actor, roles}, Case)
   - Case Owner → CASE_MANAGER: Accept(Offer(as_CaseParticipant))
     (``accept-actor-recommendation``)
   - CASE_MANAGER → Coordinator: Invite(CaseStub+embargo+roles)

2. Reject path:
   - Reporter → CaseActor inbox: Offer(Actor, Case)
   - CaseActor → Case Owner inbox: Offer(as_CaseParticipant{actor, roles}, Case)
   - Case Owner → CaseActor inbox: Reject(Offer(as_CaseParticipant))
   - CaseActor → Reporter inbox: RejectActorRecommendation

The vendor mints the case through ``create-case``, so it holds both
CASE_OWNER and CASE_MANAGER and the recommendation routes through its inbox
in both roles.  The reject path still builds its activities by hand and posts
them into the vendor's inbox, which refuses the Case Owner's Reject: no
trigger sends it yet (#5459).

Each demo starts from an initialized case (report submitted and validated,
case created, reporter participant added) so that the suggestion workflow can
be demonstrated in isolation.
"""

# Standard library imports
import logging
from collections.abc import Callable, Sequence

from vultron.demo.actor_session import ActorSession
from vultron.demo.helpers.polling import (
    find_case_invite_for_actor,
    find_cp_offer_for_case,
)
from vultron.demo.helpers.runner import run_exchange_demos
from vultron.demo.helpers.workflow import setup_initialized_case
from vultron.demo.utils import (  # noqa: F401 — BASE_URL needed for test monkeypatching
    BASE_URL,
    DataLayerClient,
    demo_check,
    demo_gate,
    demo_step,
    log_case_state,
    logfmt,
    post_to_inbox_and_wait,
    setup_demo_logging,
    verify_received_activity_stored,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.factories import (
    offer_case_participant_activity,
    recommend_actor_activity,
    reject_case_participant_offer_activity,
)

# Vultron imports
from vultron.wire.as2.vocab.base.objects.actors import as_Actor

logger = logging.getLogger(__name__)


def demo_suggest_actor_accept(
    client: DataLayerClient,
    reporter: as_Actor,
    vendor: as_Actor,
    coordinator: as_Actor,
) -> None:
    """Demonstrates the accept path of the suggest-actor-to-case workflow.

    ADR-0026 CaseActor-routed protocol, each act through its actor's trigger:

    1. Setup: initialize case
    2. Reporter → CASE_MANAGER: Offer(Actor, Case)
    3. CASE_MANAGER → Case Owner: Offer(as_CaseParticipant{actor,roles}, Case)
    4. Case Owner → CASE_MANAGER: Accept(Offer(as_CaseParticipant))
    5. CASE_MANAGER → coordinator: Invite to the case

    The vendor minted the case, so it holds both CASE_OWNER and CASE_MANAGER.
    """
    logger.info("=" * 80)
    logger.info("DEMO: Suggest Actor — Accept Path (ADR-0026)")
    logger.info("=" * 80)

    case = setup_initialized_case(client, reporter, vendor)

    # The reporter's suggest-actor-to-case trigger sends Offer(Actor, Case) to
    # the case's CASE_MANAGER (CM-16-001), which forwards it to the Case Owner
    # as Offer(CaseParticipant) and records that it did (CM-16-004).  The demo
    # builds and posts neither: the Case Owner's Accept of an Offer the
    # CASE_MANAGER never recorded is refused (#5438).
    with demo_step(
        "Step 2: Reporter recommends the coordinator (suggest-actor-to-case)"
    ):
        ActorSession(client=client, actor=reporter).with_case(
            case
        ).quiet().suggest_actor_to_case(
            suggested_actor_id=coordinator.id_, roles=[CVDRole.VENDOR]
        )

    cp_offer_id = None
    with demo_gate(
        "Step 3: CASE_MANAGER forwarded Offer(CaseParticipant) to the Case Owner"
    ):
        cp_offer_id = find_cp_offer_for_case(client, case.id_)
        logger.info("Forwarded Offer(CaseParticipant): %s", cp_offer_id)

        with demo_step(
            "Step 4: Case Owner accepts the recommendation"
            " (accept-actor-recommendation)"
        ):
            ActorSession(
                client=client, actor=vendor
            ).quiet().accept_actor_recommendation(
                cp_offer_id=cp_offer_id, case_actor_id=vendor.id_
            )

        with demo_check("Step 5: CASE_MANAGER invited the coordinator"):
            # Read through a client bound to the coordinator's own store; the
            # shared client is bound to the vendor.
            invite_id = find_case_invite_for_actor(
                client.model_copy(update={"actor_id": coordinator.id_}),
                case.id_,
                coordinator.id_,
            )
            logger.info("Coordinator received Invite %s", invite_id)

    logger.info(
        "✅ DEMO COMPLETE (accept path): the CASE_MANAGER invited the"
        " recommended coordinator."
    )


def demo_suggest_actor_reject(
    client: DataLayerClient,
    reporter: as_Actor,
    vendor: as_Actor,
    coordinator: as_Actor,
) -> None:
    """Demonstrates the reject path of the suggest-actor-to-case workflow.

    ADR-0026 CaseActor-routed protocol:

    1. Setup: initialize case
    2. Reporter → CaseActor inbox: Offer(Actor, Case)
    3. CaseActor → Case Owner inbox: Offer(as_CaseParticipant{actor,roles}, Case)
    4. Case Owner → CaseActor inbox: Reject(Offer(as_CaseParticipant))
    5. Verify no new participant was added
    """
    logger.info("=" * 80)
    logger.info("DEMO: Suggest Actor — Reject Path (ADR-0026)")
    logger.info("=" * 80)

    case = setup_initialized_case(client, reporter, vendor)

    initial_case = log_case_state(client, case.id_, "initial")
    initial_count = len(initial_case.case_participants) if initial_case else 0

    recommendation = cp_offer = None
    with demo_step(
        "Step 2: Reporter sends Offer(Actor, Case) to CaseActor inbox"
    ):
        recommendation = recommend_actor_activity(
            coordinator,
            actor=reporter.id_,
            target=case.id_,
            to=[vendor.id_],
            content=(
                f"I suggest inviting {coordinator.id_} to participate in "
                f"{case.name}."
            ),
        )
        logger.info("Sending Offer(Actor,Case): %s", logfmt(recommendation))
        post_to_inbox_and_wait(client, vendor.id_, recommendation)
        with demo_check("Offer(Actor,Case) stored in data layer"):
            verify_received_activity_stored(client, recommendation.id_)

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
        logger.info("Sending Offer(as_CaseParticipant): %s", logfmt(cp_offer))
        post_to_inbox_and_wait(client, vendor.id_, cp_offer)
        with demo_check("Offer(as_CaseParticipant) stored in data layer"):
            verify_received_activity_stored(client, cp_offer.id_)

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
            "Sending Reject(Offer(as_CaseParticipant)): %s", logfmt(reject)
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


_ALL_DEMOS: Sequence[tuple[str, Callable[..., None]]] = [
    ("Demo: Suggest Actor — Accept Path", demo_suggest_actor_accept),
    ("Demo: Suggest Actor — Reject Path", demo_suggest_actor_reject),
]


def main(
    skip_health_check: bool = False,
    demos: Sequence | None = None,
) -> None:
    """Main entry point for the suggest_actor demo script."""
    run_exchange_demos(
        _ALL_DEMOS, skip_health_check=skip_health_check, demos=demos
    )


if __name__ == "__main__":
    setup_demo_logging()
    main()
