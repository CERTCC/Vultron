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
2. Case status workflow: vendor creates a as_CaseStatus → adds it to the case
3. Participant status workflow: vendor creates a as_ParticipantStatus for a
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
from typing import Optional, Sequence, Tuple

from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Create,
    as_Remove,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.case_participant import (
    as_CaseParticipant,
)
from vultron.enums.roles import CVDRole
from vultron.core.states.participant_embargo_consent import PEC
from vultron.wire.as2.vocab.objects.case_status import (
    as_CaseStatus,
    as_ParticipantStatus,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.core.states.cs import CS_pxa, CS_vfd
from vultron.demo.utils import (  # noqa: F401 — BASE_URL needed for test monkeypatching
    BASE_URL,
    DataLayerClient,
    demo_check,
    demo_step,
    log_case_state,
    post_to_inbox_and_wait,
    ref_id,
    verify_object_stored,
    setup_demo_logging,
)
from vultron.wire.as2.factories import (
    add_note_to_case_activity,
    add_status_to_case_activity,
    add_status_to_participant_activity,
    create_case_status_activity,
    create_status_for_participant_activity,
)

from vultron.demo.helpers.runner import run_exchange_demos
from vultron.demo.helpers.verification import _fetch_participant
from vultron.demo.helpers.workflow import setup_initialized_case

logger = logging.getLogger(__name__)


def _setup_initialized_case(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
) -> Tuple[as_VulnerabilityCase, as_CaseParticipant]:
    """Set up a case with one FinderReporter participant.

    Delegates to the shared :func:`~vultron.demo.helpers.workflow.setup_initialized_case`
    and then looks up the finder's participant record for callers that need it.
    """
    case = setup_initialized_case(client, finder, vendor)
    participant = _fetch_participant(client, case.id_, finder.id_)
    if participant is None:
        raise ValueError(
            f"Finder participant not found in case {case.id_} after setup"
        )
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

    with demo_step("Step 1: Vendor creates note"):
        note = as_Note(
            name="Initial Triage Note",
            content=(
                "Reviewed the report. The heap buffer overflow is confirmed "
                "and affects all versions prior to 3.2.1."
            ),
            context=case.id_,
            attributed_to=vendor.id_,
        )
        create_note_activity = as_Create(
            actor=vendor.id_,
            object_=note,
        )
        post_to_inbox_and_wait(client, vendor.id_, create_note_activity)
        with demo_check("Note stored in data layer"):
            verify_object_stored(client, note.id_)

    with demo_step("Step 2: Vendor adds note to case"):
        add_note_activity = add_note_to_case_activity(
            note, actor=vendor.id_, target=case.id_
        )
        post_to_inbox_and_wait(client, vendor.id_, add_note_activity)
        with demo_check("Note present in case"):
            updated_case = log_case_state(
                client, case.id_, "after AddNoteToCaseActivity"
            )
            if updated_case:
                note_ids = [(ref_id(n) or str(n)) for n in updated_case.notes]
                if note.id_ not in note_ids:
                    raise ValueError(
                        f"Note '{note.id_}' not found in case after AddNoteToCaseActivity"
                    )

    with demo_step("Step 3: Vendor removes note from case"):
        remove_note_activity = as_Remove(
            actor=vendor.id_,
            object_=note,
            target=case.id_,
        )
        post_to_inbox_and_wait(client, vendor.id_, remove_note_activity)
        with demo_check("Note absent from case"):
            updated_case = log_case_state(
                client, case.id_, "after RemoveNoteFromCase"
            )
            if updated_case:
                note_ids = [(ref_id(n) or str(n)) for n in updated_case.notes]
                if note.id_ in note_ids:
                    raise ValueError(
                        f"Note '{note.id_}' still in case after RemoveNoteFromCase"
                    )

    logger.info("✅ DEMO COMPLETE: Notes workflow finished.")


def demo_status_workflow(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    coordinator: as_Actor,
) -> None:
    """
    Demonstrate the status updates workflow:
    1. Create a as_CaseStatus
    2. Add the as_CaseStatus to the case
    3. Create a as_ParticipantStatus
    4. Add the as_ParticipantStatus to the participant
    5. Verify side effects
    """
    logger.info("=" * 80)
    logger.info("DEMO: Status Updates Workflow")
    logger.info("=" * 80)

    case, participant = _setup_initialized_case(client, finder, vendor)

    with demo_step("Step 1: Vendor creates as_CaseStatus"):
        case_status = as_CaseStatus(
            context=case.id_,
            em_state=EM.NO_EMBARGO,
            pxa_state=CS_pxa.pxa,
        )
        create_status_activity = create_case_status_activity(
            case_status, actor=vendor.id_, context=case.id_
        )
        post_to_inbox_and_wait(client, vendor.id_, create_status_activity)
        with demo_check("as_CaseStatus stored in data layer"):
            verify_object_stored(client, case_status.id_)

    with demo_step("Step 2: Vendor adds as_CaseStatus to case"):
        add_status_activity = add_status_to_case_activity(
            case_status, actor=vendor.id_, target=case.id_
        )
        post_to_inbox_and_wait(client, vendor.id_, add_status_activity)
        with demo_check("as_CaseStatus present in case"):
            updated_case = log_case_state(
                client, case.id_, "after AddStatusToCaseActivity"
            )
            if updated_case:
                status_ids = [
                    (ref_id(s) or str(s)) for s in updated_case.case_statuses
                ]
                if case_status.id_ not in status_ids:
                    raise ValueError(
                        f"as_CaseStatus '{case_status.id_}' not found in case "
                        "after AddStatusToCaseActivity"
                    )

    with demo_step("Step 3: Vendor creates as_ParticipantStatus"):
        participant_status = as_ParticipantStatus(
            context=participant.id_,
            rm_state=RM.RECEIVED,
            vfd_state=CS_vfd.vfd,
            attributed_to=finder.id_,
            em_consent_state=PEC.NO_EMBARGO,
            cvd_role=[CVDRole.FINDER],
            case_status=case_status,
        )
        create_pstatus_activity = create_status_for_participant_activity(
            participant_status, actor=vendor.id_
        )
        post_to_inbox_and_wait(client, vendor.id_, create_pstatus_activity)
        with demo_check("as_ParticipantStatus stored in data layer"):
            verify_object_stored(client, participant_status.id_)

    with demo_step("Step 4: Vendor adds as_ParticipantStatus to participant"):
        add_pstatus_activity = add_status_to_participant_activity(
            participant_status, actor=vendor.id_, target=participant.id_
        )
        post_to_inbox_and_wait(client, vendor.id_, add_pstatus_activity)
        with demo_check("Final case state"):
            log_case_state(client, case.id_, "final state")

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
    """Main entry point for the status updates demo demo script."""
    run_exchange_demos(
        _ALL_DEMOS, skip_health_check=skip_health_check, demos=demos
    )


if __name__ == "__main__":
    setup_demo_logging()
    main()
