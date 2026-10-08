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
"""Ledger fan-out reaches active participants only (CM-10-004).

A ``CaseLedgerEntry`` announcement is case content, so the CASE_MANAGER sends
it only to *active* participants: seated directly or having accepted its stub
Invite, and — while an embargo is active — ``SIGNATORY`` (ADR-0114).
See ``notes/case-joining.md`` and #4046.
"""

import py_trees
import pytest

from test.core.behaviors.bt_harness import BTTestScenario
from test.support.embargo_register import activate
from vultron.core.behaviors.sync.nodes.fanout import (
    CollectLogEntryRecipientsNode,
)
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.dimensions import RmDimension
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole
from vultron.wire.as2.factories import rm_invite_to_case_activity
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

MANAGER_ID = "https://example.org/actors/case-manager"
SIGNATORY_ID = "https://example.org/actors/signatory-finder"
UNCONSENTED_ID = "https://example.org/actors/unconsented-reporter"
INVITEE_ID = "https://example.org/actors/invited-vendor"


def _participant(
    case_id: str,
    actor_id: str,
    role: CVDRole,
    rm_state: RM,
    embargo_id: str,
    consent: EmbargoConsentState,
    *,
    joined: bool = True,
) -> CaseParticipant:
    return CaseParticipant(
        joined=joined,
        attributed_to=actor_id,
        context=case_id,
        case_roles=[role],
        embargo_consents=[
            EmbargoConsent(embargo_id=embargo_id, state=consent)
        ],
        participant_statuses=[
            ParticipantStatus(
                context=case_id,
                attributed_to=actor_id,
                rm=RmDimension(state=rm_state),
                cvd_role=[role],
            )
        ],
    )


@pytest.mark.spec("CM-10-004")
def test_ledger_fanout_reaches_only_active_participants() -> None:
    """Of three non-manager participants under an active embargo, one is active.

    - a directly seated finder that accepted the embargo (a signatory) — active;
    - a directly seated reporter whose consent is still ``INVITED`` — inert
      while the embargo is active;
    - a vendor with an outstanding stub Invite it never answered — inert.

    The invitee is also ``INVITED``, so either fact alone excludes it.
    """
    scenario = BTTestScenario(actor_id=MANAGER_ID)
    case = VulnerabilityCase(
        name="Active fan-out",
        stub_summary="Security issue — active fan-out test",
        attributed_to=MANAGER_ID,
    )
    embargo = as_EmbargoEvent(context=case.id_, end_time=days_from_now_utc(45))
    activate(case, embargo.id_)
    participants = {
        MANAGER_ID: _participant(
            case.id_,
            MANAGER_ID,
            CVDRole.CASE_MANAGER,
            RM.ACCEPTED,
            embargo.id_,
            EmbargoConsentState.ACCEPTED,
        ),
        SIGNATORY_ID: _participant(
            case.id_,
            SIGNATORY_ID,
            CVDRole.FINDER,
            RM.ACCEPTED,
            embargo.id_,
            EmbargoConsentState.ACCEPTED,
        ),
        UNCONSENTED_ID: _participant(
            case.id_,
            UNCONSENTED_ID,
            CVDRole.REPORTER,
            RM.ACCEPTED,
            embargo.id_,
            EmbargoConsentState.INVITED,
        ),
        INVITEE_ID: _participant(
            case.id_,
            INVITEE_ID,
            CVDRole.VENDOR,
            RM.RECEIVED,
            embargo.id_,
            EmbargoConsentState.INVITED,
            joined=False,
        ),
    }
    for actor_id, participant in participants.items():
        case.case_participants.append(participant.id_)
        case.actor_participant_index[actor_id] = participant.id_
    stub_invite = rm_invite_to_case_activity(
        INVITEE_ID, target=case, actor=MANAGER_ID, roles=[CVDRole.VENDOR]
    )
    scenario.seed(embargo, *participants.values(), case, stub_invite)

    result = scenario.run(
        CollectLogEntryRecipientsNode(case_id=case.id_),
        log_entry=CaseLedgerEntry(
            case_id=case.id_,
            log_object_id=f"{case.id_}/events/status-1",
            event_type="add_participant_status",
        ),
    )

    scenario.assert_success(result)
    recipients = py_trees.blackboard.Blackboard.storage.get(
        "/fanout_recipients"
    )
    assert recipients == [SIGNATORY_ID]
