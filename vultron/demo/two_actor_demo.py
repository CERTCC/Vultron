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
5. **Engage**: Validation automatically cascades to engage the case
   (RM.VALID → RM.ACCEPTED) without a separate trigger call
   (D5-7-AUTOENG-2).
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
from vultron.wire.as2.vocab.activities.report import (
    RmSubmitReportActivity,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.case_participant import (
    CaseParticipant,
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
    finder_client: Optional[DataLayerClient] = None,
) -> Tuple[VulnerabilityReport, RmSubmitReportActivity]:
    """Finder creates a vulnerability report and submits it to the Vendor's inbox.

    When ``finder_client`` is provided (e.g. in a multi-container Docker demo),
    the report and offer are created via the Finder container's
    ``submit-report`` trigger endpoint so that Finder container logs tell the
    full process-flow story (D5-6a).  The resulting offer is then delivered to
    the Vendor container's inbox.

    When ``finder_client`` is ``None`` (e.g. single-container integration
    tests), the report and offer are constructed in memory and posted directly
    to the Vendor container (backward-compatible path).

    Args:
        vendor_client: Client connected to the Vendor container.
        finder: Finder ``as_Actor``.
        vendor: Vendor ``as_Actor``.
        finder_client: Optional client connected to the Finder container.
            When provided, the submit-report trigger is called on the Finder
            container; when absent the legacy in-memory path is used.

    Returns:
        Tuple of ``(report, offer)``.
    """
    if finder_client is not None:
        report_name = "Remote Code Execution in Network Stack"
        report_content = (
            "A critical remote code execution vulnerability was discovered "
            "in the network stack component. An attacker can exploit this "
            "issue to execute arbitrary code with elevated privileges."
        )
        with demo_step(
            "Finder submits vulnerability report to Vendor's inbox"
        ):
            result = post_to_trigger(
                client=finder_client,
                actor_id=finder.id_,
                behavior="submit-report",
                body={
                    "report_name": report_name,
                    "report_content": report_content,
                    "recipient_id": vendor.id_,
                },
            )
        offer_dict = result.get("offer", {})
        offer = RmSubmitReportActivity.model_validate(offer_dict)
        report_raw = offer.object_
        if isinstance(report_raw, str):
            report = VulnerabilityReport(
                id_=report_raw,
                name=report_name,
                content=report_content,
            )
        elif isinstance(report_raw, VulnerabilityReport):
            report = report_raw
        else:
            # as_Link or None — fall back to a minimal VulnerabilityReport
            # using the data we know (the trigger always embeds the full object).
            report = VulnerabilityReport(
                name=report_name,
                content=report_content,
            )
        # Deliver the offer from the Finder to the Vendor's inbox.
        # Per ADR-0012 (per-actor DataLayer isolation) the trigger stores the
        # offer only in the Finder's namespace; the Vendor must receive it
        # explicitly via inbox delivery so SubmitReportReceivedUseCase runs and
        # creates the case at RM.RECEIVED (ADR-0015).
        with demo_step("Deliver Finder's offer to Vendor's inbox"):
            post_to_inbox_and_wait(vendor_client, vendor.id_, offer)
    else:
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
            target=vendor.id_,
            to=[vendor.id_],
        )
        with demo_step(
            "Finder submits vulnerability report to Vendor's inbox"
        ):
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


def wait_for_note_in_case(
    client: DataLayerClient,
    case_id: str,
    note_id: str,
    timeout_seconds: float = 10.0,
    poll_interval: float = 0.5,
) -> None:
    """Poll until *note_id* appears in the ``notes`` list of the case.

    Used to confirm that an outbox-delivered note has been processed by
    the receiving actor's inbox handler.

    Args:
        client: DataLayerClient for the container to poll.
        case_id: Full URI of the case.
        note_id: Full URI of the note to wait for.
        timeout_seconds: Maximum time to wait before raising.
        poll_interval: Seconds between DataLayer poll attempts.

    Raises:
        AssertionError: If *note_id* does not appear within *timeout_seconds*.
    """
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            case_data = client.get(f"/datalayer/{case_id}")
            case = VulnerabilityCase(**case_data)
            note_ids = [
                n if isinstance(n, str) else getattr(n, "id_", str(n))
                for n in case.notes
            ]
            if note_id in note_ids:
                return
        except Exception:  # noqa: BLE001
            pass
        time.sleep(poll_interval)

    raise AssertionError(
        f"Timed out waiting for note {note_id!r} to appear in case "
        f"{case_id!r}"
    )


def finder_asks_question(
    vendor_client: DataLayerClient,
    finder_client: DataLayerClient,
    vendor: as_Actor,
    finder: as_Actor,
    case: VulnerabilityCase,
) -> as_Note:
    """Finder posts a question note to the case via the trigger endpoint.

    Uses the finder's ``add-note-to-case`` trigger so the note flows through
    the finder's outbox to the vendor's inbox — reflecting real deployment
    behavior (D5-7-DEMONOTECLEAN-1).

    Args:
        vendor_client: Client connected to the Vendor container.
        finder_client: Client connected to the Finder container.
        vendor: Vendor ``as_Actor`` (the case host / case actor).
        finder: Finder ``as_Actor`` (posting the question).
        case: The ``VulnerabilityCase`` the note belongs to.

    Returns:
        The ``as_Note`` question note fetched from the Vendor's DataLayer.
    """
    note_name = "Question from Finder"
    note_content = (
        "Is there a workaround available while waiting for the patch? "
        "Our security team needs to provide interim guidance to users."
    )

    with demo_step("Finder posts a question note to the case"):
        result = post_to_trigger(
            client=finder_client,
            actor_id=finder.id_,
            behavior="add-note-to-case",
            body={
                "case_id": case.id_,
                "note_name": note_name,
                "note_content": note_content,
            },
        )

    note_id = result.get("note", {}).get("id")
    if note_id is None:
        raise AssertionError(
            "add-note-to-case trigger did not return a note ID"
        )

    with demo_check("Question note delivered to Vendor's DataLayer"):
        wait_for_note_in_case(vendor_client, case.id_, note_id)
        verify_object_stored(vendor_client, note_id)

    logger.info("Question note posted to case: %s", note_id)

    note_data = vendor_client.get(f"/datalayer/{note_id}")
    return as_Note(**note_data)


def vendor_replies_to_question(
    vendor_client: DataLayerClient,
    finder_client: DataLayerClient,
    vendor: as_Actor,
    finder: as_Actor,
    case: VulnerabilityCase,
    question_note: as_Note,
) -> as_Note:
    """Vendor posts a reply note to the case via the trigger endpoint.

    Uses the vendor's ``add-note-to-case`` trigger so the note flows through
    the vendor's outbox — reflecting real deployment behavior
    (D5-7-DEMONOTECLEAN-1).  The case host (CaseActor) then automatically
    broadcasts the note to all participants via the note broadcast mechanism
    (CM-06-005).

    Args:
        vendor_client: Client connected to the Vendor container.
        finder_client: Client connected to the Finder container.
        vendor: Vendor ``as_Actor``.
        finder: Finder ``as_Actor`` (the reply recipient).
        case: The ``VulnerabilityCase`` the note belongs to.
        question_note: The original question note being replied to.

    Returns:
        The ``as_Note`` reply note fetched from the Vendor's DataLayer.
    """
    note_name = "Vendor Response"
    note_content = (
        "Yes, disabling the affected network stack component is an effective "
        "workaround. A patched version is expected within 30 days. "
        "We will notify all case participants when it is available."
    )

    with demo_step("Vendor posts a reply note to the case"):
        result = post_to_trigger(
            client=vendor_client,
            actor_id=vendor.id_,
            behavior="add-note-to-case",
            body={
                "case_id": case.id_,
                "note_name": note_name,
                "note_content": note_content,
                "in_reply_to": question_note.id_,
            },
        )

    note_id = result.get("note", {}).get("id")
    if note_id is None:
        raise AssertionError(
            "add-note-to-case trigger did not return a note ID"
        )

    with demo_check("Reply note stored in Vendor's DataLayer"):
        verify_object_stored(vendor_client, note_id)

    logger.info("Reply note posted to case: %s", note_id)

    note_data = vendor_client.get(f"/datalayer/{note_id}")
    return as_Note(**note_data)


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
    if current_status.em_state != EM.PROPOSED:
        raise AssertionError(
            f"Expected PROPOSED final EM state (default embargo initialized but"
            f" not yet negotiated), found {current_status.em_state}"
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


def wait_for_finder_case(
    finder_client: DataLayerClient,
    case_id: str,
    timeout_seconds: float = 10.0,
    poll_interval: float = 0.5,
) -> None:
    """Poll finder's DataLayer until *case_id* appears.

    This proves that the Vendor's outbox successfully delivered the
    ``Create(VulnerabilityCase)`` notification to the Finder and that the
    Finder's inbox handler processed it (D5-6-DEMOAUDIT requirement).

    In single-server integration tests both actors share the same DataLayer,
    so the case is visible immediately.  In a multi-server Docker demo the
    case arrives after the outbox background task completes and the Finder
    inbox handler processes the inbound activity.

    Args:
        finder_client: Client connected to the Finder container.
        case_id: Full URI of the ``VulnerabilityCase`` to wait for.
        timeout_seconds: Maximum time to wait before raising.
        poll_interval: Seconds between DataLayer poll attempts.

    Raises:
        AssertionError: If *case_id* does not appear within *timeout_seconds*.
    """
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        raw = finder_client.get("/datalayer/VulnerabilityCases/")
        # The endpoint returns a dict keyed by case ID (from by_type()).
        if isinstance(raw, dict) and case_id in raw:
            return
        time.sleep(poll_interval)

    raise AssertionError(
        f"Timed out waiting for case {case_id!r} to appear in "
        "finder's DataLayer — outbox delivery may not have completed"
    )


# ---------------------------------------------------------------------------
# SYNC-2 log replication helpers
# ---------------------------------------------------------------------------


def trigger_log_commit(
    client: DataLayerClient,
    actor_id: str,
    case_id: str,
    event_type: str,
    object_id: str | None = None,
) -> str:
    """Commit a log entry for *case_id* and return the entry hash.

    POSTs to ``/actors/{actor_id}/trigger/sync-log-entry`` and returns
    the ``entry_hash`` from the response.  The entry is also fanned out
    to all case participants via ``Announce(CaseLogEntry)`` activities
    queued in the actor's outbox.

    Args:
        client: DataLayerClient connected to the CaseActor container.
        actor_id: Full URI of the actor committing the log entry.
        case_id: Full URI of the ``VulnerabilityCase``.
        event_type: Short machine-readable event descriptor.
        object_id: Optional URI of the primary object.  Defaults to
            *case_id* when not supplied.

    Returns:
        The ``entry_hash`` of the newly committed log entry.

    Spec: SYNC-02-002, SYNC-02-003.
    """
    result = post_to_trigger(
        client=client,
        actor_id=actor_id,
        behavior="sync-log-entry",
        body={
            "case_id": case_id,
            "object_id": object_id if object_id is not None else case_id,
            "event_type": event_type,
        },
    )
    entry_hash: str = result["entry_hash"]
    logger.info(
        "Log entry committed for case '%s': hash=%s, index=%d",
        case_id,
        entry_hash[:16],
        result.get("log_index", -1),
    )
    return entry_hash


def wait_for_finder_log_entry(
    finder_client: DataLayerClient,
    case_id: str,
    entry_hash: str,
    timeout_seconds: float = 15.0,
    poll_interval: float = 0.5,
) -> None:
    """Poll finder's DataLayer until a ``CaseLogEntry`` with *entry_hash* appears.

    Proves that the vendor's ``Announce(CaseLogEntry)`` outbox activity was
    delivered to the finder's inbox and processed by
    ``AnnounceLogEntryReceivedUseCase`` (SYNC-2 receive side).

    Args:
        finder_client: Client connected to the Finder container.
        case_id: Full URI of the ``VulnerabilityCase`` (used for filtering).
        entry_hash: ``entry_hash`` value of the expected log entry.
        timeout_seconds: Maximum time to wait before raising.
        poll_interval: Seconds between DataLayer poll attempts.

    Raises:
        AssertionError: If the entry does not appear within *timeout_seconds*.

    Spec: SYNC-02-002.
    """
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        raw = finder_client.get("/datalayer/CaseLogEntrys/")
        if isinstance(raw, dict):
            for v in raw.values():
                if (
                    isinstance(v, dict)
                    and v.get("case_id") == case_id
                    and v.get("entry_hash") == entry_hash
                ):
                    logger.info(
                        "Log entry with hash=%s found in finder's DataLayer",
                        entry_hash[:16],
                    )
                    return
        time.sleep(poll_interval)

    raise AssertionError(
        f"Timed out waiting for log entry (hash={entry_hash!r}) for case "
        f"{case_id!r} to appear in finder's DataLayer — replication may "
        "not have completed"
    )


def _extract_ref_id(ref: object) -> Optional[str]:
    """Extract the string ID from an object, ``as_Link``, or string reference."""
    if ref is None:
        return None
    if isinstance(ref, str):
        return ref
    if hasattr(ref, "id_"):
        return str(ref.id_)  # type: ignore[union-attr]
    if hasattr(ref, "href"):
        return str(ref.href)  # type: ignore[union-attr]
    return str(ref)


def _get_log_entries_for_case(
    client: DataLayerClient, case_id: str
) -> list[dict]:
    """Return all ``CaseLogEntry`` dicts for *case_id* from the DataLayer."""
    raw = client.get("/datalayer/CaseLogEntrys/")
    if not isinstance(raw, dict):
        return []
    return [
        v
        for v in raw.values()
        if isinstance(v, dict) and v.get("case_id") == case_id
    ]


def verify_finder_replica_state(
    finder_client: DataLayerClient,
    vendor_client: DataLayerClient,
    case_id: str,
    vendor_actor_id: str,
    finder_actor_id: str,
) -> None:
    """Verify that the finder's case replica matches the authoritative vendor state.

    Checks four properties:

    1. The same ``case_id`` exists in the finder's DataLayer.
    2. ``actor_participant_index`` keys are identical (same participant set).
    3. ``active_embargo`` references the same ID on both sides.
    4. Log-state hash consistency: both sides share the same tail entry hash.

    Args:
        finder_client: Client connected to the Finder container.
        vendor_client: Client connected to the Vendor container.
        case_id: Full URI of the ``VulnerabilityCase`` being verified.
        vendor_actor_id: Full URI of the Vendor actor (unused directly but
            retained for symmetry with *finder_actor_id*).
        finder_actor_id: Full URI of the Finder actor (unused directly but
            retained for future participant-status checks).

    Raises:
        AssertionError: If any replica invariant is violated.

    Spec: SYNC-02-002, D5-7-DEMOREPLCHECK-1.
    """
    vendor_case_data = vendor_client.get(f"/datalayer/{case_id}")
    assert vendor_case_data, f"Vendor case {case_id!r} not found"
    vendor_case = VulnerabilityCase.model_validate(vendor_case_data)

    finder_case_data = finder_client.get(f"/datalayer/{case_id}")
    assert finder_case_data, (
        f"Finder does not have a copy of case {case_id!r} — "
        "outbox delivery or inbox processing may have failed"
    )
    finder_case = VulnerabilityCase.model_validate(finder_case_data)

    # 1. Same case ID
    assert (
        finder_case.id_ == case_id
    ), f"Finder case ID mismatch: {finder_case.id_!r} != {case_id!r}"
    logger.info("✓ Finder case ID matches: %s", case_id)

    # 2. actor_participant_index keys match
    vendor_index = vendor_case.actor_participant_index or {}
    finder_index = finder_case.actor_participant_index or {}
    assert set(vendor_index.keys()) == set(finder_index.keys()), (
        "Finder actor_participant_index key set differs from vendor: "
        f"finder={set(finder_index.keys())} "
        f"vendor={set(vendor_index.keys())}"
    )
    logger.info(
        "✓ Finder actor_participant_index matches (%d participants)",
        len(finder_index),
    )

    # 3. active_embargo ID matches (if present on vendor)
    vendor_embargo_id = _extract_ref_id(vendor_case.active_embargo)
    finder_embargo_id = _extract_ref_id(finder_case.active_embargo)
    if vendor_embargo_id is not None:
        assert vendor_embargo_id == finder_embargo_id, (
            f"Finder active_embargo {finder_embargo_id!r} != "
            f"vendor active_embargo {vendor_embargo_id!r}"
        )
        logger.info("✓ Finder active_embargo matches: %s", vendor_embargo_id)

    # 4. Log-state hash consistency
    vendor_entries = _get_log_entries_for_case(vendor_client, case_id)
    finder_entries = _get_log_entries_for_case(finder_client, case_id)
    assert len(finder_entries) > 0, (
        "Finder has no CaseLogEntry records for the case — "
        "SYNC-2 replication did not complete"
    )
    vendor_tail = max(vendor_entries, key=lambda e: e["log_index"])
    finder_tail = max(finder_entries, key=lambda e: e["log_index"])
    assert vendor_tail["entry_hash"] == finder_tail["entry_hash"], (
        f"Finder log tail hash {finder_tail['entry_hash']!r} != "
        f"vendor log tail hash {vendor_tail['entry_hash']!r} — "
        "hash-chain replication integrity failure"
    )
    logger.info(
        "✓ Finder log tail hash matches vendor: %s… (index=%d)",
        finder_tail["entry_hash"][:16],
        finder_tail["log_index"],
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
    4. Vendor validates report; the BT automatically creates the case,
       initializes the default embargo, and registers both the Vendor and
       Finder as case participants (vendor RM → ACCEPTED).
    5. Finder posts a question note to the case; Vendor replies and the
       case forwards the reply to the Finder.
    6. Verify final state on the Vendor container and optional CaseActor
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
        finder_client=finder_client,
    )

    # ── Step 3: Vendor validates report ──────────────────────────────────
    # Per ADR-0015, case creation and participant seeding now happen at
    # RM.RECEIVED (finder_submits_report above).  validate-report advances
    # the vendor's RM state from RECEIVED to VALID and then automatically
    # cascades to engage-case (VALID → ACCEPTED) per D5-7-AUTOENG-2.
    vendor_validates_report(
        vendor_client=vendor_client,
        vendor=vendor_in_vendor,
        offer_id=offer.id_,
    )

    # ── Step 3b: Confirm case exists (engage-case now auto-cascades) ──────
    with demo_check("VulnerabilityCase exists in Vendor's DataLayer"):
        case = find_case_for_offer(vendor_client, offer.id_)
        if case is None:
            raise AssertionError(
                "Expected VulnerabilityCase to be created after validate-report"
            )
        logger.info("Case created: %s", case.id_)

    wait_for_case_participants(
        vendor_client=vendor_client,
        case_id=case.id_,
        expected_count=2,
    )

    # Verify the Finder's container received the case via outbox delivery.
    # The validate-report trigger queues a Create(VulnerabilityCase) activity
    # to the Vendor's outbox; the outbox BackgroundTask delivers it to the
    # Finder's inbox, which then runs CreateCaseReceivedUseCase.
    with demo_check(
        "Finder's DataLayer received case via Vendor outbox delivery"
    ):
        wait_for_finder_case(
            finder_client=finder_client,
            case_id=case.id_,
        )
        logger.info(
            "Case %s confirmed in Finder's DataLayer (outbox delivery verified)",
            case.id_,
        )

    # Refresh case after BT completes.
    case_data = vendor_client.get(f"/datalayer/{case.id_}")
    case = VulnerabilityCase(**case_data)

    # ── Step 4: Notes exchange ────────────────────────────────────────────
    # Finder actor from the Finder container.
    finder_in_finder = get_actor_by_id(finder_client, finder.id_)

    question_note = finder_asks_question(
        vendor_client=vendor_client,
        finder_client=finder_client,
        vendor=vendor_in_vendor,
        finder=finder_in_finder,
        case=case,
    )

    reply_note = vendor_replies_to_question(
        vendor_client=vendor_client,
        finder_client=finder_client,
        vendor=vendor_in_vendor,
        finder=finder_in_finder,
        case=case,
        question_note=question_note,
    )

    # ── Step 5: Verify final state ────────────────────────────────────────
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

    # ── Step 6: Commit log entry + verify finder replica ──────────────────
    # Per SYNC-2, the CaseActor (co-located in the Vendor container for the
    # D5-2 topology) commits a log entry that fans out to the Finder via
    # Announce(CaseLogEntry).  We then poll the Finder for the entry and
    # compare replica state against the authoritative Vendor view.
    with demo_step("Committing case log entry on Vendor (CaseActor)"):
        entry_hash = trigger_log_commit(
            client=vendor_client,
            actor_id=vendor.id_,
            case_id=case.id_,
            event_type="demo_verification",
        )

    with demo_step("Waiting for Finder to receive replicated log entry"):
        wait_for_finder_log_entry(
            finder_client=finder_client,
            case_id=case.id_,
            entry_hash=entry_hash,
        )

    with demo_check("Finder replica state matches authoritative Vendor state"):
        verify_finder_replica_state(
            finder_client=finder_client,
            vendor_client=vendor_client,
            case_id=case.id_,
            vendor_actor_id=vendor.id_,
            finder_actor_id=finder.id_,
        )

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
