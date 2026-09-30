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
participant's PEC state, ``embargo_adherence``, ``accepted_embargo_ids``,
and that ``find_excluded_actor_ids`` (the CM-10-004 content gate, which
reads the list) agrees with the scalar state about who is a signatory to
the active embargo.

One store, three actors.  Every trigger here runs against the case's
canonical store, which is the state the CASE_MANAGER's adjudication of each
answer produces (EP-09-005; the relay that carries a non-manager's answer to
it is #3913).  A trigger's BT follows the requesting actor's store when that
actor is hosted alongside the store's owner, so the three actors are given
ids under distinct authorities to keep every trigger in this one store.
The proposal is indexed here by hand for the same reason: indexing a
relayed proposal at the CASE_MANAGER is the relay's job.
"""

from datetime import timedelta
from typing import cast

import pytest

from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.behaviors.case.update_support import find_excluded_actor_ids
from vultron.core.models._helpers import now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC
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
            embargo_consent_state=PEC.SIGNATORY,
            accepted_embargo_ids=[self.active.id_],
        )
        owner_p.add_role(CVDRole.CASE_MANAGER)
        proposer_p = FinderParticipant(
            attributed_to=PROPOSER,
            context=self.case.id_,
            embargo_consent_state=PEC.SIGNATORY,
            accepted_embargo_ids=[self.active.id_],
        )
        third_p = VendorParticipant(
            attributed_to=THIRD,
            context=self.case.id_,
            embargo_consent_state=PEC.SIGNATORY,
            accepted_embargo_ids=[self.active.id_],
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
        """The proposer proposes revision B ending *days* from now; returns B's id."""
        result = SvcProposeEmbargoRevisionUseCase(
            self.dl,
            ProposeEmbargoRevisionTriggerRequest(
                actor_id=PROPOSER,
                case_id=self.case.id_,
                end_time=now_utc() + timedelta(days=days),
            ),
            trigger_activity=TriggerActivityAdapter(self.dl),
        ).execute()
        activity = result["activity"]
        revision_id = str(activity["object"]["id"])
        proposal_id = str(activity["id"])
        # The CASE_MANAGER indexes a relayed proposal (EP-09-001; #3913).
        case = self.read_case()
        case.pending_embargo_proposal_index = {
            **case.pending_embargo_proposal_index,
            revision_id: proposal_id,
        }
        self.dl.save(case)
        return revision_id

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
        ).execute()

    # -- the reads ---------------------------------------------------------

    def read_case(self) -> VulnerabilityCase:
        return cast(VulnerabilityCase, self.dl.read(self.case.id_))

    def consent(self) -> dict[str, tuple[str, bool, list[str]]]:
        """``{actor: (pec_state, embargo_adherence, accepted_embargo_ids)}``."""
        out: dict[str, tuple[str, bool, list[str]]] = {}
        for actor_id, participant_id in self.participants.items():
            p = cast(CaseParticipant, self.dl.read(participant_id))
            status = p.participant_status
            assert status is not None
            out[actor_id] = (
                p.embargo_consent_state,
                status.embargo_adherence,
                list(p.accepted_embargo_ids),
            )
        return out

    def assert_gate_agrees_with_state(self) -> None:
        """``find_excluded_actor_ids`` (list-based) matches the scalar state.

        The content gate excludes an actor whose list lacks the active
        embargo; the scalar says an actor is bound iff SIGNATORY.  The two
        must name the same actors (the disagreement was Concern #3884).
        """
        excluded = find_excluded_actor_ids(self.read_case(), self.dl)
        not_signatory = {
            actor
            for actor, (state, _adherence, _ids) in self.consent().items()
            if state != PEC.SIGNATORY.value
        }
        assert excluded == not_signatory


@pytest.fixture()
def revision():
    scenario = _Revision()
    try:
        yield scenario
    finally:
        scenario.close()


def _assert_all_signatories_to(
    revision: _Revision, embargo_id: str, *, extra_ids: dict[str, list[str]]
) -> None:
    for actor, (state, adherence, ids) in revision.consent().items():
        assert state == PEC.SIGNATORY.value, actor
        assert adherence is True, actor
        assert embargo_id in ids, actor
        for extra in extra_ids.get(actor, []):
            assert extra in ids, (actor, extra)


@pytest.mark.spec("EP-05-002")
@pytest.mark.spec("MSM-07-005")
def test_proposing_a_revision_changes_nobodys_consent(revision: _Revision):
    """ACTIVE → REVISE: everyone stays a signatory to A; the proposer's list gains B."""
    a = revision.active.id_
    b = revision.propose_revision(days=90)

    assert revision.read_case().current_status.em.state == EM.REVISE
    consent = revision.consent()
    assert consent[OWNER] == (PEC.SIGNATORY.value, True, [a])
    assert consent[PROPOSER] == (PEC.SIGNATORY.value, True, [a, b])
    assert consent[THIRD] == (PEC.SIGNATORY.value, True, [a])
    revision.assert_gate_agrees_with_state()


@pytest.mark.spec("EP-05-001")
@pytest.mark.spec("MSM-07-005")
@pytest.mark.spec("MSM-07-003")
@pytest.mark.spec("CM-10-001")
def test_accepted_shorter_revision_carries_every_signatory_over(
    revision: _Revision,
):
    """ACTIVE → REVISE → ACTIVE under shorter B: nobody lapses, everyone holds B."""
    a = revision.active.id_
    b = revision.propose_revision(days=30)
    revision.assert_gate_agrees_with_state()

    revision.owner_accepts(b)

    case = revision.read_case()
    assert case.current_status.em.state == EM.ACTIVE
    assert case.active_embargo_id == b
    assert case.proposed_embargoes == []
    assert case.pending_embargo_proposal_index == {}
    _assert_all_signatories_to(revision, b, extra_ids={OWNER: [a], THIRD: [a]})
    revision.assert_gate_agrees_with_state()


@pytest.mark.spec("EP-05-001")
@pytest.mark.spec("MSM-07-005")
@pytest.mark.spec("CM-18-002")
@pytest.mark.spec("CM-18-001")
def test_accepted_longer_revision_lapses_only_the_silent_signatory(
    revision: _Revision,
):
    """ACTIVE → REVISE → ACTIVE under longer B: the third party, who never
    answered, lapses; the proposer (consented by proposing) and the owner
    (consented by accepting) stay signatories."""
    a = revision.active.id_
    b = revision.propose_revision(days=90)

    revision.owner_accepts(b)

    case = revision.read_case()
    assert case.current_status.em.state == EM.ACTIVE
    assert case.active_embargo_id == b
    consent = revision.consent()
    assert consent[OWNER] == (PEC.SIGNATORY.value, True, [a, b])
    assert consent[PROPOSER] == (PEC.SIGNATORY.value, True, [a, b])
    assert consent[THIRD] == (PEC.LAPSED.value, False, [a])
    # The gate excludes exactly the lapsed party: its list lacks B.
    assert find_excluded_actor_ids(case, revision.dl) == {THIRD}
    revision.assert_gate_agrees_with_state()


@pytest.mark.spec("MSM-07-004")
@pytest.mark.spec("EP-05-002")
def test_rejected_revision_strands_nobody(revision: _Revision):
    """ACTIVE → REVISE → ACTIVE by EJ: A stays in force; no record changes."""
    a = revision.active.id_
    b = revision.propose_revision(days=90)
    before = revision.consent()

    revision.owner_rejects(b)

    case = revision.read_case()
    assert case.current_status.em.state == EM.ACTIVE
    assert case.active_embargo_id == a
    assert case.proposed_embargoes == []
    assert case.pending_embargo_proposal_index == {}
    assert revision.consent() == before
    for actor, (state, adherence, _ids) in before.items():
        assert state == PEC.SIGNATORY.value, actor
        assert adherence is True, actor
    assert find_excluded_actor_ids(case, revision.dl) == set()
    revision.assert_gate_agrees_with_state()
