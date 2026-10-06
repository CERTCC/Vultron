"""Shared fixtures and helpers for embargo trigger use-case tests."""

from collections.abc import Generator

import pytest

from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger import compute_genesis_hash
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.factories import em_propose_embargo_activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Invite
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import (
    FinderParticipant,
    VendorParticipant,
)
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent


def _persist_actor(dl: SqliteDataLayer, name: str) -> as_Service:
    actor = as_Service(name=name)
    dl.create(actor)
    return actor


def _build_active_embargo_case(
    dl: SqliteDataLayer, owner_id: str, participant_id: str
) -> tuple[VulnerabilityCase, as_Invite, str]:
    case = VulnerabilityCase(
        name="Embargo regression case",
        attributed_to=owner_id,
    )
    embargo = as_EmbargoEvent(context=case.id_, end_time=days_from_now_utc(45))
    proposal = em_propose_embargo_activity(
        embargo, context=case.id_, actor=owner_id
    )

    owner_participant = VendorParticipant(
        attributed_to=owner_id,
        context=case.id_,
        embargo_consents=[
            EmbargoConsent(
                embargo_id=embargo.id_, state=EmbargoConsentState.ACCEPTED
            )
        ],
    )
    owner_participant.add_role(CVDRole.CASE_MANAGER)
    participant = FinderParticipant(
        attributed_to=participant_id,
        context=case.id_,
        embargo_consents=[
            EmbargoConsent(
                embargo_id=embargo.id_, state=EmbargoConsentState.INVITED
            )
        ],
    )

    case.case_participants = [owner_participant.id_, participant.id_]
    case.actor_participant_index = {
        owner_id: owner_participant.id_,
        participant_id: participant.id_,
    }
    case.append_case_status(em_state=EM.ACTIVE)
    case.proposed_embargoes.append(embargo.id_)
    case.pending_embargo_proposal_index[embargo.id_] = proposal.id_
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
) -> tuple[VulnerabilityCase, as_Invite, str]:
    """Build a PROPOSED embargo case with ``attributed_to=None``."""
    case = VulnerabilityCase(name="No-attribution proposed embargo case")
    # No attributed_to → no auto-seeded CaseStatus; seed one manually.
    case.add_case_status(CaseStatus(context=case.id_))
    # Set genesis_hash explicitly so EmitCaseStatusUpdateNode can bootstrap
    # the ledger chain without attributed_to (RSH-04-002/004, CLP-08-005).
    assert case.published is not None
    case.genesis_hash = compute_genesis_hash(
        case.id_, case.published, case_manager_id
    )

    embargo = as_EmbargoEvent(context=case.id_, end_time=days_from_now_utc(45))
    proposal = em_propose_embargo_activity(
        embargo, context=case.id_, actor=case_manager_id
    )

    case_manager_participant = VendorParticipant(
        attributed_to=case_manager_id,
        context=case.id_,
        embargo_consents=[
            EmbargoConsent(
                embargo_id=embargo.id_, state=EmbargoConsentState.ACCEPTED
            )
        ],
    )
    case_manager_participant.add_role(CVDRole.CASE_MANAGER)

    actor_participant = FinderParticipant(
        attributed_to=actor_id,
        context=case.id_,
        embargo_consents=[
            EmbargoConsent(
                embargo_id=embargo.id_, state=EmbargoConsentState.INVITED
            )
        ],
    )

    case.case_participants = [
        case_manager_participant.id_,
        actor_participant.id_,
    ]
    case.actor_participant_index = {
        case_manager_id: case_manager_participant.id_,
        actor_id: actor_participant.id_,
    }
    case.append_case_status(em_state=EM.PROPOSED)
    case.proposed_embargoes.append(embargo.id_)
    case.pending_embargo_proposal_index[embargo.id_] = proposal.id_

    dl.create(case)
    dl.create(embargo)
    dl.create(proposal)
    dl.create(case_manager_participant)
    dl.create(actor_participant)

    return case, proposal, actor_participant.id_


def _build_exited_case(
    dl: SqliteDataLayer, owner_id: str
) -> VulnerabilityCase:
    """Case at ``EM.EXITED`` whose owner is its CASE_MANAGER (CM-24-006)."""
    case = VulnerabilityCase(
        name="Exited embargo case",
        attributed_to=owner_id,
    )
    owner_participant = VendorParticipant(
        attributed_to=owner_id,
        context=case.id_,
    )
    owner_participant.add_role(CVDRole.CASE_MANAGER)
    case.case_participants = [owner_participant.id_]
    case.actor_participant_index = {owner_id: owner_participant.id_}
    case.append_case_status(em_state=EM.EXITED)
    dl.create(case)
    dl.create(owner_participant)
    return case


def _build_unbound_case_with_case_manager(
    dl: SqliteDataLayer, owner_id: str
) -> VulnerabilityCase:
    case = VulnerabilityCase(
        name="No embargo case",
        attributed_to=owner_id,
    )
    owner_participant = VendorParticipant(
        attributed_to=owner_id,
        context=case.id_,
    )
    owner_participant.add_role(CVDRole.CASE_MANAGER)
    case.case_participants = [owner_participant.id_]
    case.actor_participant_index = {owner_id: owner_participant.id_}
    case.append_case_status(em_state=EM.NONE)
    case.active_embargo = None
    dl.create(case)
    dl.create(owner_participant)
    return case


def _build_active_embargo_case_with_case_manager(
    dl: SqliteDataLayer, actor_id: str
) -> VulnerabilityCase:
    """Build a case in EM.ACTIVE state with ``actor`` as owner/case-manager."""
    case = VulnerabilityCase(
        name="Active embargo revision case",
        attributed_to=actor_id,
    )
    embargo = as_EmbargoEvent(context=case.id_, end_time=days_from_now_utc(45))

    owner_participant = VendorParticipant(
        attributed_to=actor_id,
        context=case.id_,
        embargo_consents=[
            EmbargoConsent(
                embargo_id=embargo.id_, state=EmbargoConsentState.ACCEPTED
            )
        ],
    )
    owner_participant.add_role(CVDRole.CASE_MANAGER)

    case.case_participants = [owner_participant.id_]
    case.actor_participant_index = {actor_id: owner_participant.id_}
    case.append_case_status(em_state=EM.ACTIVE)
    case.proposed_embargoes.append(embargo.id_)
    case.set_embargo(embargo.id_)

    dl.create(case)
    dl.create(embargo)
    dl.create(owner_participant)
    return case


def _actor_and_own_store(
    name: str,
) -> Generator[tuple[as_Service, SqliteDataLayer], None, None]:
    """Yield an actor and *its own* store.

    Which actor owns the store is not decoration: a trigger's BT executes as the
    requesting actor and its store follows that actor (ADR-0073), so a test whose
    request names actor A while holding B's store leaves the tree reading an
    empty one and the case "not found".  Pick the fixture that matches the
    ``actor_id`` on the request under test.
    """
    actor = as_Service(name=name)
    reset_datalayer(actor.id_)
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=actor.id_)
    dl.clear_all()
    dl.create(actor)
    try:
        yield actor, dl
    finally:
        dl.close()
        reset_datalayer(actor.id_)


@pytest.fixture
def finder_actor_and_dl() -> Generator[
    tuple[as_Service, SqliteDataLayer], None, None
]:
    """The finder and its own store — for triggers requested *by the finder*."""
    yield from _actor_and_own_store("Finder Co")


@pytest.fixture
def owner_actor_and_dl() -> Generator[
    tuple[as_Service, SqliteDataLayer], None, None
]:
    """The case owner and its own store — for triggers requested *by the owner*.

    Embargo teardown is one: the authority is the case's CASE_MANAGER, which
    ``_build_active_embargo_case`` gives to the owner, so the owner is both the
    requesting actor and the store's owner.
    """
    yield from _actor_and_own_store("Vendor Co")


def _assert_asked_case_manager(
    dl: SqliteDataLayer,
    *,
    actor_id: str,
    case_id: str,
    manager_id: str,
    activity_type: str,
    event_type: str,
) -> str:
    """Assert a non-manager trigger only asked the CASE_MANAGER (EP-09-008).

    One activity of *activity_type* is queued, addressed to the manager
    alone; no ``Add(CaseStatus)`` declaration is queued; and the activity is
    recorded pending in *actor_id*'s pending-assertion store
    (SYNC-11-002).  Returns the queued activity's id.
    """
    from typing import cast

    from test.support.ledger import committed_event_types
    from vultron.core.models.activity import VultronActivity
    from vultron.core.models.pending_assertion import (
        get_pending_assertion_store,
    )

    queued = [cast(VultronActivity, dl.read(i)) for i in dl.outbox_list()]
    asks = [a for a in queued if a.type_ == activity_type]
    assert len(asks) == 1, [a.type_ for a in queued]
    assert asks[0].to == [manager_id]
    # A case-status declaration is a ledger commit, never an outbox item, so
    # "declares nothing" is checked against the ledger (AC-3).
    assert "add_case_status_to_case" not in committed_event_types(
        dl, case_id
    ), "a non-manager must not declare an EM state it has not been given"
    store = get_pending_assertion_store(actor_id)
    assert store.is_suppressed(case_id, event_type, asks[0].id_)
    return asks[0].id_


def _add_participant(
    dl: SqliteDataLayer,
    case_id: str,
    actor_id: str,
    consent: EmbargoConsentState | None = EmbargoConsentState.ACCEPTED,
) -> str:
    """Add a finder participant for *actor_id* to a stored case; return its id.

    Its row for the embargo in force is ``ACCEPTED`` by default, so a case-content send reaches it while the
    embargo is in force (CM-10-004).
    """
    from typing import cast

    case = cast(VulnerabilityCase, dl.read(case_id))
    rows = (
        [EmbargoConsent(embargo_id=case.active_embargo_id, state=consent)]
        if consent is not None and case.active_embargo_id is not None
        else []
    )
    participant = FinderParticipant(
        attributed_to=actor_id,
        context=case_id,
        embargo_consents=rows,
    )
    dl.create(participant)
    case.case_participants = [*case.case_participants, participant.id_]
    case.actor_participant_index = {
        **case.actor_participant_index,
        actor_id: participant.id_,
    }
    dl.save(case)
    return participant.id_


def _case_with_open_proposal(
    dl: SqliteDataLayer, owner_id: str
) -> tuple[VulnerabilityCase, str]:
    """A case at EM.PROPOSED whose only open proposal is the owner's."""
    case = _build_unbound_case_with_case_manager(dl, owner_id)
    embargo = as_EmbargoEvent(context=case.id_, end_time=days_from_now_utc(45))
    proposal = em_propose_embargo_activity(
        embargo, context=case.id_, actor=owner_id
    )
    dl.create(embargo)
    dl.create(proposal)
    case.append_case_status(em_state=EM.PROPOSED)
    case.proposed_embargoes.append(embargo.id_)
    case.pending_embargo_proposal_index[embargo.id_] = proposal.id_
    dl.save(case)
    return case, proposal.id_
