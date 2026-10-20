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

1. Notes workflow: vendor adds a note, carried inline, to a case
2. Status workflow: vendor reports public awareness in a new
   ParticipantStatus, carried inline, on its own participant record

A participant reports P, X or A only in the CaseStatus its own
``Add(ParticipantStatus)`` embeds; ``Add(CaseStatus)`` is the CASE_MANAGER's
record of the status it adopted, and a receiver refuses it from anyone else
(RSH-04-001, RSH-04-005).

Each demo starts from an initialized case with a single REPORTER
participant, seated through its stub Invite, so the status update workflows can be demonstrated in isolation.

This corresponds to the workflow documented in:
    docs/howto/activitypub/activities/status_updates.md

When run as a script, this module will:
1. Check if the API server is available
2. Reset the data layer to a clean state
3. Discover actors (reporter, vendor, coordinator) via the API
4. Run both demo workflows
5. Verify side effects in the data layer
"""

import logging
from collections.abc import Sequence

from vultron.core.models.dimensions import (
    PxaDimension,
)
from vultron.core.states.cs import CS_pxa
from vultron.demo.helpers.runner import run_exchange_demos
from vultron.demo.helpers.verification import _fetch_participant
from vultron.demo.helpers.workflow import setup_initialized_case
from vultron.demo.utils import (  # noqa: F401 — BASE_URL needed for test monkeypatching
    BASE_URL,
    DataLayerClient,
    demo_check,
    demo_step,
    log_case_state,
    post_to_inbox_and_wait,
    ref_id,
    setup_demo_logging,
    verify_object_stored,
)
from vultron.wire.as2.factories import (
    add_note_to_case_activity,
    add_status_to_participant_activity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Remove,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.case_participant import (
    as_CaseParticipant,
)
from vultron.wire.as2.vocab.objects.case_status import (
    as_CaseStatus,
    as_ParticipantStatus,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

logger = logging.getLogger(__name__)


def _setup_initialized_case(
    client: DataLayerClient,
    reporter: as_Actor,
    vendor: as_Actor,
) -> tuple[as_VulnerabilityCase, as_CaseParticipant]:
    """Set up a case with the reporter seated as a REPORTER participant.

    Delegates to the shared :func:`~vultron.demo.helpers.workflow.setup_initialized_case`
    and then looks up the reporter's participant record for callers that need it.
    """
    case = setup_initialized_case(client, reporter, vendor)
    participant = _fetch_participant(client, case.id_, reporter.id_)
    if participant is None:
        raise ValueError(
            f"Reporter participant not found in case {case.id_} after setup"
        )
    return case, participant


def demo_notes_workflow(
    client: DataLayerClient,
    reporter: as_Actor,
    vendor: as_Actor,
    coordinator: as_Actor,
) -> None:
    """
    Demonstrate the notes workflow:
    1. Add a note, carried inline, to a case
    2. Verify the note is stored and the case has the note
    3. Remove the note from the case
    4. Verify the case no longer has the note

    The note travels inline on the single ``Add(Note)`` that attaches it;
    this implementation does not send a separate ``Create(Note)`` ahead of
    the ``Add`` (VAM-01-010, #4706).
    """
    logger.info("=" * 80)
    logger.info("DEMO: Notes Workflow")
    logger.info("=" * 80)

    case, _participant = _setup_initialized_case(client, reporter, vendor)

    note = None
    with demo_step("Step 1: Vendor adds a note, carried inline, to the case"):
        note = as_Note(
            name="Initial Triage Note",
            content=(
                "Reviewed the report. The heap buffer overflow is confirmed "
                "and affects all versions prior to 3.2.1."
            ),
            context=case.id_,
            attributed_to=vendor.id_,
        )
        add_note_activity = add_note_to_case_activity(
            note, actor=vendor.id_, target=case.id_
        )
        post_to_inbox_and_wait(client, vendor.id_, add_note_activity)
        with demo_check("Note stored in data layer"):
            verify_object_stored(client, note.id_)
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

    with demo_step("Step 2: Vendor removes note from case"):
        # The vendor is this case's CASE_OWNER and its CASE_MANAGER
        # (setup_initialized_case), so its inbox is the manager's inbox and the
        # sender is the note's author: the Remove(Note) is entitled (CM-30-001).
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
    reporter: as_Actor,
    vendor: as_Actor,
    coordinator: as_Actor,
) -> None:
    """
    Demonstrate the status updates workflow:
    1. The vendor reports public awareness in a new ParticipantStatus,
       carried inline, on its own participant record
    2. Verify the status is on the vendor's record and the case status
       adopted the public awareness

    A participant sends only ``Add(ParticipantStatus)``, embedding its view
    of the case status; it never sends ``Add(CaseStatus)``, which only the
    CASE_MANAGER sends (RSH-04-001, RSH-04-005).  The status travels inline
    on the ``Add`` that attaches it.  This implementation does not support a
    separate ``Create(ParticipantStatus)`` ahead of the ``Add`` (#4598).
    """
    logger.info("=" * 80)
    logger.info("DEMO: Status Updates Workflow")
    logger.info("=" * 80)

    case, _participant = _setup_initialized_case(client, reporter, vendor)
    vendor_participant = _fetch_participant(client, case.id_, vendor.id_)
    if vendor_participant is None:
        raise ValueError(
            f"Vendor participant not found in case {case.id_} after setup"
        )
    current = vendor_participant.participant_status
    if current is None:
        raise ValueError(
            f"Vendor participant '{vendor_participant.id_}' has no status"
        )
    before = log_case_state(client, case.id_, "before the report")
    if before is None:
        raise ValueError(f"Could not retrieve case {case.id_} after setup")

    # Bound before the step so Step 2 can read it (#2308 ratchet).
    participant_status = None
    with demo_step(
        "Step 1: Vendor reports public awareness in its own ParticipantStatus"
    ):
        # A snapshot of every dimension the vendor holds, with the public
        # awareness it reports in the embedded case status (RSH-04-001).
        participant_status = as_ParticipantStatus(
            context=case.id_,
            rm=current.rm,
            vf=current.vf,
            d=current.d,
            attributed_to=vendor.id_,
            cvd_role=current.cvd_role,
            case_status=as_CaseStatus(
                context=case.id_,
                em=before.current_status.em,
                pxa=PxaDimension(state=CS_pxa.Pxa),
            ),
        )
        add_pstatus_activity = add_status_to_participant_activity(
            participant_status,
            actor=vendor.id_,
            target=vendor_participant.id_,
        )
        post_to_inbox_and_wait(client, vendor.id_, add_pstatus_activity)

    with demo_step("Step 2: Verify the status and the adopted case status"):
        with demo_check("ParticipantStatus present on the vendor's record"):
            updated = _fetch_participant(client, case.id_, vendor.id_)
            status_ids = (
                [s.id_ for s in updated.participant_statuses]
                if updated is not None
                else []
            )
            if participant_status.id_ not in status_ids:
                raise ValueError(
                    f"ParticipantStatus '{participant_status.id_}' not found"
                    " on the vendor's participant record"
                )
        with demo_check("Case status adopted public awareness"):
            updated_case = log_case_state(client, case.id_, "final state")
            if updated_case is None:
                raise ValueError("Could not retrieve case after the report")
            pxa = updated_case.current_status.pxa.state
            if pxa != CS_pxa.Pxa:
                raise ValueError(
                    f"Case status pxaState is {pxa}, expected"
                    f" {CS_pxa.Pxa} after the vendor's report"
                )

    logger.info("✅ DEMO COMPLETE: Status updates workflow finished.")


_ALL_DEMOS = [
    (
        "Demo: Status Updates — Notes Workflow",
        demo_notes_workflow,
    ),
    (
        "Demo: Status Updates — Participant Status Workflow",
        demo_status_workflow,
    ),
]


def main(
    skip_health_check: bool = False,
    demos: Sequence | None = None,
) -> None:
    """Main entry point for the status updates demo demo script."""
    run_exchange_demos(
        _ALL_DEMOS, skip_health_check=skip_health_check, demos=demos
    )


if __name__ == "__main__":
    setup_demo_logging()
    main()
