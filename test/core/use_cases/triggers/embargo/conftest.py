"""Shared fixtures and helpers for embargo trigger use-case tests."""

from collections.abc import Generator

import pytest

from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC
from vultron.enums.roles import CVDRole
from vultron.wire.as2.factories import em_propose_embargo_activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Invite
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import (
    FinderParticipant,
    VendorParticipant,
)
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)


def _persist_actor(dl: SqliteDataLayer, name: str) -> as_Service:
    actor = as_Service(name=name)
    dl.create(actor)
    return actor


def _build_active_embargo_case(
    dl: SqliteDataLayer, owner_id: str, participant_id: str
) -> tuple[as_VulnerabilityCase, as_Invite, str]:
    case = as_VulnerabilityCase(
        name="Embargo regression case",
        attributed_to=owner_id,
    )
    embargo = as_EmbargoEvent(context=case.id_)
    proposal = em_propose_embargo_activity(
        embargo, context=case.id_, actor=owner_id
    )

    owner_participant = VendorParticipant(
        attributed_to=owner_id,
        context=case.id_,
        embargo_consent_state=PEC.SIGNATORY,
        accepted_embargo_ids=[embargo.id_],
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
    case.current_status.em_state = EM.ACTIVE
    case.proposed_embargoes.append(embargo.id_)
    case.set_embargo(embargo.id_)

    dl.create(case)
    dl.create(embargo)
    dl.create(proposal)
    dl.create(owner_participant)
    dl.create(participant)

    return case, proposal, participant.id_


def _build_proposed_embargo_case_no_owner_attribution(
    dl: SqliteDataLayer,
    actor_id: str,
    case_manager_id: str,
) -> tuple[as_VulnerabilityCase, as_Invite, str]:
    """Build a PROPOSED embargo case with ``attributed_to=None``."""
    case = as_VulnerabilityCase(name="No-attribution proposed embargo case")

    embargo = as_EmbargoEvent(context=case.id_)
    proposal = em_propose_embargo_activity(
        embargo, context=case.id_, actor=case_manager_id
    )

    case_manager_participant = VendorParticipant(
        attributed_to=case_manager_id,
        context=case.id_,
        embargo_consent_state=PEC.SIGNATORY,
        accepted_embargo_ids=[embargo.id_],
    )
    case_manager_participant.add_role(CVDRole.CASE_MANAGER)

    actor_participant = FinderParticipant(
        attributed_to=actor_id,
        context=case.id_,
        embargo_consent_state=PEC.INVITED,
    )

    case.case_participants = [
        case_manager_participant.id_,
        actor_participant.id_,
    ]
    case.actor_participant_index = {
        case_manager_id: case_manager_participant.id_,
        actor_id: actor_participant.id_,
    }
    case.current_status.em_state = EM.PROPOSED
    case.proposed_embargoes.append(embargo.id_)

    dl.create(case)
    dl.create(embargo)
    dl.create(proposal)
    dl.create(case_manager_participant)
    dl.create(actor_participant)

    return case, proposal, actor_participant.id_


def _build_exited_case(
    dl: SqliteDataLayer, owner_id: str
) -> as_VulnerabilityCase:
    case = as_VulnerabilityCase(
        name="Exited embargo case",
        attributed_to=owner_id,
    )
    case.current_status.em_state = EM.EXITED
    dl.create(case)
    return case


def _build_no_embargo_case_with_case_manager(
    dl: SqliteDataLayer, owner_id: str
) -> as_VulnerabilityCase:
    case = as_VulnerabilityCase(
        name="No embargo case",
        attributed_to=owner_id,
    )
    owner_participant = VendorParticipant(
        attributed_to=owner_id,
        context=case.id_,
        embargo_consent_state=PEC.NO_EMBARGO,
    )
    owner_participant.add_role(CVDRole.CASE_MANAGER)
    case.case_participants = [owner_participant.id_]
    case.actor_participant_index = {owner_id: owner_participant.id_}
    case.current_status.em_state = EM.NONE
    case.active_embargo = None
    dl.create(case)
    dl.create(owner_participant)
    return case


def _build_active_embargo_case_with_case_manager(
    dl: SqliteDataLayer, actor_id: str
) -> as_VulnerabilityCase:
    """Build a case in EM.ACTIVE state with ``actor`` as owner/case-manager."""
    case = as_VulnerabilityCase(
        name="Active embargo revision case",
        attributed_to=actor_id,
    )
    embargo = as_EmbargoEvent(context=case.id_)

    owner_participant = VendorParticipant(
        attributed_to=actor_id,
        context=case.id_,
        embargo_consent_state=PEC.SIGNATORY,
        accepted_embargo_ids=[embargo.id_],
    )
    owner_participant.add_role(CVDRole.CASE_MANAGER)

    case.case_participants = [owner_participant.id_]
    case.actor_participant_index = {actor_id: owner_participant.id_}
    case.current_status.em_state = EM.ACTIVE
    case.proposed_embargoes.append(embargo.id_)
    case.set_embargo(embargo.id_)

    dl.create(case)
    dl.create(embargo)
    dl.create(owner_participant)
    return case


@pytest.fixture
def finder_actor_and_dl() -> (
    Generator[tuple[as_Service, SqliteDataLayer], None, None]
):
    finder_actor = as_Service(name="Finder Co")
    reset_datalayer(finder_actor.id_)
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=finder_actor.id_)
    dl.clear_all()
    dl.create(finder_actor)
    try:
        yield finder_actor, dl
    finally:
        dl.close()
        reset_datalayer(finder_actor.id_)
