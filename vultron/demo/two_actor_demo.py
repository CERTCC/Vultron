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

"""Two-actor (Finder + Vendor) multi-container CVD workflow demo.

Orchestrates a complete CVD workflow across two separate API server containers:
a Finder who discovers a vulnerability and a Vendor who validates and engages
the case.  CaseActor is co-located in the Vendor container for this two-actor
scenario (D5-1-G3).

Environment variables
---------------------
``VULTRON_FINDER_BASE_URL``
    Base URL of the Finder container API
    (default: ``http://localhost:7901/api/v2``).
``VULTRON_VENDOR_BASE_URL``
    Base URL of the Vendor container API
    (default: ``http://localhost:7902/api/v2``).

Workflow
--------
1. **Reset**: Clear all container state to a known clean baseline.
2. **Seed**: Create actor records and register peers on both containers.
3. **Submit**: Finder submits a vulnerability report to the Vendor's inbox.
4. **Validate**: Vendor validates the report via the ``validate-report``
   trigger endpoint.
5. **Engage**: Vendor engages the resulting case via the ``engage-case``
   trigger endpoint.
6. **Add Participant**: Vendor directly adds the Finder as a case participant
   (the Finder expressed intent to participate by submitting the report;
   no invite/accept flow is required for initial participants).
7. **Notes Exchange**: Finder posts a question note to the case; Vendor replies
   and the case forwards the reply to the Finder.
8. **Verify**: The Vendor container holds the authoritative case state with
   two participants and two case notes.

References: ``notes/multi-actor-architecture.md`` §4 G5,
``specs/multi-actor-demo.md`` DEMO-MA-03-001 through DEMO-MA-04-002.
"""

import logging
import os
import sys
import time
from typing import Optional, Tuple

from vultron.adapters.utils import parse_id
from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.wire.as2.vocab.activities.case import (
    AddNoteToCaseActivity,
)
from vultron.wire.as2.vocab.activities.case_participant import (
    AddParticipantToCaseActivity,
    CreateParticipantActivity,
)
from vultron.wire.as2.vocab.activities.report import (
    RmSubmitReportActivity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Create
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.case_participant import (
    CaseParticipant,
    FinderReporterParticipant,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    VulnerabilityReport,
)
from vultron.demo.utils import (  # noqa: F401 — re-exported for test monkeypatching
    BASE_URL,
    DataLayerClient,
    check_server_availability,
    demo_check,
    demo_step,
    logfmt,
    post_to_inbox_and_wait,
    post_to_trigger,
    ref_id,
    reset_datalayer,
    seed_actor,
    verify_object_stored,
)

logger = logging.getLogger(__name__)

# Default container base URLs — override via environment variables.
FINDER_BASE_URL = os.environ.get(
    "VULTRON_FINDER_BASE_URL", "http://localhost:7901/api/v2"
)
VENDOR_BASE_URL = os.environ.get(
    "VULTRON_VENDOR_BASE_URL", "http://localhost:7902/api/v2"
)
CASE_ACTOR_BASE_URL = os.environ.get(
    "VULTRON_CASE_ACTOR_BASE_URL", "http://localhost:7903/api/v2"
)

# Deterministic actor IDs from docker-compose-multi-actor.yml (D5-1-G3).
FINDER_ACTOR_ID = "http://finder:7999/api/v2/actors/finder"
VENDOR_ACTOR_ID = "http://vendor:7999/api/v2/actors/vendor"


# ---------------------------------------------------------------------------
# Seeding helpers
# ---------------------------------------------------------------------------


def seed_containers(
    finder_client: DataLayerClient,
    vendor_client: DataLayerClient,
    finder_actor_id: str | None = None,
    vendor_actor_id: str | None = None,
) -> Tuple[as_Actor, as_Actor]:
    """Seed both containers: create actor records and register cross-container peers.

    The seeding is done in two phases to avoid ordering issues:

    1. Create the local actor on each container independently.
    2. Register each actor as a known peer on the other container.

    This function is idempotent: re-running it returns existing actors
    unchanged (the ``POST /actors/`` endpoint is idempotent).

    Args:
        finder_client: Client connected to the Finder container.
        vendor_client: Client connected to the Vendor container.
        finder_actor_id: Optional deterministic URI for the Finder actor.
            When absent the server derives one from ``VULTRON_BASE_URL``.
        vendor_actor_id: Optional deterministic URI for the Vendor actor.
            When absent the server derives one from ``VULTRON_BASE_URL``.

    Returns:
        Tuple of ``(finder, vendor)`` ``as_Actor`` objects as created on their
        respective containers.
    """
    logger.info("Phase 1: creating local actors on each container...")
    finder = seed_actor(
        client=finder_client,
        name="Finder",
        actor_type="Person",
        actor_id=finder_actor_id,
    )
    logger.info("Finder actor seeded on Finder container: %s", finder.id_)

    vendor = seed_actor(
        client=vendor_client,
        name="Vendor",
        actor_type="Organization",
        actor_id=vendor_actor_id,
    )
    logger.info("Vendor actor seeded on Vendor container: %s", vendor.id_)

    logger.info("Phase 2: registering cross-container peers...")
    seed_actor(
        client=finder_client,
        name="Vendor",
        actor_type="Organization",
        actor_id=vendor.id_,
    )
    logger.info("Vendor peer registered on Finder container: %s", vendor.id_)

    seed_actor(
        client=vendor_client,
        name="Finder",
        actor_type="Person",
        actor_id=finder.id_,
    )
    logger.info("Finder peer registered on Vendor container: %s", finder.id_)

    return finder, vendor


def get_actor_by_id(client: DataLayerClient, actor_id: str) -> as_Actor:
    """Fetch an actor record from a container by its full URI.

    Args:
        client: Client connected to the target container.
        actor_id: Full URI of the actor to fetch.

    Returns:
        The ``as_Actor`` object.

    Raises:
        ValueError: If the actor is not found.
    """
    actors = client.get("/actors/")
    for a in actors:
        actor = as_Actor.model_validate(a)
        if actor.id_ == actor_id:
            return actor
    raise ValueError(f"Actor {actor_id!r} not found in container")


def reset_containers(
    finder_client: DataLayerClient,
    vendor_client: DataLayerClient,
    case_actor_client: DataLayerClient | None = None,
) -> None:
    """Reset all containers used by the demo to a clean baseline.

    D5-2 requires repeatable, single-command execution. Resetting each
    container's DataLayer at the start of the run ensures the demo does
    not depend on a prior `docker compose down -v`.
    """
    targets: list[tuple[str, DataLayerClient]] = [
        ("Finder", finder_client),
        ("Vendor", vendor_client),
    ]
    if case_actor_client is not None:
        targets.append(("CaseActor", case_actor_client))

    with demo_step("Resetting actor containers to a clean baseline"):
        for label, client in targets:
            result = reset_datalayer(client=client, init=False)
            logger.debug("%s reset result: %s", label, result)

    with demo_check("All actor containers start with no persisted cases"):
        for label, client in targets:
            cases = client.get("/datalayer/VulnerabilityCases/")
            if cases:
                raise AssertionError(
                    f"{label} container was not reset cleanly: {cases}"
                )


# ---------------------------------------------------------------------------
# Workflow step functions
# ---------------------------------------------------------------------------


def finder_submits_report(
    vendor_client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
) -> Tuple[VulnerabilityReport, RmSubmitReportActivity]:
    """Finder creates a vulnerability report and submits it to the Vendor's inbox.

    The activity is POSTed directly to the Vendor container's inbox endpoint
    (simulating cross-container delivery; in production the Finder's outbox
    handler would deliver this via HTTP to the Vendor's inbox URL).

    Args:
        vendor_client: Client connected to the Vendor container.
        finder: Finder ``as_Actor``.
        vendor: Vendor ``as_Actor``.

    Returns:
        Tuple of ``(report, offer)``.
    """
    report = VulnerabilityReport(
        attributed_to=finder.id_,
        name="Remote Code Execution in Network Stack",
        content=(
            "A critical remote code execution vulnerability was discovered "
            "in the network stack component. An attacker can exploit this "
            "issue to execute arbitrary code with elevated privileges."
        ),
    )
    offer = RmSubmitReportActivity(
        actor=finder.id_,
        object_=report,
        to=[vendor.id_],
    )
    with demo_step("Finder submits vulnerability report to Vendor's inbox"):
        post_to_inbox_and_wait(vendor_client, vendor.id_, offer)
    with demo_check("Report stored in Vendor's DataLayer"):
        verify_object_stored(vendor_client, report.id_)
    with demo_check("Offer stored in Vendor's DataLayer"):
        verify_object_stored(vendor_client, offer.id_)
    logger.info("Report submitted: %s", ref_id(report))
    return report, offer


def vendor_validates_report(
    vendor_client: DataLayerClient,
    vendor: as_Actor,
    offer_id: str,
) -> dict:
    """Vendor validates the submitted report via the trigger endpoint.

    Args:
        vendor_client: Client connected to the Vendor container.
        vendor: Vendor ``as_Actor``.
        offer_id: Full URI of the ``RmSubmitReportActivity`` offer to validate.

    Returns:
        Response dict from the trigger endpoint (contains the validate activity).
    """
    vendor_obj_id = parse_id(vendor.id_)["object_id"]
    with demo_step("Vendor validates the vulnerability report"):
        result = post_to_trigger(
            client=vendor_client,
            actor_id=vendor.id_,
            behavior="validate-report",
            body={"offer_id": offer_id},
        )
    logger.info("Validate-report trigger result for actor %s", vendor_obj_id)
    return result


def vendor_engages_case(
    vendor_client: DataLayerClient,
    vendor: as_Actor,
    case_id: str,
) -> dict:
    """Vendor engages the case via the trigger endpoint.

    Args:
        vendor_client: Client connected to the Vendor container.
        vendor: Vendor ``as_Actor``.
        case_id: Full URI of the ``VulnerabilityCase`` to engage.

    Returns:
        Response dict from the trigger endpoint.
    """
    vendor_obj_id = parse_id(vendor.id_)["object_id"]
    with demo_step("Vendor engages the vulnerability case"):
        result = post_to_trigger(
            client=vendor_client,
            actor_id=vendor.id_,
            behavior="engage-case",
            body={"case_id": case_id},
        )
    logger.info("Engage-case trigger result for actor %s", vendor_obj_id)
    return result


def vendor_adds_finder_as_participant(
    vendor_client: DataLayerClient,
    finder_client: DataLayerClient,
    vendor: as_Actor,
    finder: as_Actor,
    case: VulnerabilityCase,
) -> FinderReporterParticipant:
    """Vendor directly adds the Finder to the case as a FinderReporter participant.

    The Finder already expressed intent to participate by submitting the report,
    so no invite/accept flow is needed.  The Vendor creates the participant
    record and adds it to the case directly.  A notification is sent to the
    Finder's inbox so the Finder learns they were added.

    Args:
        vendor_client: Client connected to the Vendor container.
        finder_client: Client connected to the Finder container.
        vendor: Vendor ``as_Actor`` (the case owner adding the participant).
        finder: Finder ``as_Actor`` (the actor being added).
        case: The ``VulnerabilityCase`` to add the Finder to.

    Returns:
        The ``FinderReporterParticipant`` record created for the Finder.
    """
    finder_participant = FinderReporterParticipant(
        attributed_to=finder.id_,
        context=case.id_,
    )
    create_participant = CreateParticipantActivity(
        actor=vendor.id_,
        object_=finder_participant,
        context=case.id_,
    )
    add_participant = AddParticipantToCaseActivity(
        actor=vendor.id_,
        object_=finder_participant.id_,
        target=case.id_,
    )

    with demo_step("Vendor creates Finder's participant record"):
        post_to_inbox_and_wait(vendor_client, vendor.id_, create_participant)
    with demo_check("Finder participant stored in Vendor's DataLayer"):
        verify_object_stored(vendor_client, finder_participant.id_)

    with demo_step("Vendor adds Finder as a case participant"):
        post_to_inbox_and_wait(vendor_client, vendor.id_, add_participant)

    if vendor_client.base_url != finder_client.base_url:
        with demo_step(
            "Vendor notifies Finder that they were added to the case"
        ):
            post_to_inbox_and_wait(finder_client, finder.id_, add_participant)
        with demo_check(
            "Add-participant notification stored in Finder's DataLayer"
        ):
            verify_object_stored(finder_client, add_participant.id_)

    logger.info(
        "Finder added as case participant: %s", ref_id(finder_participant)
    )
    return finder_participant


def finder_asks_question(
    vendor_client: DataLayerClient,
    vendor: as_Actor,
    finder: as_Actor,
    case: VulnerabilityCase,
) -> as_Note:
    """Finder posts a question note to the case via the Vendor's inbox.

    The note is addressed to the case (not directly to the Vendor actor).
    The Vendor container processes it and adds it to the case.

    Args:
        vendor_client: Client connected to the Vendor container.
        vendor: Vendor ``as_Actor`` (the case host).
        finder: Finder ``as_Actor`` (posting the question).
        case: The ``VulnerabilityCase`` the note belongs to.

    Returns:
        The ``as_Note`` question note.
    """
    question_note = as_Note(
        name="Question from Finder",
        content=(
            "Is there a workaround available while waiting for the patch? "
            "Our security team needs to provide interim guidance to users."
        ),
        context=case.id_,
        attributed_to=finder.id_,
    )
    create_note = as_Create(
        actor=finder.id_,
        object_=question_note,
    )
    add_note = AddNoteToCaseActivity(
        actor=finder.id_,
        object_=question_note,
        target=case.id_,
    )

    with demo_step("Finder posts a question note to the case"):
        post_to_inbox_and_wait(vendor_client, vendor.id_, create_note)
        post_to_inbox_and_wait(vendor_client, vendor.id_, add_note)
    with demo_check("Question note stored in Vendor's DataLayer"):
        verify_object_stored(vendor_client, question_note.id_)

    logger.info("Question note posted to case: %s", ref_id(question_note))
    return question_note


def vendor_replies_to_question(
    vendor_client: DataLayerClient,
    finder_client: DataLayerClient,
    vendor: as_Actor,
    finder: as_Actor,
    case: VulnerabilityCase,
    question_note: as_Note,
) -> as_Note:
    """Vendor posts a reply note to the case and the case forwards it to the Finder.

    The Vendor adds the reply to the case, then (acting as the case host)
    sends the reply to the Finder's inbox, simulating the case relaying the
    note to all participants.

    Args:
        vendor_client: Client connected to the Vendor container.
        finder_client: Client connected to the Finder container.
        vendor: Vendor ``as_Actor``.
        finder: Finder ``as_Actor`` (the reply recipient).
        case: The ``VulnerabilityCase`` the note belongs to.
        question_note: The original question note being replied to.

    Returns:
        The ``as_Note`` reply note.
    """
    reply_note = as_Note(
        name="Vendor Response",
        content=(
            "Yes, disabling the affected network stack component is an effective "
            "workaround. A patched version is expected within 30 days. "
            "We will notify all case participants when it is available."
        ),
        context=case.id_,
        attributed_to=vendor.id_,
        in_reply_to=question_note.id_,
    )
    create_reply = as_Create(
        actor=vendor.id_,
        object_=reply_note,
    )
    add_reply = AddNoteToCaseActivity(
        actor=vendor.id_,
        object_=reply_note,
        target=case.id_,
    )

    with demo_step("Vendor posts a reply note to the case"):
        post_to_inbox_and_wait(vendor_client, vendor.id_, create_reply)
        post_to_inbox_and_wait(vendor_client, vendor.id_, add_reply)
    with demo_check("Reply note stored in Vendor's DataLayer"):
        verify_object_stored(vendor_client, reply_note.id_)

    if vendor_client.base_url != finder_client.base_url:
        with demo_step("Case forwards Vendor's reply note to Finder"):
            post_to_inbox_and_wait(finder_client, finder.id_, create_reply)
        with demo_check("Reply note stored in Finder's DataLayer"):
            verify_object_stored(finder_client, reply_note.id_)

    logger.info("Reply note posted to case: %s", ref_id(reply_note))
    return reply_note


def find_case_for_offer(
    vendor_client: DataLayerClient,
    offer_id: str,
) -> Optional[VulnerabilityCase]:
    """Find the VulnerabilityCase associated with a report offer in the Vendor container.

    Args:
        vendor_client: Client connected to the Vendor container.
        offer_id: Full URI of the ``RmSubmitReportActivity`` offer.

    Returns:
        The matching ``VulnerabilityCase``, or ``None`` if not found.
    """
    offer_data = vendor_client.get(f"/datalayer/{offer_id}")
    if not offer_data:
        return None

    offer_object = offer_data.get("object")
    report_id: str | None
    if isinstance(offer_object, str):
        report_id = offer_object
    elif isinstance(offer_object, dict):
        report_id = offer_object.get("id")
    else:
        report_id = ref_id(offer_object)

    if not report_id:
        logger.warning("Offer %s does not reference a report object", offer_id)
        return None

    cases_data = vendor_client.get("/datalayer/VulnerabilityCases/")
    if not cases_data:
        return None
    for item in cases_data:
        if isinstance(item, str):
            try:
                data = vendor_client.get(f"/datalayer/{item}")
                case = VulnerabilityCase(**data)
            except Exception as exc:
                logger.warning("Could not fetch case %s: %s", item, exc)
                continue
        else:
            case = VulnerabilityCase(**item)

        report_ids = [
            r if isinstance(r, str) else getattr(r, "id_", str(r))
            for r in (case.vulnerability_reports or [])
        ]
        if report_id in report_ids:
            return case
    return None


def verify_vendor_case_state(
    vendor_client: DataLayerClient,
    case_id: str,
    report_id: str,
    vendor_actor_id: str,
    finder_actor_id: str,
    question_note_id: str | None = None,
    reply_note_id: str | None = None,
) -> VulnerabilityCase:
    """Assert the final authoritative case state stored on the Vendor container."""
    final_case_data = vendor_client.get(f"/datalayer/{case_id}")
    final_case = VulnerabilityCase(**final_case_data)

    participant_count = len(final_case.case_participants)
    if participant_count != 2:
        raise AssertionError(
            f"Expected 2 case participants, found {participant_count}"
        )

    report_ids = [
        ref_id(report) or str(report)
        for report in final_case.vulnerability_reports
    ]
    if report_id not in report_ids:
        raise AssertionError(
            "Final case does not reference the submitted report"
        )

    vendor_participant_id = final_case.actor_participant_index.get(
        vendor_actor_id
    )
    if vendor_participant_id is None:
        raise AssertionError(
            "Vendor actor is missing from actor_participant_index"
        )

    finder_participant_id = final_case.actor_participant_index.get(
        finder_actor_id
    )
    if finder_participant_id is None:
        raise AssertionError(
            "Finder actor is missing from actor_participant_index"
        )

    vendor_participant_data = vendor_client.get(
        f"/datalayer/{vendor_participant_id}"
    )
    vendor_participant = CaseParticipant(**vendor_participant_data)
    if not vendor_participant.participant_statuses:
        raise AssertionError("Vendor participant has no participant statuses")
    if vendor_participant.participant_statuses[-1].rm_state != RM.ACCEPTED:
        raise AssertionError(
            "Vendor participant RM state did not transition to ACCEPTED"
        )

    event_types = [event.event_type for event in final_case.events]
    if "participant_added" not in event_types:
        raise AssertionError(
            "Expected participant_added event after Finder was added to the case"
        )

    current_status = final_case.current_status
    if current_status.em_state != EM.NO_EMBARGO:
        raise AssertionError(
            f"Expected NO_EMBARGO final EM state, found {current_status.em_state}"
        )
    if current_status.pxa_state != CS_pxa.pxa:
        raise AssertionError(
            f"Expected pxa final case state, found {current_status.pxa_state}"
        )

    if question_note_id is not None or reply_note_id is not None:
        note_ids = [ref_id(n) or str(n) for n in final_case.notes]
        if question_note_id is not None and question_note_id not in note_ids:
            raise AssertionError(
                f"Question note {question_note_id!r} not found in case notes"
            )
        if reply_note_id is not None and reply_note_id not in note_ids:
            raise AssertionError(
                f"Reply note {reply_note_id!r} not found in case notes"
            )

    return final_case


def verify_case_actor_unused(
    case_actor_client: DataLayerClient | None,
    case_id: str,
) -> None:
    """Verify the dedicated CaseActor container remains unused in D5-2.

    Per D5-1-G3, the per-case `VultronCaseActor` co-locates in the Vendor
    container for D5-2. The standalone `case-actor` service participates in
    the Docker topology but should not hold the created `VulnerabilityCase`.
    """
    if case_actor_client is None:
        return

    case_actor_cases = case_actor_client.get("/datalayer/VulnerabilityCases/")
    if case_id in case_actor_cases:
        raise AssertionError(
            "Dedicated case-actor container unexpectedly persisted the D5-2 case"
        )


def wait_for_case_participants(
    vendor_client: DataLayerClient,
    case_id: str,
    expected_count: int,
    timeout_seconds: float = 5.0,
    poll_interval: float = 0.25,
) -> None:
    """Poll until the Vendor's case reflects the expected participant count."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        case_data = vendor_client.get(f"/datalayer/{case_id}")
        case = VulnerabilityCase(**case_data)
        if len(case.case_participants) >= expected_count:
            return
        time.sleep(poll_interval)

    final_case = VulnerabilityCase(
        **vendor_client.get(f"/datalayer/{case_id}")
    )
    raise AssertionError(
        "Timed out waiting for participant count "
        f"{expected_count}; found {len(final_case.case_participants)}"
    )


# ---------------------------------------------------------------------------
# Main workflow orchestration
# ---------------------------------------------------------------------------


def run_two_actor_demo(
    finder_client: DataLayerClient,
    vendor_client: DataLayerClient,
    case_actor_client: DataLayerClient | None = None,
    finder_id: str | None = None,
    vendor_id: str | None = None,
) -> None:
    """Orchestrate the complete two-actor (Finder + Vendor) CVD workflow.

    1. Reset all participating containers to a clean baseline.
    2. Seed both actor containers.
    3. Finder submits report → Vendor's inbox.
    4. Vendor validates report and engages case.
    5. Vendor directly adds Finder as a case participant (no invite/accept).
    6. Finder posts a question note to the case; Vendor replies and the
       case forwards the reply to the Finder.
    7. Verify final state on the Vendor container and optional CaseActor
       isolation for the D5-2 topology.

    Args:
        finder_client: Client connected to the Finder container.
        vendor_client: Client connected to the Vendor container.
        case_actor_client: Optional client connected to a dedicated CaseActor
            container.  When provided, the demo verifies it remains unused
            (per D5-2: CaseActor co-locates in Vendor).
        finder_id: Optional deterministic URI for the Finder actor.
        vendor_id: Optional deterministic URI for the Vendor actor.
    """
    logger.info("=" * 80)
    logger.info("TWO-ACTOR DEMO: Finder + Vendor CVD Workflow (D5-1-G5)")
    logger.info("=" * 80)
    logger.info("Finder container: %s", finder_client.base_url)
    logger.info("Vendor container: %s", vendor_client.base_url)
    if case_actor_client is not None:
        logger.info("CaseActor container: %s", case_actor_client.base_url)

    # ── Step 0: Reset containers ───────────────────────────────────────────
    reset_containers(
        finder_client=finder_client,
        vendor_client=vendor_client,
        case_actor_client=case_actor_client,
    )

    # ── Step 1: Seed containers ───────────────────────────────────────────
    with demo_step("Seeding both containers with actor records"):
        finder, vendor = seed_containers(
            finder_client=finder_client,
            vendor_client=vendor_client,
            finder_actor_id=finder_id,
            vendor_actor_id=vendor_id,
        )

    # Fetch vendor as seen from the vendor container (same actor, same ID).
    vendor_in_vendor = get_actor_by_id(vendor_client, vendor.id_)

    # ── Step 2: Finder submits report ─────────────────────────────────────
    report, offer = finder_submits_report(
        vendor_client=vendor_client,
        finder=finder,
        vendor=vendor_in_vendor,
    )

    # ── Step 3: Vendor validates and engages ──────────────────────────────
    vendor_validates_report(
        vendor_client=vendor_client,
        vendor=vendor_in_vendor,
        offer_id=offer.id_,
    )

    with demo_check("VulnerabilityCase exists in Vendor's DataLayer"):
        case = find_case_for_offer(vendor_client, offer.id_)
        if case is None:
            raise AssertionError(
                "Expected VulnerabilityCase to be created after validate-report"
            )
        logger.info("Case created: %s", case.id_)

    vendor_engages_case(
        vendor_client=vendor_client,
        vendor=vendor_in_vendor,
        case_id=case.id_,
    )

    # ── Step 4: Vendor directly adds Finder as a participant ──────────────
    # Refresh case to get up-to-date state.
    case_data = vendor_client.get(f"/datalayer/{case.id_}")
    case = VulnerabilityCase(**case_data)

    # Finder actor as known by the vendor container.
    finder_in_vendor = get_actor_by_id(vendor_client, finder.id_)

    vendor_adds_finder_as_participant(
        vendor_client=vendor_client,
        finder_client=finder_client,
        vendor=vendor_in_vendor,
        finder=finder_in_vendor,
        case=case,
    )

    wait_for_case_participants(
        vendor_client=vendor_client,
        case_id=case.id_,
        expected_count=2,
    )

    # Refresh case after participant addition.
    case_data = vendor_client.get(f"/datalayer/{case.id_}")
    case = VulnerabilityCase(**case_data)

    # ── Step 5: Notes exchange ────────────────────────────────────────────
    # Finder actor from the Finder container.
    finder_in_finder = get_actor_by_id(finder_client, finder.id_)
    # Vendor as known by the Finder container.
    vendor_in_finder = get_actor_by_id(finder_client, vendor.id_)

    question_note = finder_asks_question(
        vendor_client=vendor_client,
        vendor=vendor_in_vendor,
        finder=finder_in_finder,
        case=case,
    )

    reply_note = vendor_replies_to_question(
        vendor_client=vendor_client,
        finder_client=finder_client,
        vendor=vendor_in_vendor,
        finder=vendor_in_finder,
        case=case,
        question_note=question_note,
    )

    # ── Step 6: Verify final state ────────────────────────────────────────
    with demo_check(
        "Vendor container holds the authoritative final case state"
    ):
        final_case = verify_vendor_case_state(
            vendor_client=vendor_client,
            case_id=case.id_,
            report_id=report.id_,
            vendor_actor_id=vendor.id_,
            finder_actor_id=finder.id_,
            question_note_id=question_note.id_,
            reply_note_id=reply_note.id_,
        )
        logger.info("Final case state (Vendor): %s", logfmt(final_case))

    with demo_check("Dedicated CaseActor container remains unused for D5-2"):
        verify_case_actor_unused(case_actor_client, case.id_)

    logger.info("=" * 80)
    logger.info("TWO-ACTOR DEMO COMPLETE ✓")
    logger.info("=" * 80)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(
    skip_health_check: bool = False,
    finder_url: str | None = None,
    vendor_url: str | None = None,
    case_actor_url: str | None = None,
    finder_id: str | None = None,
    vendor_id: str | None = None,
) -> None:
    """Entry point for the two-actor multi-container CVD workflow demo.

    Args:
        skip_health_check: Skip the server availability check (useful for
            testing).
        finder_url: Override base URL for the Finder container.
        vendor_url: Override base URL for the Vendor container.
        case_actor_url: Optional base URL for the dedicated CaseActor container.
        finder_id: Optional deterministic URI for the Finder actor.
        vendor_id: Optional deterministic URI for the Vendor actor.
    """
    f_url = finder_url or FINDER_BASE_URL
    v_url = vendor_url or VENDOR_BASE_URL
    c_url = case_actor_url or CASE_ACTOR_BASE_URL

    finder_client = DataLayerClient(base_url=f_url)
    vendor_client = DataLayerClient(base_url=v_url)
    case_actor_client = DataLayerClient(base_url=c_url) if c_url else None

    if not skip_health_check:
        targets: list[tuple[str, DataLayerClient]] = [
            ("Finder", finder_client),
            ("Vendor", vendor_client),
        ]
        if case_actor_client is not None:
            targets.append(("CaseActor", case_actor_client))
        for label, client in targets:
            if not check_server_availability(client):
                logger.error("=" * 80)
                logger.error("ERROR: %s API server is not available", label)
                logger.error("=" * 80)
                logger.error("Cannot connect to: %s", client.base_url)
                logger.error(
                    "Ensure the %s container is running and healthy.", label
                )
                logger.error("=" * 80)
                sys.exit(1)

    try:
        run_two_actor_demo(
            finder_client=finder_client,
            vendor_client=vendor_client,
            case_actor_client=case_actor_client,
            finder_id=finder_id,
            vendor_id=vendor_id,
        )
    except Exception as exc:
        logger.error("Two-actor demo failed: %s", exc, exc_info=True)
        logger.error("=" * 80)
        logger.error("ERROR SUMMARY")
        logger.error("=" * 80)
        logger.error("%s", exc)
        logger.error("=" * 80)
        sys.exit(1)


def _setup_logging() -> None:
    """Configure console logging for standalone script execution."""
    logging.getLogger("requests").setLevel(logging.WARNING)
    _logger = logging.getLogger()
    hdlr = logging.StreamHandler(sys.stdout)
    hdlr.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    )
    _logger.addHandler(hdlr)
    _logger.setLevel(logging.DEBUG)


if __name__ == "__main__":
    _setup_logging()
    main()
