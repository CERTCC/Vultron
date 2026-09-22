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
"""EP-08: open embargo proposals resolve in earliest-expiration order.

`docs/topics/process_models/em/defaults.md` is a normative page and requires that
a Participant facing two or more open proposals accept the earliest-expiring one
and handle the remainder as revisions.  That rule lived only in prose until
EP-08, so nothing held the implementation to it and the implementation diverged:
``find_embargo_proposal_id`` selects by *arrival* order.

Both tests below are ``xfail(strict=True)``.  They assert the EP-08 behaviour
against the real use-case entry point rather than the private helper, so they
survive the signature change the fix requires (the helper needs DataLayer access
to read each candidate's ``end_time``).  They auto-promote to passing when #3470
lands.

Each drives the path EP-08 actually governs: a *default* selection for
EP-08-001/002 (no ``proposal_id`` on the request), and an *owner* accept that
moves EM PROPOSED -> ACTIVE for EP-08-003.  A participant-consent accept against
an already-active embargo decides nothing, so it cannot witness either rule.
Note that #3470's remit covers both records of open proposals:
``pending_embargo_proposal_index`` has no remover at all, and
``proposed_embargoes`` is pruned only on teardown.

Spec: EP-08-001, EP-08-002, EP-08-003.  ADR-0100.
"""

from datetime import timedelta
from typing import cast

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.models._helpers import now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC
from vultron.core.use_cases.triggers.embargo import SvcAcceptEmbargoUseCase
from vultron.core.use_cases.triggers.requests import (
    AcceptEmbargoTriggerRequest,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.factories import em_propose_embargo_activity
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import (
    FinderParticipant,
    VendorParticipant,
)
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

from .conftest import _persist_actor


def _build_case_with_two_open_proposals(
    dl: SqliteDataLayer, owner_id: str, participant_id: str
) -> tuple[VulnerabilityCase, str, str]:
    """Build a PROPOSED case with two open proposals in reverse expiry order.

    The proposal recorded *first* expires *later*, which is the counter-proposal
    shape EMB-15-003 produces: countering emits a fresh EP while the EM state
    stays PROPOSED, so arrival order puts the superseded terms in front.

    Returns the case plus the proposal IDs of the later- and earlier-expiring
    proposals, in that order.
    """
    case = VulnerabilityCase(
        name="Two open embargo proposals",
        attributed_to=owner_id,
    )

    # Durations are set at construction: ``as_EmbargoEvent`` is frozen
    # (ADR-0074), so assigning ``end_time`` afterwards raises and would make
    # these tests fail for a reason that has nothing to do with EP-08.
    start = now_utc()
    later = as_EmbargoEvent(
        context=case.id_,
        start_time=start,
        end_time=start + timedelta(days=90),
    )
    earlier = as_EmbargoEvent(
        context=case.id_,
        start_time=start,
        end_time=start + timedelta(days=30),
    )

    later_proposal = em_propose_embargo_activity(
        later, context=case.id_, actor=owner_id
    )
    earlier_proposal = em_propose_embargo_activity(
        earlier, context=case.id_, actor=owner_id
    )

    owner_participant = VendorParticipant(
        attributed_to=owner_id,
        context=case.id_,
        embargo_consent_state=PEC.UNBOUND,
    )
    owner_participant.add_role(CVDRole.CASE_MANAGER)
    participant = FinderParticipant(
        attributed_to=participant_id,
        context=case.id_,
        embargo_consent_state=PEC.INVITED,
    )

    case.case_participants = [owner_participant.id_, participant.id_]
    case.actor_participant_index = {
        owner_id: owner_participant.id_,
        participant_id: participant.id_,
    }
    case.append_case_status(em_state=EM.PROPOSED)

    # Insertion order is load-bearing: the later-expiring proposal is recorded
    # first, so a resolver that returns the first entry returns the wrong one.
    case.proposed_embargoes.extend([later.id_, earlier.id_])
    case.pending_embargo_proposal_index[later.id_] = later_proposal.id_
    case.pending_embargo_proposal_index[earlier.id_] = earlier_proposal.id_

    dl.create(case)
    for obj in (
        later,
        earlier,
        later_proposal,
        earlier_proposal,
        owner_participant,
        participant,
    ):
        dl.create(obj)

    return case, later_proposal.id_, earlier_proposal.id_


@pytest.mark.xfail(
    strict=True,
    reason=(
        "EP-08-001/EP-08-002: find_embargo_proposal_id selects by arrival order, "
        "not earliest expiration. Tracked by #3470."
    ),
)
@pytest.mark.spec("EP-08-001")
@pytest.mark.spec("EP-08-002")
def test_default_selection_picks_the_earliest_expiring_proposal(
    finder_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """An accept that names no proposal must resolve to the shortest embargo.

    Asserted through the use case's own resolution step rather than the helper,
    because the fix changes the helper's signature.
    """
    finder, finder_dl = finder_actor_and_dl
    owner = _persist_actor(finder_dl, "Vendor Co")
    case, later_proposal_id, earlier_proposal_id = (
        _build_case_with_two_open_proposals(finder_dl, owner.id_, finder.id_)
    )

    request = AcceptEmbargoTriggerRequest(
        actor_id=finder.id_,
        case_id=case.id_,
    )
    use_case = SvcAcceptEmbargoUseCase(
        finder_dl, request, trigger_activity=TriggerActivityAdapter(finder_dl)
    )
    use_case._prepare()

    resolved = use_case._proposal_id
    assert resolved != later_proposal_id, (
        "resolved the later-expiring proposal, which is the superseded one "
        "when a counter-proposal is open"
    )
    assert resolved == earlier_proposal_id


def _build_case_with_one_open_proposal(
    dl: SqliteDataLayer, owner_id: str, participant_id: str
) -> tuple[VulnerabilityCase, str]:
    """Build a PROPOSED case with exactly one open proposal, owned by *owner_id*.

    EM must be PROPOSED and the accepting actor must be the case owner, or the
    accept takes the participant-consent branch
    (``SvcAcceptEmbargoUseCase._log_lifecycle_result`` else-arm) and decides
    nothing — which is the shape ``_build_active_embargo_case`` produces and
    ``test_accept.py`` already covers.  EP-08-003 is about the *decision* path.
    """
    case = VulnerabilityCase(
        name="One open embargo proposal",
        attributed_to=owner_id,
    )

    start = now_utc()
    embargo = as_EmbargoEvent(
        context=case.id_,
        start_time=start,
        end_time=start + timedelta(days=30),
    )
    proposal = em_propose_embargo_activity(
        embargo, context=case.id_, actor=owner_id
    )

    owner_participant = VendorParticipant(
        attributed_to=owner_id,
        context=case.id_,
        embargo_consent_state=PEC.UNBOUND,
    )
    owner_participant.add_role(CVDRole.CASE_MANAGER)
    participant = FinderParticipant(
        attributed_to=participant_id,
        context=case.id_,
        embargo_consent_state=PEC.INVITED,
    )

    case.case_participants = [owner_participant.id_, participant.id_]
    case.actor_participant_index = {
        owner_id: owner_participant.id_,
        participant_id: participant.id_,
    }
    case.append_case_status(em_state=EM.PROPOSED)
    case.proposed_embargoes.append(embargo.id_)
    case.pending_embargo_proposal_index[embargo.id_] = proposal.id_

    dl.create(case)
    for obj in (embargo, proposal, owner_participant, participant):
        dl.create(obj)

    return case, proposal.id_


@pytest.mark.xfail(
    strict=True,
    reason=(
        "EP-08-003: nothing removes an entry from "
        "pending_embargo_proposal_index once its proposal is decided, and "
        "proposed_embargoes is pruned only on teardown. Tracked by #3470."
    ),
)
@pytest.mark.spec("EP-08-003")
def test_accepting_a_proposal_removes_it_from_the_open_proposal_record(
    owner_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """A decided proposal must not remain in the open-proposal record.

    EP-08-002 orders that record, so a retained decided entry is a candidate the
    resolver can still select.

    The owner accepts here, and the EM assertion below runs *first* on purpose:
    it proves the harness actually produced a decision (PROPOSED -> ACTIVE)
    before the record is checked, so this cannot pass or fail vacuously.  A
    participant-consent accept against an already-ACTIVE embargo decides nothing
    and would leave the entry stale for a reason EP-08-003 does not govern.
    """
    owner, owner_dl = owner_actor_and_dl
    finder = _persist_actor(owner_dl, "Finder Co")
    case, proposal_id = _build_case_with_one_open_proposal(
        owner_dl, owner.id_, finder.id_
    )
    assert proposal_id in case.pending_embargo_proposal_index.values()

    request = AcceptEmbargoTriggerRequest(
        actor_id=owner.id_,
        case_id=case.id_,
        proposal_id=proposal_id,
    )
    SvcAcceptEmbargoUseCase(
        owner_dl, request, trigger_activity=TriggerActivityAdapter(owner_dl)
    ).execute()

    updated_case = cast(VulnerabilityCase, owner_dl.read(case.id_))
    assert updated_case.current_status.em.state == EM.ACTIVE, (
        "the owner's accept did not activate the embargo, so no proposal was "
        "decided and this test cannot speak to EP-08-003"
    )
    assert (
        proposal_id not in updated_case.pending_embargo_proposal_index.values()
    )
