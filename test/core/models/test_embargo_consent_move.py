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

"""The consent row a trigger leaves, as a change an entry carries (#4716).

:func:`consent_row_move` writes nothing and reads only the case file; the
row it names applies through the one apply function.  :func:`owner_agreement`
and :func:`joiner_agreement` are what an owner's activation and an invitee's
stub ``Accept`` state, decided the same way on every node (CM-23-016).
"""

import pytest

from test.support.embargo_register import activate, propose
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_apply import (
    ConsentRowVerb,
    EmbargoCaseFile,
    apply_embargo_change,
)
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.embargo_consent_move import (
    consent_row_move,
    joiner_agreement,
    owner_agreement,
)
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
    PEC_Trigger,
)
from vultron.errors import VultronNotFoundError

CASE_ID = "https://example.org/cases/move"
OWNER = "https://example.org/actors/owner"
JOINER = "https://example.org/actors/joiner"
E1 = f"{CASE_ID}/embargoes/1"
E2 = f"{CASE_ID}/embargoes/2"

_S = EmbargoConsentState


def _case_file(
    *, active: str | None = E1, proposed: tuple[str, ...] = (E2,), **rows
) -> EmbargoCaseFile:
    """A case owned by OWNER with JOINER on the roster.

    *rows* maps ``owner``/``joiner`` to ``{embargo_id: state}``; every other
    register entry's row is ``UNINVITED``.
    """
    case = VulnerabilityCase(id_=CASE_ID, attributed_to=OWNER)
    if active:
        activate(case, active)
    propose(case, *proposed)
    participants = {}
    for name, actor_id in (("owner", OWNER), ("joiner", JOINER)):
        held = rows.get(name, {})
        record = CaseParticipant(
            id_=f"{CASE_ID}/participants/{name}",
            attributed_to=actor_id,
            context=CASE_ID,
            embargo_consents=[
                EmbargoConsent(embargo_id=e, state=held.get(e, _S.UNINVITED))
                for e in (e.embargo_id for e in case.embargo_register)
            ],
        )
        case.actor_participant_index[actor_id] = record.id_
        participants[actor_id] = record
    return EmbargoCaseFile(case=case, participants=participants)


class TestConsentRowMove:
    @pytest.mark.spec("CM-18-003")
    def test_names_the_row_the_trigger_leaves(self):
        case_file = _case_file(joiner={E2: _S.INVITED})

        change = consent_row_move(case_file, JOINER, E2, PEC_Trigger.AGREE)

        assert change is not None
        assert change.verb is ConsentRowVerb.UPDATE
        assert change.row.state is _S.AGREED
        assert change.row.attributed_to == JOINER
        assert change.row.id_ == EmbargoConsent.build_id(E2, JOINER)
        # It applies through the one apply function as named.
        after = apply_embargo_change(case_file, change)
        assert after.participants[JOINER].consent_for(E2) is _S.AGREED

    def test_writes_nothing(self):
        case_file = _case_file(joiner={E2: _S.INVITED})
        before = case_file.participants[JOINER].model_dump()

        consent_row_move(case_file, JOINER, E2, PEC_Trigger.AGREE)

        assert case_file.participants[JOINER].model_dump() == before

    @pytest.mark.spec("CM-18-003")
    def test_an_illegal_trigger_moves_nothing(self):
        case_file = _case_file(joiner={E2: _S.AGREED})

        assert (
            consent_row_move(case_file, JOINER, E2, PEC_Trigger.TIME_OUT)
            is None
        )

    @pytest.mark.spec("CM-18-003")
    def test_a_final_entry_moves_nothing(self):
        """E1 is superseded once E2 is activated: its rows are frozen."""
        case_file = _case_file(proposed=(E2,))
        activate(case_file.case, E2)

        assert (
            consent_row_move(case_file, JOINER, E1, PEC_Trigger.AGREE) is None
        )

    def test_an_unknown_actor_or_embargo_moves_nothing(self):
        case_file = _case_file()

        assert (
            consent_row_move(
                case_file,
                "https://example.org/actors/nobody",
                E2,
                PEC_Trigger.AGREE,
            )
            is None
        )
        assert (
            consent_row_move(
                case_file, JOINER, f"{CASE_ID}/embargoes/9", PEC_Trigger.AGREE
            )
            is None
        )

    @pytest.mark.spec("CM-18-005")
    def test_a_missing_row_for_a_register_entry_raises(self):
        """Every entry has a row on every participant (ADR-0122)."""
        case_file = _case_file()
        joiner = case_file.participants[JOINER]
        stripped = joiner.model_copy(
            update={
                "embargo_consents": [
                    r for r in joiner.embargo_consents if r.embargo_id != E2
                ]
            }
        )
        case_file = EmbargoCaseFile(
            case=case_file.case,
            participants={**case_file.participants, JOINER: stripped},
        )

        with pytest.raises(VultronNotFoundError):
            consent_row_move(case_file, JOINER, E2, PEC_Trigger.AGREE)

    @pytest.mark.spec("CM-28-013")
    def test_a_move_out_of_invited_drops_the_deadline(self):
        case_file = _case_file(joiner={E2: _S.INVITED})

        change = consent_row_move(case_file, JOINER, E2, PEC_Trigger.TIME_OUT)

        assert change is not None
        assert change.row.state is _S.TIMED_OUT
        assert change.row.rsvp_deadline is None


class TestOwnerAgreement:
    @pytest.mark.spec("MSM-07-008")
    @pytest.mark.parametrize("held", [_S.UNINVITED, _S.INVITED, _S.DECLINED])
    def test_the_owners_row_is_agreed(self, held):
        """A DECLINED row moves too: activating is changing the answer."""
        case_file = _case_file(owner={E2: held})

        change = owner_agreement(case_file, E2)

        assert change is not None
        assert change.actor_id == OWNER
        assert change.row.state is _S.AGREED

    @pytest.mark.spec("MSM-07-008")
    def test_an_agreed_owner_moves_nothing(self):
        assert owner_agreement(_case_file(owner={E2: _S.AGREED}), E2) is None

    def test_an_owner_off_the_roster_moves_nothing(self):
        """A partial replica that holds no owner record (ADR-0087)."""
        case_file = _case_file()
        case_file = EmbargoCaseFile(
            case=case_file.case,
            participants={JOINER: case_file.participants[JOINER]},
        )

        assert owner_agreement(case_file, E2) is None


class TestJoinerAgreement:
    @pytest.mark.spec("CM-10-001")
    @pytest.mark.parametrize("held", [_S.UNINVITED, _S.INVITED, _S.TIMED_OUT])
    def test_the_joiner_agrees_to_the_embargo_in_force(self, held):
        change = joiner_agreement(_case_file(joiner={E1: held}), JOINER)

        assert change is not None
        assert change.row.embargo_id == E1
        assert change.row.state is _S.AGREED

    @pytest.mark.spec("CM-18-003")
    @pytest.mark.parametrize("held", [_S.AGREED, _S.DECLINED])
    def test_an_answered_row_is_left_as_it_is(self, held):
        """Seeding never overrides an answer the participant gave."""
        assert joiner_agreement(_case_file(joiner={E1: held}), JOINER) is None

    def test_no_embargo_in_force_moves_nothing(self):
        case_file = _case_file(active=None)

        assert joiner_agreement(case_file, JOINER) is None

    @pytest.mark.spec("CM-18-005")
    def test_a_missing_row_for_the_embargo_in_force_raises(self):
        """Every entry has a row on every participant (ADR-0122)."""
        case_file = _case_file()
        joiner = case_file.participants[JOINER]
        stripped = joiner.model_copy(
            update={
                "embargo_consents": [
                    r for r in joiner.embargo_consents if r.embargo_id != E1
                ]
            }
        )
        case_file = EmbargoCaseFile(
            case=case_file.case,
            participants={**case_file.participants, JOINER: stripped},
        )

        with pytest.raises(VultronNotFoundError):
            joiner_agreement(case_file, JOINER)
