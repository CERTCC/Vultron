"""Tests for SvcProposeEmbargoRevisionUseCase."""

from datetime import UTC, datetime, timedelta
from typing import cast

import pytest

from test.support.ledger import committed_event_types
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.behaviors.embargo.nodes import EMBARGO_INVITE_EVENT_TYPE
from vultron.core.models.activity import VultronActivity
from vultron.core.models.case import VulnerabilityCase
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.core.use_cases.triggers.embargo import (
    SvcProposeEmbargoRevisionUseCase,
)
from vultron.core.use_cases.triggers.requests import (
    ProposeEmbargoRevisionTriggerRequest,
)
from vultron.errors import VultronInvalidStateTransitionError
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant

from .conftest import (
    _add_participant,
    _build_active_embargo_case_with_case_manager,
    _build_unbound_case_with_case_manager,
)


def test_propose_embargo_revision_transitions_em_to_revise(
    finder_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """SvcProposeEmbargoRevisionUseCase transitions EM.ACTIVE → EM.REVISE via BTBridge."""
    actor, dl = finder_actor_and_dl
    case = _build_active_embargo_case_with_case_manager(dl, actor.id_)

    request = ProposeEmbargoRevisionTriggerRequest(
        actor_id=actor.id_,
        case_id=case.id_,
        end_time=datetime.now(tz=UTC) + timedelta(days=14),
    )

    result = SvcProposeEmbargoRevisionUseCase(
        dl,
        request,
        trigger_activity=TriggerActivityAdapter(dl),
        sync_port=SyncActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
    ).execute()

    assert result.activity is not None
    updated_case = cast(VulnerabilityCase, dl.read(case.id_))
    assert updated_case.current_status.em.state == EM.REVISE
    assert len(updated_case.proposed_embargoes) == 2


@pytest.mark.spec("EP-09-002")
@pytest.mark.spec("EP-09-008")
def test_manager_revision_relays_an_invite_to_each_other_participant(
    finder_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """The CASE_MANAGER's own revision is relayed; nothing is self-addressed."""
    actor, dl = finder_actor_and_dl
    case = _build_active_embargo_case_with_case_manager(dl, actor.id_)
    other_id = "https://example.org/actors/other-vendor"
    _add_participant(dl, case.id_, other_id)

    request = ProposeEmbargoRevisionTriggerRequest(
        actor_id=actor.id_,
        case_id=case.id_,
        end_time=datetime.now(tz=UTC) + timedelta(days=14),
    )

    SvcProposeEmbargoRevisionUseCase(
        dl,
        request,
        trigger_activity=TriggerActivityAdapter(dl),
        sync_port=SyncActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
    ).execute()

    queued = [cast(VultronActivity, dl.read(i)) for i in dl.outbox_list()]
    invites = [a for a in queued if a.type_ == "Invite"]
    assert [a.to for a in invites] == [[other_id]]
    assert not any(actor.id_ in (a.to or []) for a in queued)
    assert EMBARGO_INVITE_EVENT_TYPE in committed_event_types(dl, case.id_)


def test_propose_embargo_revision_invalid_em_state_raises_error(
    finder_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """SvcProposeEmbargoRevisionUseCase raises error when EM state is not ACTIVE/REVISE."""
    actor, dl = finder_actor_and_dl
    case = _build_unbound_case_with_case_manager(dl, actor.id_)

    request = ProposeEmbargoRevisionTriggerRequest(
        actor_id=actor.id_,
        case_id=case.id_,
        end_time=datetime.now(tz=UTC) + timedelta(days=14),
    )

    with pytest.raises(VultronInvalidStateTransitionError):
        SvcProposeEmbargoRevisionUseCase(
            dl,
            request,
            trigger_activity=TriggerActivityAdapter(dl),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()


def test_propose_embargo_revision_invalid_state_does_not_persist_embargo(
    finder_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Failed revision must not leave behind a persisted EmbargoEvent."""
    actor, dl = finder_actor_and_dl
    case = _build_unbound_case_with_case_manager(dl, actor.id_)

    before = len(list(dl.list_objects("EmbargoEvent")))

    request = ProposeEmbargoRevisionTriggerRequest(
        actor_id=actor.id_,
        case_id=case.id_,
        end_time=datetime.now(tz=UTC) + timedelta(days=14),
    )

    with pytest.raises(VultronInvalidStateTransitionError):
        SvcProposeEmbargoRevisionUseCase(
            dl,
            request,
            trigger_activity=TriggerActivityAdapter(dl),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

    after = len(list(dl.list_objects("EmbargoEvent")))
    assert after == before


def test_propose_embargo_revision_in_revise_state_succeeds(
    finder_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """SvcProposeEmbargoRevisionUseCase succeeds when EM is already REVISE.

    Guards against a regression where EM.REVISE → EM.REVISE counter-revision
    is incorrectly blocked.  Existing participant consent rows MUST NOT change on this
    path — nor on ACTIVE → REVISE: a revision *proposal* changes nobody's
    consent (EP-05-002, ADR-0093); a signatory lapses (derived, nothing stored) only when the
    owner activates longer terms it has not accepted.
    """
    actor, dl = finder_actor_and_dl

    case = _build_active_embargo_case_with_case_manager(dl, actor.id_)
    case.append_case_status(em_state=EM.REVISE)
    dl.save(case)

    participant_id = case.actor_participant_index[actor.id_]
    participant_before = cast(as_CaseParticipant, dl.read(participant_id))
    consents_before = list(participant_before.embargo_consents)

    request = ProposeEmbargoRevisionTriggerRequest(
        actor_id=actor.id_,
        case_id=case.id_,
        end_time=datetime.now(tz=UTC) + timedelta(days=21),
    )

    result = SvcProposeEmbargoRevisionUseCase(
        dl,
        request,
        trigger_activity=TriggerActivityAdapter(dl),
        sync_port=SyncActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
    ).execute()

    assert result.activity is not None
    updated_case = cast(VulnerabilityCase, dl.read(case.id_))
    assert updated_case.current_status.em.state == EM.REVISE
    assert len(updated_case.proposed_embargoes) == 2

    participant_after = cast(as_CaseParticipant, dl.read(participant_id))
    # The proposer's row for the embargo in force is untouched; proposing adds
    # only an ACCEPTED row for the proposed revision (ADR-0120).
    proposed_id = updated_case.proposed_embargoes[-1]
    assert [
        r
        for r in participant_after.embargo_consents
        if r.embargo_id != proposed_id
    ] == consents_before
    assert (
        participant_after.consent_for(proposed_id)
        == EmbargoConsentState.ACCEPTED
    )
