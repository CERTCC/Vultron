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

"""The CASE_MANAGER's refusal closes the proposer's pending assertion.

A non-manager's embargo proposal is recorded in its pending-assertion store
(EP-09-008, SYNC-11-002).  A refused proposal is never committed, so only the
manager's ``Reject(Invite(EmbargoEvent))`` closes it; another participant's
``Reject`` is an answer, not the refusal, and closes nothing (#3962 AC-4).
"""

from typing import cast

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.events.embargo import (
    RejectInviteToEmbargoOnCaseReceivedEvent,
)
from vultron.core.models.pending_assertion import (
    get_pending_assertion_store,
    record_pending_assertion,
)
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC
from vultron.core.use_cases.received.embargo import (
    RejectInviteToEmbargoOnCaseReceivedUseCase,
)
from vultron.enums.roles import CVDRole
from vultron.semantic_registry import extract_event
from vultron.wire.as2.factories import (
    em_propose_embargo_activity,
    em_reject_embargo_activity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Invite
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import (
    FinderParticipant,
    VendorParticipant,
)
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

_PROPOSER = "https://example.org/actors/refusal-finder"
_MANAGER = "https://example.org/actors/refusal-manager"
_OTHER = "https://example.org/actors/refusal-other"
_INVITE = MessageSemantics.INVITE_TO_EMBARGO_ON_CASE.value


def _proposer_with_pending_proposal() -> tuple[
    SqliteDataLayer, VulnerabilityCase, as_Invite
]:
    """The proposer's replica: its ask to the manager is pending."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_PROPOSER)
    for actor_id in (_PROPOSER, _MANAGER, _OTHER):
        dl.create(as_Service(id_=actor_id, name=actor_id.rsplit("/", 1)[-1]))
    case = VulnerabilityCase(name="Refusal case", attributed_to=_MANAGER)
    manager = VendorParticipant(
        attributed_to=_MANAGER,
        context=case.id_,
        embargo_consent_state=PEC.UNBOUND,
    )
    manager.add_role(CVDRole.CASE_MANAGER)
    finders = [
        FinderParticipant(
            attributed_to=actor_id,
            context=case.id_,
            embargo_consent_state=PEC.UNBOUND,
        )
        for actor_id in (_PROPOSER, _OTHER)
    ]
    case.case_participants = [manager.id_, *(f.id_ for f in finders)]
    case.actor_participant_index = {
        _MANAGER: manager.id_,
        _PROPOSER: finders[0].id_,
        _OTHER: finders[1].id_,
    }
    case.append_case_status(em_state=EM.NONE)
    dl.create(case)
    for participant in (manager, *finders):
        dl.create(participant)

    embargo = as_EmbargoEvent(context=case.id_, end_time=days_from_now_utc(30))
    proposal = em_propose_embargo_activity(
        embargo=embargo, context=case.id_, actor=_PROPOSER, to=[_MANAGER]
    )
    dl.create(embargo)
    dl.create(proposal)
    record_pending_assertion(_PROPOSER, case.id_, _INVITE, proposal.id_)
    return dl, case, proposal


def _receive_reject(
    dl: SqliteDataLayer,
    proposal: as_Invite,
    case_id: str,
    rejecting_actor_id: str,
) -> None:
    reject = em_reject_embargo_activity(
        proposal=proposal, context=case_id, actor=rejecting_actor_id
    )
    event = cast(
        RejectInviteToEmbargoOnCaseReceivedEvent,
        extract_event(reject).model_copy(
            update={"receiving_actor_id": _PROPOSER}
        ),
    )
    RejectInviteToEmbargoOnCaseReceivedUseCase(
        dl, event, wire_render_port=As2WireRenderAdapter()
    ).execute()


def _pending(case_id: str, proposal_id: str) -> bool:
    return get_pending_assertion_store(_PROPOSER).is_suppressed(
        case_id, _INVITE, proposal_id
    )


@pytest.mark.spec("EP-09-008")
@pytest.mark.spec("SYNC-11-003")
def test_case_managers_reject_closes_the_pending_proposal() -> None:
    dl, case, proposal = _proposer_with_pending_proposal()
    assert _pending(case.id_, proposal.id_)

    _receive_reject(dl, proposal, case.id_, _MANAGER)

    assert not _pending(case.id_, proposal.id_)


@pytest.mark.spec("EP-09-008")
def test_participants_reject_leaves_the_proposal_pending() -> None:
    dl, case, proposal = _proposer_with_pending_proposal()

    _receive_reject(dl, proposal, case.id_, _OTHER)

    assert _pending(case.id_, proposal.id_)
