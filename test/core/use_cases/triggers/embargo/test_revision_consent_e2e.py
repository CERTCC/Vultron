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

"""Consent through a full revision cycle, end to end through the trigger use
cases (ADR-0093 as revised for #3884; EP-05, MSM-07).

``ACTIVE → REVISE → ACTIVE`` three ways — an accepted shorter revision, an
accepted longer revision, a rejected revision — on a case with an owner, a
proposer and a silent third signatory, asserting after every step each
participant's consent rows (one per embargo, ADR-0122), and that
``find_excluded_actor_ids`` (the CM-10-004 content gate) agrees with the
derived ``is_signatory`` / ``has_lapsed`` answers about who is bound by the
active embargo.

One store, three actors.  Every trigger here runs against the case's
canonical store, whose owner is the CASE_MANAGER.  The proposer is not, so
its revision trigger only asks (EP-09-008): the queued ``Invite`` is routed
back into the store as the owner's inbox would route it, and the owner's
adjudication moves the case to REVISE and indexes the proposal (EP-09-001).
The owner then answers by trigger as the CASE_MANAGER.  A trigger's BT
follows the requesting actor's store when that actor is hosted alongside the
store's owner, so the three actors are given ids under distinct authorities
to keep every trigger in this one store.
"""

import inspect
from datetime import timedelta
from typing import cast

import pytest

from test.support.trigger_results import activity_of
from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.adapters.outbox_sealed_body import read_sealed_body_dict
from vultron.core.behaviors.case.update_support import find_excluded_actor_ids
from vultron.core.models._helpers import now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.core.use_cases.triggers.embargo import (
    SvcAcceptEmbargoUseCase,
    SvcProposeEmbargoRevisionUseCase,
    SvcRejectEmbargoUseCase,
)
from vultron.core.use_cases.triggers.requests import (
    AcceptEmbargoTriggerRequest,
    ProposeEmbargoRevisionTriggerRequest,
    RejectEmbargoTriggerRequest,
)
from vultron.enums.roles import CVDRole
from vultron.semantic_registry import extract_event, use_case_map
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import (
    FinderParticipant,
    VendorParticipant,
)
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

OWNER = "https://owner.example/actors/owner"
PROPOSER = "https://proposer.example/actors/proposer"
THIRD = "https://third.example/actors/third"
ACTORS = (OWNER, PROPOSER, THIRD)

ACTIVE_DAYS = 45


class _Revision:
    """One store, one case under active embargo A, three signatories to A."""

    def __init__(self) -> None:
        reset_datalayer(OWNER)
        self.dl = SqliteDataLayer("sqlite:///:memory:", actor_id=OWNER)
        self.dl.clear_all()
        for actor_id in ACTORS:
            self.dl.create(as_Service(id_=actor_id, name=actor_id))

        self.case = VulnerabilityCase(
            name="Revision consent case", attributed_to=OWNER
        )
        self.active = as_EmbargoEvent(
            context=self.case.id_,
            end_time=now_utc() + timedelta(days=ACTIVE_DAYS),
        )
        owner_p = VendorParticipant(
            attributed_to=OWNER,
            context=self.case.id_,
            embargo_consents=[
                EmbargoConsent(
                    embargo_id=self.active.id_,
                    state=EmbargoConsentState.ACCEPTED,
                )
            ],
        )
        owner_p.add_role(CVDRole.CASE_MANAGER)
        proposer_p = FinderParticipant(
            attributed_to=PROPOSER,
            context=self.case.id_,
            embargo_consents=[
                EmbargoConsent(
                    embargo_id=self.active.id_,
                    state=EmbargoConsentState.ACCEPTED,
                )
            ],
        )
        third_p = VendorParticipant(
            attributed_to=THIRD,
            context=self.case.id_,
            embargo_consents=[
                EmbargoConsent(
                    embargo_id=self.active.id_,
                    state=EmbargoConsentState.ACCEPTED,
                )
            ],
        )
        self.participants = {
            OWNER: owner_p.id_,
            PROPOSER: proposer_p.id_,
            THIRD: third_p.id_,
        }
        self.case.case_participants = [
            owner_p.id_,
            proposer_p.id_,
            third_p.id_,
        ]
        self.case.actor_participant_index = dict(self.participants)
        self.case.append_case_status(em_state=EM.ACTIVE)
        self.case.set_embargo(self.active.id_)
        self.dl.create(self.case)
        self.dl.create(self.active)
        for p in (owner_p, proposer_p, third_p):
            self.dl.create(p)

    def close(self) -> None:
        self.dl.close()
        reset_datalayer(OWNER)

    # -- the steps ---------------------------------------------------------

    def propose_revision(self, *, days: int) -> str:
        """The proposer proposes revision B ending *days* from now; returns B's id.

        The proposer is not the CASE_MANAGER, so its trigger only asks
        (EP-09-008); the owner's adjudication of the queued ``Invite`` is what
        moves the case to REVISE and indexes the proposal (EP-09-001).
        """
        result = SvcProposeEmbargoRevisionUseCase(
            self.dl,
            ProposeEmbargoRevisionTriggerRequest(
                actor_id=PROPOSER,
                case_id=self.case.id_,
                end_time=now_utc() + timedelta(days=days),
            ),
            trigger_activity=TriggerActivityAdapter(self.dl),
            sync_port=SyncActivityAdapter(self.dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()
        activity = activity_of(result)
        assert activity["to"] == [OWNER]
        self._receive_as_owner(str(activity["id"]))
        return str(activity["object"]["id"])

    def _receive_as_owner(self, activity_id: str) -> None:
        """Route a queued activity into the case's store as the inbox would."""
        body = read_sealed_body_dict(self.dl, activity_id)
        assert body is not None, f"'{activity_id}' was never sealed"
        event = extract_event(parse_activity(body)).model_copy(
            update={"receiving_actor_id": OWNER}
        )
        use_case = use_case_map()[event.semantic_type]
        offered: dict[str, object] = {
            "sync_port": SyncActivityAdapter(self.dl),
            "trigger_activity": TriggerActivityAdapter(self.dl),
            "wire_render_port": As2WireRenderAdapter(),
        }
        accepted = inspect.signature(use_case).parameters
        ports = {k: v for k, v in offered.items() if k in accepted}
        verdict = use_case(self.dl, event, **ports).execute()
        assert verdict.disposition is HandlerDisposition.APPLIED, (
            verdict.reason
        )

    def owner_accepts(self, revision_id: str) -> None:
        proposal_id = self.read_case().pending_embargo_proposal_index[
            revision_id
        ]
        SvcAcceptEmbargoUseCase(
            self.dl,
            AcceptEmbargoTriggerRequest(
                actor_id=OWNER, case_id=self.case.id_, proposal_id=proposal_id
            ),
            trigger_activity=TriggerActivityAdapter(self.dl),
            sync_port=SyncActivityAdapter(self.dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

    def owner_rejects(self, revision_id: str) -> None:
        proposal_id = self.read_case().pending_embargo_proposal_index[
            revision_id
        ]
        SvcRejectEmbargoUseCase(
            self.dl,
            RejectEmbargoTriggerRequest(
                actor_id=OWNER, case_id=self.case.id_, proposal_id=proposal_id
            ),
            trigger_activity=TriggerActivityAdapter(self.dl),
            sync_port=SyncActivityAdapter(self.dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

    # -- the reads ---------------------------------------------------------

    def read_case(self) -> VulnerabilityCase:
        return cast(VulnerabilityCase, self.dl.read(self.case.id_))

    def consent(self) -> dict[str, dict[str, EmbargoConsentState]]:
        """``{actor: {embargo_id: row state}}`` for every participant."""
        return {
            actor_id: {
                row.embargo_id: row.state
                for row in cast(
                    CaseParticipant, self.dl.read(participant_id)
                ).embargo_consents
            }
            for actor_id, participant_id in self.participants.items()
        }

    def participant(self, actor_id: str) -> CaseParticipant:
        return cast(CaseParticipant, self.dl.read(self.participants[actor_id]))

    def signatories(self) -> set[str]:
        """Actors whose row for the active embargo is ACCEPTED."""
        active_id = self.read_case().active_embargo_id
        return {
            actor
            for actor in self.participants
            if self.participant(actor).is_signatory(active_id)
        }

    def assert_gate_agrees_with_rows(self) -> None:
        """``find_excluded_actor_ids`` names exactly the non-signatories.

        The content gate and the derived signatory lookup both read the
        consent row for the active embargo, so they cannot disagree (the
        disagreement between a list and a scalar was Concern #3884).
        """
        excluded = find_excluded_actor_ids(self.read_case(), self.dl)
        assert excluded == set(self.participants) - self.signatories()


@pytest.fixture()
def revision():
    scenario = _Revision()
    try:
        yield scenario
    finally:
        scenario.close()


def _assert_all_signatories_to(revision: _Revision, embargo_id: str) -> None:
    assert revision.read_case().active_embargo_id == embargo_id
    assert revision.signatories() == set(ACTORS)
    for actor, rows in revision.consent().items():
        assert rows[embargo_id] == EmbargoConsentState.ACCEPTED, actor
        assert not revision.participant(actor).has_lapsed(embargo_id), actor


_ACCEPTED = EmbargoConsentState.ACCEPTED
_INVITED = EmbargoConsentState.INVITED


@pytest.mark.spec("EP-05-002")
@pytest.mark.spec("MSM-07-005")
def test_proposing_a_revision_changes_nobodys_consent(revision: _Revision):
    """ACTIVE -> REVISE: everyone stays a signatory to A; the proposer gains an ACCEPTED row for B and
    the asked signatory an INVITED one (its row for A is kept, EP-09-004)."""
    a = revision.active.id_
    b = revision.propose_revision(days=90)

    assert revision.read_case().current_status.em.state == EM.REVISE
    consent = revision.consent()
    assert consent[OWNER] == {a: _ACCEPTED}
    assert consent[PROPOSER] == {a: _ACCEPTED, b: _ACCEPTED}
    assert consent[THIRD] == {a: _ACCEPTED, b: _INVITED}
    assert revision.signatories() == set(ACTORS)
    revision.assert_gate_agrees_with_rows()


@pytest.mark.spec("EP-05-001")
@pytest.mark.spec("MSM-07-005")
@pytest.mark.spec("MSM-07-003")
@pytest.mark.spec("CM-10-001")
def test_accepted_shorter_revision_carries_every_signatory_over(
    revision: _Revision,
):
    """ACTIVE -> REVISE -> ACTIVE under shorter B: nobody lapses, everyone holds B."""
    a = revision.active.id_
    b = revision.propose_revision(days=30)
    revision.assert_gate_agrees_with_rows()

    revision.owner_accepts(b)

    case = revision.read_case()
    assert case.current_status.em.state == EM.ACTIVE
    assert case.active_embargo_id == b
    assert case.proposed_embargoes == []
    assert case.pending_embargo_proposal_index == {}
    _assert_all_signatories_to(revision, b)
    for rows in revision.consent().values():
        assert rows[a] == _ACCEPTED
    revision.assert_gate_agrees_with_rows()


@pytest.mark.spec("EP-05-001")
@pytest.mark.spec("MSM-07-005")
@pytest.mark.spec("CM-18-002")
@pytest.mark.spec("CM-18-001")
def test_accepted_longer_revision_lapses_only_the_silent_signatory(
    revision: _Revision,
):
    """ACTIVE -> REVISE -> ACTIVE under longer B: the third party, who never
    answered, lapses (derived: an ACCEPTED row for A, none for B); the proposer
    (consented by proposing) and the owner (consented by accepting) stay
    signatories."""
    a = revision.active.id_
    b = revision.propose_revision(days=90)

    revision.owner_accepts(b)

    case = revision.read_case()
    assert case.current_status.em.state == EM.ACTIVE
    assert case.active_embargo_id == b
    consent = revision.consent()
    assert consent[OWNER] == {a: _ACCEPTED, b: _ACCEPTED}
    assert consent[PROPOSER] == {a: _ACCEPTED, b: _ACCEPTED}
    assert consent[THIRD] == {a: _ACCEPTED, b: _INVITED}
    assert revision.participant(THIRD).has_lapsed(b)
    assert not revision.participant(THIRD).is_signatory(b)
    assert revision.signatories() == {OWNER, PROPOSER}
    # The gate excludes exactly the lapsed party: it has no accepting row for B.
    assert find_excluded_actor_ids(case, revision.dl) == {THIRD}
    revision.assert_gate_agrees_with_rows()


@pytest.mark.spec("MSM-07-004")
@pytest.mark.spec("EP-05-002")
def test_rejected_revision_strands_nobody(revision: _Revision):
    """ACTIVE -> REVISE -> ACTIVE by EJ: A stays in force; no signatory is lost."""
    a = revision.active.id_
    b = revision.propose_revision(days=90)
    before = revision.consent()

    revision.owner_rejects(b)

    case = revision.read_case()
    assert case.current_status.em.state == EM.ACTIVE
    assert case.active_embargo_id == a
    assert case.proposed_embargoes == []
    assert case.pending_embargo_proposal_index == {}
    # Every row for A is untouched; the owner's rejection of a proposal while
    # A is in force writes nothing (ADR-0122).
    after = revision.consent()
    for actor in ACTORS:
        assert after[actor][a] == before[actor][a] == _ACCEPTED, actor
    assert revision.signatories() == set(ACTORS)
    assert find_excluded_actor_ids(case, revision.dl) == set()
    revision.assert_gate_agrees_with_rows()
