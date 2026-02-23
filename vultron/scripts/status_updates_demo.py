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
Demonstrates status updates and notes workflows via the Vultron API.

This demo script showcases the following workflows:

1. Notes workflow: vendor creates a note on a case → adds it to the case
2. Case status workflow: vendor creates a CaseStatus → adds it to the case
3. Participant status workflow: vendor creates a ParticipantStatus for a
   participant → adds it to that participant

Each demo starts from an initialized case with a single FinderReporter
participant so the status update workflows can be demonstrated in isolation.

This corresponds to the workflow documented in:
    docs/howto/activitypub/activities/status_updates.md

When run as a script, this module will:
1. Check if the API server is available
2. Reset the data layer to a clean state
3. Discover actors (finder, vendor, coordinator) via the API
4. Run all three demo workflows
5. Verify side effects in the data layer
"""

import logging
import sys
from typing import Optional, Sequence, Tuple

from vultron.as_vocab.activities.case import (
    AddNoteToCase,
    AddReportToCase,
    AddStatusToCase,
    CreateCase,
    CreateCaseStatus,
)
from vultron.as_vocab.activities.case_participant import (
    AddParticipantToCase,
    AddStatusToParticipant,
    CreateStatusForParticipant,
)
from vultron.as_vocab.activities.report import RmSubmitReport, RmValidateReport
from vultron.as_vocab.base.objects.activities.transitive import (
    as_Create,
    as_Remove,
)
from vultron.as_vocab.base.objects.actors import as_Actor
from vultron.as_vocab.base.objects.object_types import as_Note
from vultron.as_vocab.objects.case_participant import (
    CaseParticipant,
    FinderReporterParticipant,
)
from vultron.as_vocab.objects.case_status import CaseStatus, ParticipantStatus
from vultron.as_vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport
from vultron.bt.embargo_management.states import EM
from vultron.bt.report_management.states import RM
from vultron.case_states.states import CS_pxa, CS_vfd
from vultron.scripts.initialize_case_demo import (
    BASE_URL,
    DataLayerClient,
    check_server_availability,
    get_offer_from_datalayer,
    log_case_state,
    logfmt,
    post_to_inbox_and_wait,
    setup_clean_environment,
    verify_object_stored,
)

logger = logging.getLogger(__name__)


def _setup_initialized_case(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
) -> Tuple[VulnerabilityCase, CaseParticipant]:
    """
    Set up a case with one FinderReporter participant as a precondition
    for the status updates workflow.

    Steps:
    1. Finder submits report to vendor
    2. Vendor validates report
    3. Vendor creates case
    4. Vendor adds report to case
    5. Vendor creates FinderReporter participant
    6. Vendor adds participant to case
    """
    report = VulnerabilityReport(
        attributed_to=finder.as_id,
        content="A heap buffer overflow in the image parsing library.",
        name="Heap Buffer Overflow in Image Parser",
    )
    report_offer = RmSubmitReport(
        actor=finder.as_id,
        as_object=report,
        to=[vendor.as_id],
    )
    post_to_inbox_and_wait(client, vendor.as_id, report_offer)
    verify_object_stored(client, report.as_id)

    offer = get_offer_from_datalayer(client, vendor.as_id, report_offer.as_id)
    validate_activity = RmValidateReport(
        actor=vendor.as_id,
        object=offer.as_id,
        content="Confirmed — heap buffer overflow via malformed image input.",
    )
    post_to_inbox_and_wait(client, vendor.as_id, validate_activity)

    case = VulnerabilityCase(
        attributed_to=vendor.as_id,
        name="Heap Overflow Case — Image Parser",
        content="Tracking the heap buffer overflow in the image parsing library.",
    )
    create_case_activity = CreateCase(
        actor=vendor.as_id,
        as_object=case,
    )
    post_to_inbox_and_wait(client, vendor.as_id, create_case_activity)
    verify_object_stored(client, case.as_id)

    add_report_activity = AddReportToCase(
        actor=vendor.as_id,
        as_object=report.as_id,
        target=case.as_id,
    )
    post_to_inbox_and_wait(client, vendor.as_id, add_report_activity)

    participant = FinderReporterParticipant(
        attributed_to=finder.as_id,
        context=case.as_id,
    )
    create_participant_activity = as_Create(
        actor=vendor.as_id,
        as_object=participant,
        context=case.as_id,
    )
    post_to_inbox_and_wait(client, vendor.as_id, create_participant_activity)
    verify_object_stored(client, participant.as_id)

    add_participant_activity = AddParticipantToCase(
        actor=vendor.as_id,
        as_object=participant.as_id,
        target=case.as_id,
    )
    post_to_inbox_and_wait(client, vendor.as_id, add_participant_activity)

    log_case_state(client, case.as_id, "after setup")
    logger.info("✓ Setup: Case initialized with one participant")
    return case, participant


def demo_notes_workflow(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    coordinator: as_Actor,
) -> None:
    """
    Demonstrate the notes workflow:
    1. Create a note
    2. Add the note to a case
    3. Verify the case has the note
    4. Remove the note from the case
    5. Verify the case no longer has the note
    """
    logger.info("=" * 80)
    logger.info("DEMO: Notes Workflow")
    logger.info("=" * 80)

    case, participant = _setup_initialized_case(client, finder, vendor)

    # Step 1: Create a note
    note = as_Note(
        name="Initial Triage Note",
        content=(
            "Reviewed the report. The heap buffer overflow is confirmed "
            "and affects all versions prior to 3.2.1."
        ),
        context=case.as_id,
        attributed_to=vendor.as_id,
    )
    create_note_activity = as_Create(
        actor=vendor.as_id,
        as_object=note,
    )
    post_to_inbox_and_wait(client, vendor.as_id, create_note_activity)
    verify_object_stored(client, note.as_id)
    logger.info("✓ Step 1: Note created")

    # Step 2: Add the note to the case
    add_note_activity = AddNoteToCase(
        actor=vendor.as_id,
        object=note,
        target=case.as_id,
    )
    post_to_inbox_and_wait(client, vendor.as_id, add_note_activity)

    updated_case = log_case_state(client, case.as_id, "after AddNoteToCase")
    if updated_case:
        note_ids = [
            (n.as_id if hasattr(n, "as_id") else n) for n in updated_case.notes
        ]
        if note.as_id not in note_ids:
            raise ValueError(
                f"Note '{note.as_id}' not found in case after AddNoteToCase"
            )
    logger.info("✓ Step 2: Note added to case")

    # Step 3: Remove the note from the case
    remove_note_activity = as_Remove(
        actor=vendor.as_id,
        as_object=note,
        target=case.as_id,
    )
    post_to_inbox_and_wait(client, vendor.as_id, remove_note_activity)

    updated_case = log_case_state(
        client, case.as_id, "after RemoveNoteFromCase"
    )
    if updated_case:
        note_ids = [
            (n.as_id if hasattr(n, "as_id") else n) for n in updated_case.notes
        ]
        if note.as_id in note_ids:
            raise ValueError(
                f"Note '{note.as_id}' still in case after RemoveNoteFromCase"
            )
    logger.info("✓ Step 3: Note removed from case")

    logger.info("✅ DEMO COMPLETE: Notes workflow finished.")


def demo_status_workflow(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    coordinator: as_Actor,
) -> None:
    """
    Demonstrate the status updates workflow:
    1. Create a CaseStatus
    2. Add the CaseStatus to the case
    3. Create a ParticipantStatus
    4. Add the ParticipantStatus to the participant
    5. Verify side effects
    """
    logger.info("=" * 80)
    logger.info("DEMO: Status Updates Workflow")
    logger.info("=" * 80)

    case, participant = _setup_initialized_case(client, finder, vendor)

    # Step 1: Create a CaseStatus
    case_status = CaseStatus(
        context=case.as_id,
        em_state=EM.NO_EMBARGO,
        pxa_state=CS_pxa.pxa,
    )
    create_status_activity = CreateCaseStatus(
        actor=vendor.as_id,
        object=case_status,
        context=case.as_id,
    )
    post_to_inbox_and_wait(client, vendor.as_id, create_status_activity)
    verify_object_stored(client, case_status.as_id)
    logger.info("✓ Step 1: CaseStatus created")

    # Step 2: Add CaseStatus to the case
    add_status_activity = AddStatusToCase(
        actor=vendor.as_id,
        object=case_status,
        target=case.as_id,
    )
    post_to_inbox_and_wait(client, vendor.as_id, add_status_activity)

    updated_case = log_case_state(client, case.as_id, "after AddStatusToCase")
    if updated_case:
        status_ids = [
            (s.as_id if hasattr(s, "as_id") else s)
            for s in updated_case.case_status
        ]
        if case_status.as_id not in status_ids:
            raise ValueError(
                f"CaseStatus '{case_status.as_id}' not found in case "
                "after AddStatusToCase"
            )
    logger.info("✓ Step 2: CaseStatus added to case")

    # Step 3: Create a ParticipantStatus for the finder participant
    participant_status = ParticipantStatus(
        context=participant.as_id,
        rm_state=RM.RECEIVED,
        vfd_state=CS_vfd.vfd,
        attributed_to=finder.as_id,
        case_status=case_status,
    )
    create_pstatus_activity = CreateStatusForParticipant(
        actor=vendor.as_id,
        object=participant_status,
    )
    post_to_inbox_and_wait(client, vendor.as_id, create_pstatus_activity)
    verify_object_stored(client, participant_status.as_id)
    logger.info("✓ Step 3: ParticipantStatus created")

    # Step 4: Add ParticipantStatus to the participant
    add_pstatus_activity = AddStatusToParticipant(
        actor=vendor.as_id,
        object=participant_status,
        target=participant.as_id,
    )
    post_to_inbox_and_wait(client, vendor.as_id, add_pstatus_activity)
    logger.info("✓ Step 4: ParticipantStatus added to participant")

    log_case_state(client, case.as_id, "final state")
    logger.info("✅ DEMO COMPLETE: Status updates workflow finished.")


_ALL_DEMOS = [
    (
        "Demo: Status Updates — Notes Workflow",
        demo_notes_workflow,
    ),
    (
        "Demo: Status Updates — Case and Participant Status Workflow",
        demo_status_workflow,
    ),
]


def main(
    skip_health_check: bool = False,
    demos: Optional[Sequence] = None,
) -> None:
    """
    Main entry point for the status_updates demo script.

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
            finder, vendor, coordinator = setup_clean_environment(client)
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
