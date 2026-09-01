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
"""Tests for CaseActor lazy invite-expiry lapse (#2212) and late-Accept
compatibility (#2213)."""

from datetime import datetime, timedelta, timezone

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.services.embargo_lifecycle import EmbargoLifecycle
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC
from vultron.core.use_cases.received.embargo import (
    AcceptInviteToEmbargoOnCaseReceivedUseCase,
    InviteToEmbargoOnCaseReceivedUseCase,
    RejectInviteToEmbargoOnCaseReceivedUseCase,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.factories import (
    em_accept_embargo_activity,
    em_propose_embargo_activity,
    em_reject_embargo_activity,
)
from vultron.wire.as2.vocab.objects.case_participant import (
    as_CaseParticipant as WireCP,
)
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import (  # noqa: F401
    as_VulnerabilityCase,
)

CoreCase = VulnerabilityCase

_NOW = datetime.now(tz=timezone.utc).replace(microsecond=0)
_PAST = _NOW - timedelta(days=1)
# _FUTURE must stay above the EP-07-002 minimum window floor (~3 days from
# datetime.now()).  The original hardcoded date (2026-09-03) has since fallen
# within the floor; use a rolling offset instead.
_FUTURE = datetime.now(tz=timezone.utc) + timedelta(days=7)

_COORD = "https://example.org/actors/coordinator"
_INVITEE = "https://example.org/actors/invitee"


def _make_dl(actor_id: str = _COORD) -> SqliteDataLayer:
    return SqliteDataLayer("sqlite:///:memory:", actor_id=actor_id)


def _make_active_embargo_case(
    dl: SqliteDataLayer,
    case_id: str,
    embargo_id: str,
    invitee_pec: PEC = PEC.INVITED,
    invitee_deadline: datetime | None = None,
):
    """Create and persist a case with an active embargo and one invitee participant.

    Returns (case, embargo, invitee_participant_id).
    """
    case = VulnerabilityCase(
        id_=case_id,
        name="Lapse Test Case",
        attributed_to=_COORD,
    )
    case.append_case_status(em_state=EM.ACTIVE)
    embargo = as_EmbargoEvent(id_=embargo_id, context=case_id)
    case.set_embargo(embargo_id)

    invitee_cp = WireCP(
        attributed_to=_INVITEE,
        context=case_id,
        embargo_consent_state=invitee_pec.value,
        case_roles=[CVDRole.VENDOR],
    )
    invitee_cp_core = invitee_cp.to_core()
    if invitee_deadline is not None:
        invitee_cp_core.invite_rsvp_deadline = invitee_deadline

    dl.create(case)
    dl.create(embargo)
    dl.create(invitee_cp_core)
    case.actor_participant_index[_INVITEE] = invitee_cp_core.id_
    dl.save(case)
    return case, embargo, invitee_cp_core.id_


# ---------------------------------------------------------------------------
# Unit tests — EmbargoLifecycle.detect_and_apply_lapse
# ---------------------------------------------------------------------------


class TestDetectAndApplyLapse:
    """Direct unit tests for EmbargoLifecycle.detect_and_apply_lapse."""

    def test_lapse_invited_past_deadline(self):
        """INVITED participant lapses to DECLINED when deadline has passed."""
        dl = _make_dl()
        case_id = "https://example.org/cases/lapse1"
        embargo_id = "https://example.org/cases/lapse1/embargos/e1"
        _make_active_embargo_case(
            dl,
            case_id,
            embargo_id,
            invitee_pec=PEC.INVITED,
            invitee_deadline=_PAST,
        )

        service = EmbargoLifecycle(persistence=dl)
        result = service.detect_and_apply_lapse(
            case_id=case_id,
            actor_id=_INVITEE,
            now=_NOW,
        )

        assert result.is_lapsed is True
        assert len(result.participant_changes) == 1
        change = result.participant_changes[0]
        assert change.pec_before == PEC.INVITED.value
        assert change.pec_after == PEC.DECLINED.value

        # Verify persistence
        case = dl.read(case_id)
        assert isinstance(case, CoreCase)
        participant_id = case.actor_participant_index[_INVITEE]
        participant = dl.read(participant_id)
        assert isinstance(participant, CaseParticipant)
        assert participant.embargo_consent_state == PEC.DECLINED

    def test_no_lapse_future_deadline(self):
        """Participant is NOT lapsed when deadline is in the future."""
        dl = _make_dl()
        case_id = "https://example.org/cases/lapse2"
        embargo_id = "https://example.org/cases/lapse2/embargos/e2"
        _make_active_embargo_case(
            dl,
            case_id,
            embargo_id,
            invitee_pec=PEC.INVITED,
            invitee_deadline=_FUTURE,
        )

        service = EmbargoLifecycle(persistence=dl)
        result = service.detect_and_apply_lapse(
            case_id=case_id,
            actor_id=_INVITEE,
            now=_NOW,
        )

        assert result.is_lapsed is False
        assert result.participant_changes == []

        case = dl.read(case_id)
        assert isinstance(case, CoreCase)
        participant_id = case.actor_participant_index[_INVITEE]
        participant = dl.read(participant_id)
        assert isinstance(participant, CaseParticipant)
        assert participant.embargo_consent_state == PEC.INVITED

    def test_no_lapse_no_deadline(self):
        """Participant is never lapsed when no invite_rsvp_deadline is set."""
        dl = _make_dl()
        case_id = "https://example.org/cases/lapse3"
        embargo_id = "https://example.org/cases/lapse3/embargos/e3"
        _make_active_embargo_case(
            dl,
            case_id,
            embargo_id,
            invitee_pec=PEC.INVITED,
            invitee_deadline=None,
        )

        service = EmbargoLifecycle(persistence=dl)
        result = service.detect_and_apply_lapse(
            case_id=case_id,
            actor_id=_INVITEE,
            now=_NOW,
        )

        assert result.is_lapsed is False
        assert result.participant_changes == []

    def test_lapse_idempotent_already_declined(self):
        """detect_and_apply_lapse does not re-fire DECLINE when already DECLINED."""
        dl = _make_dl()
        case_id = "https://example.org/cases/lapse4"
        embargo_id = "https://example.org/cases/lapse4/embargos/e4"
        _make_active_embargo_case(
            dl,
            case_id,
            embargo_id,
            invitee_pec=PEC.DECLINED,
            invitee_deadline=_PAST,
        )

        service = EmbargoLifecycle(persistence=dl)
        result = service.detect_and_apply_lapse(
            case_id=case_id,
            actor_id=_INVITEE,
            now=_NOW,
        )

        # Deadline passed, so is_lapsed=True, but no PEC change (already DECLINED).
        assert result.is_lapsed is True
        assert result.participant_changes == []

    def test_lapse_no_background_task(self):
        """Lapse is derived on read without any background scheduler (AC-6)."""
        dl = _make_dl()
        case_id = "https://example.org/cases/lapse5"
        embargo_id = "https://example.org/cases/lapse5/embargos/e5"
        _make_active_embargo_case(
            dl,
            case_id,
            embargo_id,
            invitee_pec=PEC.INVITED,
            invitee_deadline=_PAST,
        )

        # No scheduler; call detect_and_apply_lapse directly to trigger lapse.
        service = EmbargoLifecycle(persistence=dl)
        result = service.detect_and_apply_lapse(
            case_id=case_id,
            actor_id=_INVITEE,
            now=_NOW,
        )

        assert result.is_lapsed is True
        # PEC changed without any background task.
        assert any(
            c.pec_after == PEC.DECLINED.value
            for c in result.participant_changes
        )


# ---------------------------------------------------------------------------
# Integration tests — InviteToEmbargoOnCaseReceivedUseCase stores deadline
# ---------------------------------------------------------------------------


class TestInviteStoresDeadline:
    """Receiving an Invite stores the RSVP deadline on the participant record."""

    def test_invite_with_deadline_stores_rsvp_deadline(self, make_payload):
        """Processing an InviteToEmbargoOnCase with rsvp_deadline stores it."""
        dl = _make_dl(actor_id=_INVITEE)
        case_id = "https://example.org/cases/store1"
        embargo_id = "https://example.org/cases/store1/embargos/e1"

        case = VulnerabilityCase(
            id_=case_id, name="Store Deadline", attributed_to=_COORD
        )
        case.append_case_status(em_state=EM.PROPOSED)
        embargo = as_EmbargoEvent(id_=embargo_id, context=case_id)

        invitee_cp = WireCP(
            attributed_to=_INVITEE,
            context=case_id,
            case_roles=[CVDRole.VENDOR],
        )
        invitee_cp_core = invitee_cp.to_core()

        dl.create(case)
        dl.create(embargo)
        dl.create(invitee_cp_core)
        case.actor_participant_index[_INVITEE] = invitee_cp_core.id_
        dl.save(case)

        # Propose with a deadline
        invite = em_propose_embargo_activity(
            embargo=embargo,
            context=case.id_,
            actor=_COORD,
            to=[_INVITEE],
            rsvp_deadline=_FUTURE,
        )
        event = make_payload(invite, receiving_actor_id=_INVITEE)

        InviteToEmbargoOnCaseReceivedUseCase(dl, event).execute()

        # The deadline should be stored on the participant record
        fresh_case = dl.read(case_id)
        assert isinstance(fresh_case, CoreCase)
        p_id = fresh_case.actor_participant_index.get(_INVITEE)
        assert p_id is not None
        participant = dl.read(p_id)
        assert isinstance(participant, CaseParticipant)
        assert participant.invite_rsvp_deadline == _FUTURE


class TestInviteeIsTheAddressee:
    """The invitee is the activity's ``to:`` recipient, not the receiving actor.

    ``receiving_actor_id`` answers "whose replica is this?"; the Invite's
    ``to:`` field answers "who is being invited?".  ADR-0022 requires the
    second to be threaded into the tree as leaf-node data rather than reused
    as the BT execution identity.  Conflating them writes the PEC transition
    and the RSVP deadline (CM-28-001, CM-28-003) onto the wrong participant
    record, so the CaseActor records an invitation it never received and the
    real invitee is left with no deadline for lapse detection to find.
    """

    def _seed_case(
        self,
        dl,
        case_id: str,
        embargo_id: str,
        invitee_pec: PEC = PEC.NO_EMBARGO,
    ):
        """Case with the coordinator as CASE_MANAGER and a separate invitee."""
        case = VulnerabilityCase(
            id_=case_id, name="Addressee Test", attributed_to=_COORD
        )
        case.append_case_status(em_state=EM.PROPOSED)
        embargo = as_EmbargoEvent(id_=embargo_id, context=case_id)

        coord_cp = WireCP(
            attributed_to=_COORD,
            context=case_id,
            case_roles=[CVDRole.CASE_MANAGER],
        ).to_core()
        invitee_cp = WireCP(
            attributed_to=_INVITEE,
            context=case_id,
            embargo_consent_state=invitee_pec.value,
            case_roles=[CVDRole.VENDOR],
        ).to_core()

        dl.create(case)
        dl.create(embargo)
        dl.create(coord_cp)
        dl.create(invitee_cp)
        case.actor_participant_index[_COORD] = coord_cp.id_
        case.actor_participant_index[_INVITEE] = invitee_cp.id_
        dl.save(case)
        return case, embargo, coord_cp.id_, invitee_cp.id_

    def _read_participant(self, dl, participant_id: str) -> CaseParticipant:
        participant = dl.read(participant_id)
        assert isinstance(participant, CaseParticipant)
        return participant

    def test_case_actor_receipt_targets_the_addressee(self, make_payload):
        """CaseActor processing an Invite addressed to someone else."""
        dl = _make_dl(actor_id=_COORD)
        case_id = "https://example.org/cases/addressee1"
        embargo_id = "https://example.org/cases/addressee1/embargos/e1"
        case, embargo, coord_p_id, invitee_p_id = self._seed_case(
            dl, case_id, embargo_id
        )

        invite = em_propose_embargo_activity(
            embargo=embargo,
            context=case.id_,
            actor=_INVITEE,
            to=[_INVITEE],
            rsvp_deadline=_FUTURE,
        )
        event = make_payload(invite, receiving_actor_id=_COORD)

        InviteToEmbargoOnCaseReceivedUseCase(dl, event).execute()

        invitee = self._read_participant(dl, invitee_p_id)
        assert invitee.embargo_consent_state == PEC.INVITED
        assert invitee.invite_rsvp_deadline == _FUTURE

        coord = self._read_participant(dl, coord_p_id)
        assert coord.embargo_consent_state == PEC.NO_EMBARGO
        assert coord.invite_rsvp_deadline is None

    def test_absent_receiving_actor_targets_the_addressee(self, make_payload):
        """CLI/replay dispatch: no receiving_actor_id, store owned by CaseActor."""
        dl = _make_dl(actor_id=_COORD)
        case_id = "https://example.org/cases/addressee2"
        embargo_id = "https://example.org/cases/addressee2/embargos/e2"
        case, embargo, coord_p_id, invitee_p_id = self._seed_case(
            dl, case_id, embargo_id
        )

        invite = em_propose_embargo_activity(
            embargo=embargo,
            context=case.id_,
            actor=_INVITEE,
            to=[_INVITEE],
            rsvp_deadline=_FUTURE,
        )
        event = make_payload(invite)
        assert event.receiving_actor_id is None

        InviteToEmbargoOnCaseReceivedUseCase(dl, event).execute()

        invitee = self._read_participant(dl, invitee_p_id)
        assert invitee.embargo_consent_state == PEC.INVITED
        assert invitee.invite_rsvp_deadline == _FUTURE

        coord = self._read_participant(dl, coord_p_id)
        assert coord.embargo_consent_state == PEC.NO_EMBARGO
        assert coord.invite_rsvp_deadline is None

    def test_missing_to_field_warns_and_uses_receiving_actor(
        self, make_payload, caplog
    ):
        """An Invite with no ``to:`` is malformed (OX-08-001) and says so."""
        dl = _make_dl(actor_id=_INVITEE)
        case_id = "https://example.org/cases/addressee3"
        embargo_id = "https://example.org/cases/addressee3/embargos/e3"
        case, embargo, _, invitee_p_id = self._seed_case(
            dl, case_id, embargo_id
        )

        invite = em_propose_embargo_activity(
            embargo=embargo,
            context=case.id_,
            actor=_COORD,
            rsvp_deadline=_FUTURE,
        )
        event = make_payload(invite, receiving_actor_id=_INVITEE)
        assert event.invitee_id is None

        caplog.set_level("WARNING")
        InviteToEmbargoOnCaseReceivedUseCase(dl, event).execute()

        assert any(
            "carries no 'to:' recipient" in record.message
            for record in caplog.records
        )
        # Degrades to the receiving actor rather than dropping the invite.
        invitee = self._read_participant(dl, invitee_p_id)
        assert invitee.embargo_consent_state == PEC.INVITED

    def test_reject_declines_the_rejecting_actor_not_the_receiver(
        self, make_payload
    ):
        """The DECLINE lands on the actor who rejected, not the CaseActor.

        ``reject_invite_to_embargo_tree`` takes ``rejecting_actor_id`` but only
        logged it, so the participant lookup fell through to the BT execution
        actor and the CaseActor declined its own embargo on the rejecter's
        behalf.
        """
        dl = _make_dl(actor_id=_COORD)
        case_id = "https://example.org/cases/addressee4"
        embargo_id = "https://example.org/cases/addressee4/embargos/e4"
        case, embargo, coord_p_id, invitee_p_id = self._seed_case(
            dl, case_id, embargo_id, invitee_pec=PEC.INVITED
        )

        proposal = em_propose_embargo_activity(
            embargo=embargo,
            context=case.id_,
            actor=_COORD,
            to=[_INVITEE],
            id_=f"{case_id}/proposals/p1",
        )
        dl.create(proposal)
        reject = em_reject_embargo_activity(
            proposal=proposal, context=case.id_, actor=_INVITEE, to=[_COORD]
        )
        event = make_payload(reject, receiving_actor_id=_COORD)

        RejectInviteToEmbargoOnCaseReceivedUseCase(dl, event).execute()

        invitee = self._read_participant(dl, invitee_p_id)
        assert invitee.embargo_consent_state == PEC.DECLINED

        coord = self._read_participant(dl, coord_p_id)
        assert coord.embargo_consent_state == PEC.NO_EMBARGO


# ---------------------------------------------------------------------------
# Integration tests — AcceptInviteToEmbargoOnCaseReceivedUseCase (EMB-17)
# ---------------------------------------------------------------------------


def _make_accept_event(proposal, case, accepting_actor_id: str, make_payload):
    accept = em_accept_embargo_activity(
        proposal=proposal,
        context=case.id_,
        actor=accepting_actor_id,
    )
    return make_payload(accept, receiving_actor_id=_COORD)


class TestLateAcceptHandling:
    """EMB-17: late-Accept compatibility routing."""

    def test_late_accept_honored_when_embargo_current(self, make_payload):
        """Late Accept with matching active embargo → PEC SIGNATORY (AC-2 #2213)."""
        dl = _make_dl(actor_id=_COORD)
        case_id = "https://example.org/cases/ea1"
        embargo_id = "https://example.org/cases/ea1/embargos/e1"

        case, embargo, _ = _make_active_embargo_case(
            dl,
            case_id,
            embargo_id,
            invitee_pec=PEC.INVITED,
            invitee_deadline=_PAST,
        )

        proposal = em_propose_embargo_activity(
            embargo=embargo,
            context=case.id_,
            actor=_COORD,
            to=[_INVITEE],
            id_=f"{case_id}/proposals/p1",
        )
        dl.create(proposal)

        event = _make_accept_event(proposal, case, _INVITEE, make_payload)
        AcceptInviteToEmbargoOnCaseReceivedUseCase(dl, event).execute()

        fresh_case = dl.read(case_id)
        assert isinstance(fresh_case, CoreCase)
        p_id = fresh_case.actor_participant_index[_INVITEE]
        participant = dl.read(p_id)
        assert isinstance(participant, CaseParticipant)
        assert participant.embargo_consent_state == PEC.SIGNATORY

    def test_late_accept_reinvite_when_stale_embargo(self, make_payload):
        """Late Accept for stale embargo → re-invite with current embargo (AC-3 #2213)."""
        from unittest.mock import MagicMock

        dl = _make_dl(actor_id=_COORD)
        case_id = "https://example.org/cases/ea2"
        current_embargo_id = "https://example.org/cases/ea2/embargos/current"
        stale_embargo_id = "https://example.org/cases/ea2/embargos/stale"

        # Case has current_embargo active, not stale_embargo
        case, current_embargo, _ = _make_active_embargo_case(
            dl,
            case_id,
            current_embargo_id,
            invitee_pec=PEC.INVITED,
            invitee_deadline=_PAST,
        )

        # Also create the stale embargo in the DL
        stale_embargo = as_EmbargoEvent(id_=stale_embargo_id, context=case_id)
        dl.create(stale_embargo)

        # Proposal was for the stale embargo
        stale_proposal = em_propose_embargo_activity(
            embargo=stale_embargo,
            context=case.id_,
            actor=_COORD,
            id_=f"{case_id}/proposals/stale",
        )
        dl.create(stale_proposal)

        # Mock trigger_activity to capture re-invite call
        trigger_mock = MagicMock()
        new_invite_id = f"{case_id}/proposals/reinvite"
        trigger_mock.propose_embargo.return_value = (new_invite_id, {})

        event = _make_accept_event(
            stale_proposal, case, _INVITEE, make_payload
        )
        AcceptInviteToEmbargoOnCaseReceivedUseCase(
            dl, event, trigger_activity=trigger_mock
        ).execute()

        # propose_embargo should have been called with the CURRENT embargo
        trigger_mock.propose_embargo.assert_called_once()
        call_kwargs = trigger_mock.propose_embargo.call_args
        assert (
            call_kwargs.kwargs.get("embargo_id") == current_embargo_id
            or call_kwargs.args[0] == current_embargo_id
        )

        # Invitee PEC should be INVITED (re-invited to current embargo)
        fresh_case = dl.read(case_id)
        assert isinstance(fresh_case, CoreCase)
        p_id = fresh_case.actor_participant_index[_INVITEE]
        participant = dl.read(p_id)
        assert isinstance(participant, CaseParticipant)
        assert participant.embargo_consent_state == PEC.INVITED

    def test_late_accept_noop_when_em_exited(self, make_payload):
        """Late Accept after EM EXITED → ack no-op, actor stays in case (AC-4 #2213)."""
        dl = _make_dl(actor_id=_COORD)
        case_id = "https://example.org/cases/ea3"
        embargo_id = "https://example.org/cases/ea3/embargos/e3"

        case, embargo, participant_id = _make_active_embargo_case(
            dl,
            case_id,
            embargo_id,
            invitee_pec=PEC.DECLINED,
            invitee_deadline=_PAST,
        )
        # Simulate EM EXITED (embargo terminated, PEC reset)
        case.append_case_status(em_state=EM.EXITED)
        case.set_embargo(None)
        dl.save(case)

        proposal = em_propose_embargo_activity(
            embargo=embargo,
            context=case.id_,
            actor=_COORD,
            id_=f"{case_id}/proposals/p3",
        )
        dl.create(proposal)

        event = _make_accept_event(proposal, case, _INVITEE, make_payload)
        AcceptInviteToEmbargoOnCaseReceivedUseCase(dl, event).execute()

        # Actor must still be a case participant (not removed)
        fresh_case = dl.read(case_id)
        assert isinstance(fresh_case, CoreCase)
        assert _INVITEE in fresh_case.actor_participant_index

        # PEC should be NO_EMBARGO (reset; no active embargo to consent to)
        p_id = fresh_case.actor_participant_index[_INVITEE]
        participant = dl.read(p_id)
        assert isinstance(participant, CaseParticipant)
        assert participant.embargo_consent_state == PEC.NO_EMBARGO

    def test_accept_within_deadline_uses_normal_path(self, make_payload):
        """Accept before deadline → normal BT path, PEC SIGNATORY without lapse."""
        dl = _make_dl(actor_id=_COORD)
        case_id = "https://example.org/cases/ea4"
        embargo_id = "https://example.org/cases/ea4/embargos/e4"

        # Set up case with PROPOSED EM and vendor participant
        case = VulnerabilityCase(
            id_=case_id, name="Normal Accept", attributed_to=_COORD
        )
        case.append_case_status(em_state=EM.PROPOSED)
        embargo = as_EmbargoEvent(id_=embargo_id, context=case_id)

        invitee_cp = WireCP(
            attributed_to=_INVITEE,
            context=case_id,
            embargo_consent_state=PEC.INVITED.value,
            case_roles=[CVDRole.VENDOR],
        )
        invitee_cp_core = invitee_cp.to_core()
        invitee_cp_core.invite_rsvp_deadline = _FUTURE

        dl.create(case)
        dl.create(embargo)
        dl.create(invitee_cp_core)
        case.actor_participant_index[_INVITEE] = invitee_cp_core.id_
        dl.save(case)

        proposal = em_propose_embargo_activity(
            embargo=embargo,
            context=case.id_,
            actor=_INVITEE,
            id_=f"{case_id}/proposals/p4",
        )
        dl.create(proposal)
        case.pending_embargo_proposal_index[embargo_id] = proposal.id_
        dl.save(case)

        event = _make_accept_event(proposal, case, _COORD, make_payload)
        AcceptInviteToEmbargoOnCaseReceivedUseCase(dl, event).execute()

        # Normal path: coordinator accepted → EM ACTIVE
        fresh_case = dl.read(case_id)
        assert isinstance(fresh_case, CoreCase)
        assert fresh_case.current_status.em.state == EM.ACTIVE

    def test_accept_no_deadline_uses_normal_path(self, make_payload):
        """Accept with no deadline → policy window fallback, normal path."""
        dl = _make_dl(actor_id=_COORD)
        case_id = "https://example.org/cases/ea5"
        embargo_id = "https://example.org/cases/ea5/embargos/e5"

        case = VulnerabilityCase(
            id_=case_id, name="No Deadline Accept", attributed_to=_COORD
        )
        case.append_case_status(em_state=EM.PROPOSED)
        embargo = as_EmbargoEvent(id_=embargo_id, context=case_id)

        invitee_cp = WireCP(
            attributed_to=_INVITEE,
            context=case_id,
            embargo_consent_state=PEC.INVITED.value,
            case_roles=[CVDRole.VENDOR],
        )
        invitee_cp_core = invitee_cp.to_core()
        # No deadline set — invite_rsvp_deadline stays None

        dl.create(case)
        dl.create(embargo)
        dl.create(invitee_cp_core)
        case.actor_participant_index[_INVITEE] = invitee_cp_core.id_
        dl.save(case)

        proposal = em_propose_embargo_activity(
            embargo=embargo,
            context=case.id_,
            actor=_INVITEE,
            id_=f"{case_id}/proposals/p5",
        )
        dl.create(proposal)
        case.pending_embargo_proposal_index[embargo_id] = proposal.id_
        dl.save(case)

        event = _make_accept_event(proposal, case, _COORD, make_payload)
        AcceptInviteToEmbargoOnCaseReceivedUseCase(dl, event).execute()

        # Normal path: no lapse, acceptance proceeds
        fresh_case = dl.read(case_id)
        assert isinstance(fresh_case, CoreCase)
        assert fresh_case.current_status.em.state == EM.ACTIVE

    def test_lapse_creates_distinct_ledger_entry(self, make_payload):
        """Late Accept after lapse creates a ledger entry distinct from Reject (CM-28-009)."""
        from vultron.core.models.case_ledger_entry import CaseLedgerEntry

        dl = _make_dl(actor_id=_COORD)
        case_id = "https://example.org/cases/ea6"
        embargo_id = "https://example.org/cases/ea6/embargos/e6"

        case, embargo, _ = _make_active_embargo_case(
            dl,
            case_id,
            embargo_id,
            invitee_pec=PEC.INVITED,
            invitee_deadline=_PAST,
        )

        proposal = em_propose_embargo_activity(
            embargo=embargo,
            context=case.id_,
            actor=_COORD,
            to=[_INVITEE],
            id_=f"{case_id}/proposals/p6",
        )
        dl.create(proposal)

        event = _make_accept_event(proposal, case, _INVITEE, make_payload)
        AcceptInviteToEmbargoOnCaseReceivedUseCase(dl, event).execute()

        # A CaseLedgerEntry with event_type "invite_to_embargo_on_case_lapsed"
        # must exist (CM-28-005, CM-28-009).
        ledger_entries = [
            obj
            for obj in dl.list_objects("CaseLedgerEntry")
            if isinstance(obj, CaseLedgerEntry) and obj.case_id == case_id
        ]
        lapse_entries = [
            e
            for e in ledger_entries
            if e.event_type == "invite_to_embargo_on_case_lapsed"
        ]
        assert lapse_entries, (
            "Expected a CaseLedgerEntry with event_type"
            " 'invite_to_embargo_on_case_lapsed' but none found"
        )
        lapse_entry = lapse_entries[0]
        # Entry must be distinguishable from an explicit Reject
        assert lapse_entry.event_type != "reject_invite_to_embargo_on_case"
        # payloadSnapshot must be non-empty (CLP-07-001)
        assert lapse_entry.payload_snapshot
