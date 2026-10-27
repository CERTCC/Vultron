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
"""An invitee's replica receiving a relayed ``Invite(EmbargoEvent)`` (EP-09-002).

``seed_invitee_case`` builds the invitee's store at a chosen EM state, with
the roles and embargo policy that decide its answer; ``deliver_relayed_invite``
hands it the CASE_MANAGER's relayed Invite; ``answers_in_outbox`` reads the
answers it queued.  Shared by the owner-answer tests and the arrival-order
tests, which deliver the same Invite before and after the ledger entries it
relates to.
"""

from datetime import timedelta
from typing import Any

from test.support.embargo_register import activate, propose
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.actor import VultronOrganization
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.embargo_policy import EmbargoPolicy
from vultron.core.models.use_case_result import HandlerResult
from vultron.core.states.em import EM
from vultron.core.use_cases.received.embargo import (
    InviteToEmbargoOnCaseReceivedUseCase,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.factories import em_propose_embargo_activity
from vultron.wire.as2.vocab.objects.case_participant import (
    as_CaseParticipant as WireCP,
)
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

#: The CASE_MANAGER that relays the Invite.
COORD = "https://example.org/actors/coordinator"
#: The invitee whose replica receives it.
INVITEE = "https://example.org/actors/invitee"


def seed_invitee_case(
    dl: SqliteDataLayer,
    case_id: str,
    *,
    em_state: EM,
    roles: list[CVDRole],
    proposal_days: int,
    policy_days: int | None,
) -> tuple[VulnerabilityCase, as_EmbargoEvent]:
    """Seed *dl* as ``INVITEE``'s replica of *case_id* at *em_state*.

    Returns the case and the proposed embargo ``e1``, which ends in
    *proposal_days*.  At ``ACTIVE`` a prior embargo is in force, so ``e1`` is
    a revision; at ``REVISE`` another revision is open as well.  The invitee
    holds *roles* and publishes an embargo policy of *policy_days*, or none.
    """
    case = VulnerabilityCase(
        id_=case_id, name="Owner Answer", attributed_to=COORD
    )
    embargo = as_EmbargoEvent(
        id_=f"{case_id}/embargos/e1",
        context=case_id,
        end_time=days_from_now_utc(proposal_days),
    )
    dl.create(embargo)
    if em_state in (EM.ACTIVE, EM.REVISE):
        prior = as_EmbargoEvent(
            id_=f"{case_id}/embargos/e0",
            context=case_id,
            end_time=days_from_now_utc(30),
        )
        dl.create(prior)
        activate(case, prior.id_)
    if em_state == EM.REVISE:
        other = as_EmbargoEvent(
            id_=f"{case_id}/embargos/e-other",
            context=case_id,
            end_time=days_from_now_utc(20),
        )
        dl.create(other)
        propose(case, other.id_)
    assert case.em_state == em_state
    coord_cp = WireCP(
        attributed_to=COORD,
        context=case_id,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    invitee_cp = WireCP(
        attributed_to=INVITEE,
        context=case_id,
        case_roles=roles,
    )
    dl.create(coord_cp)
    dl.create(invitee_cp)
    case.actor_participant_index[COORD] = coord_cp.id_
    case.actor_participant_index[INVITEE] = invitee_cp.id_
    dl.create(case)
    profile = VultronOrganization(
        id_=INVITEE,
        embargo_policy=(
            None
            if policy_days is None
            else EmbargoPolicy(
                actor_id=INVITEE,
                inbox=f"{INVITEE}/inbox",
                preferred_duration=timedelta(days=policy_days),
            )
        ),
    )
    dl.create(profile)
    return case, embargo


def deliver_relayed_invite(
    dl: SqliteDataLayer,
    case: VulnerabilityCase,
    embargo: as_EmbargoEvent,
    make_payload: Any,
) -> HandlerResult:
    """Deliver ``COORD``'s relayed ``Invite(embargo)`` to ``INVITEE``."""
    invite = em_propose_embargo_activity(
        embargo=embargo,
        context=case.id_,
        actor=COORD,
        to=[INVITEE],
    )
    return InviteToEmbargoOnCaseReceivedUseCase(
        dl,
        make_payload(invite, receiving_actor_id=INVITEE),
        trigger_activity=TriggerActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
        sync_port=SyncActivityAdapter(dl),
    ).execute()


def answers_in_outbox(dl: SqliteDataLayer, actor_id: str) -> list[str]:
    """Types of the Accept/Reject answers *actor_id* queued to the manager."""
    answers = []
    for activity_id in dl.outbox_list():
        activity = dl.read(activity_id)
        type_ = getattr(activity, "type_", None)
        if (
            type_ in ("Accept", "Reject")
            and getattr(activity, "actor", None) == actor_id
        ):
            assert getattr(activity, "to", None) == [COORD]
            answers.append(str(type_))
    return answers
