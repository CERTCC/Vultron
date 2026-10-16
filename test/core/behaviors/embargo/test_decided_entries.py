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

"""Turning a staged embargo decision into its entries (#4715, ADR-0124).

``decide_on_stage`` reads what a lifecycle operation would have written and
turns it into the act's own change and one entry per other changed row; it
raises when the entries could not carry the decision, and refuses an answer
whose stated row the case cannot take.
"""

from typing import cast

import pytest

from test.core.behaviors.embargo.nodes.conftest import (
    CASE_MANAGER_ACTOR,
    OTHER_PARTICIPANT_ACTOR,
    make_case_with_manager,
)
from vultron.core.behaviors.embargo.decided_entries import (
    consent_row_changes,
    decide_embargo_act,
    decide_on_stage,
)
from vultron.core.behaviors.embargo_case_file import read_embargo_case_file
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_apply import (
    ConsentRowChange,
    ConsentRowVerb,
    EmbargoCaseFile,
    RegisterStep,
    RegisterStepKind,
)
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.services.embargo_lifecycle import EmbargoLifecycle
from vultron.core.services.embargo_lifecycle.staged_persistence import (
    StagedCasePersistence,
)
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.errors import VultronBTInternalError, VultronEntryRefusedError
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

_S = EmbargoConsentState


def _proposed(suffix: str) -> tuple[VulnerabilityCase, CasePersistence, str]:
    """A PROPOSED case whose participants hold UNINVITED rows for it."""
    case, _cm, dl = make_case_with_manager(
        suffix, em_state=EM.PROPOSED, other_consent=None
    )
    embargo_id = case.proposed_embargo_ids[0]
    return case, dl, embargo_id


def _answer(embargo_id: str, *, accept: bool = True) -> ConsentRowChange:
    return ConsentRowChange.answer(
        embargo_id=embargo_id,
        actor_id=OTHER_PARTICIPANT_ACTOR,
        accept=accept,
    )


def _accept_by_other(case_id: str, embargo_id: str):
    def _decide(staged: CasePersistence) -> object:
        return EmbargoLifecycle(persistence=staged).accept_embargo_invite(
            case_id=case_id,
            embargo_id=embargo_id,
            actor_id=OTHER_PARTICIPANT_ACTOR,
        )

    return _decide


class TestConsentRowChanges:
    def test_a_new_row_is_a_create_and_a_changed_row_an_update(self):
        case, dl, embargo_id = _proposed("dec-rows")
        before = read_embargo_case_file(dl, case.id_)
        other = before.participants[OTHER_PARTICIPANT_ACTOR]
        manager = before.participants[CASE_MANAGER_ACTOR]
        changed = other.model_copy(deep=True)
        changed.copy_consent_row(
            EmbargoConsent(
                embargo_id=embargo_id,
                state=_S.AGREED,
                attributed_to=OTHER_PARTICIPANT_ACTOR,
            )
        )
        created = manager.model_copy(deep=True)
        created.copy_consent_row(
            EmbargoConsent(
                embargo_id=f"{case.id_}/embargo_events/new",
                state=_S.UNINVITED,
                attributed_to=CASE_MANAGER_ACTOR,
            )
        )
        after = EmbargoCaseFile(
            case=before.case,
            participants={
                CASE_MANAGER_ACTOR: created,
                OTHER_PARTICIPANT_ACTOR: changed,
            },
        )

        changes = consent_row_changes(before, after)

        # Roster order: the manager first, as the case indexes it.
        assert [(c.verb, c.actor_id) for c in changes] == [
            (ConsentRowVerb.CREATE, CASE_MANAGER_ACTOR),
            (ConsentRowVerb.UPDATE, OTHER_PARTICIPANT_ACTOR),
        ]

    def test_a_participant_the_act_created_is_a_fault(self):
        case, dl, _ = _proposed("dec-new-participant")
        before = read_embargo_case_file(dl, case.id_)
        stranger = CaseParticipant(
            attributed_to="https://example.org/actors/stranger",
            context=case.id_,
        )
        after = EmbargoCaseFile(
            case=before.case,
            participants={
                **before.participants,
                "https://example.org/actors/stranger": stranger,
            },
        )
        trimmed = EmbargoCaseFile(
            case=before.case,
            participants={
                k: v
                for k, v in before.participants.items()
                if k != OTHER_PARTICIPANT_ACTOR
            },
        )

        with pytest.raises(VultronBTInternalError, match="created a"):
            consent_row_changes(trimmed, after)


class TestDecideOnStage:
    @pytest.mark.spec("CLP-07-013")
    def test_an_answer_becomes_the_acts_own_change(self):
        case, dl, embargo_id = _proposed("dec-answer")

        decision = decide_embargo_act(
            dl,
            case.id_,
            _accept_by_other(case.id_, embargo_id),
            answer=_answer(embargo_id),
        )

        assert decision.act == _answer(embargo_id)
        assert decision.rows == ()

    def test_an_answer_already_in_place_has_no_change(self):
        case, dl, embargo_id = _proposed("dec-in-place")
        decide = _accept_by_other(case.id_, embargo_id)
        staged = StagedCasePersistence(dl)
        decide(staged)
        staged.flush()  # the row is AGREED already

        decision = decide_embargo_act(
            dl, case.id_, decide, answer=_answer(embargo_id)
        )

        assert decision.act is None
        assert decision.rows == ()

    def test_an_answer_the_case_cannot_take_is_refused(self):
        case, dl, _ = _proposed("dec-unknown")
        stranger = f"{case.id_}/embargo_events/stranger"

        with pytest.raises(VultronEntryRefusedError, match="records no"):
            decide_embargo_act(
                dl,
                case.id_,
                _accept_by_other(case.id_, stranger),
                answer=_answer(stranger),
            )

    def test_an_answer_written_otherwise_than_stated_is_a_fault(self):
        case, dl, embargo_id = _proposed("dec-mismatch")

        with pytest.raises(VultronBTInternalError, match="not as"):
            decide_embargo_act(
                dl,
                case.id_,
                _accept_by_other(case.id_, embargo_id),
                answer=_answer(embargo_id, accept=False),
            )

    def test_a_step_and_an_answer_together_are_a_fault(self):
        case, dl, embargo_id = _proposed("dec-both")

        with pytest.raises(VultronBTInternalError, match="not both"):
            decide_on_stage(
                dl,
                StagedCasePersistence(dl),
                case.id_,
                RegisterStep(kind=RegisterStepKind.REJECT, embargo=embargo_id),
                _answer(embargo_id),
            )

    def test_a_register_change_no_step_carries_is_a_fault(self):
        """The operation moved the register, but the caller named no step."""
        case, dl, embargo_id = _proposed("dec-no-step")

        def _reject(staged: CasePersistence) -> object:
            return EmbargoLifecycle(
                persistence=staged
            ).reject_embargo_proposal(
                case_id=case.id_,
                embargo_id=embargo_id,
                actor_id=CASE_MANAGER_ACTOR,
            )

        with pytest.raises(VultronBTInternalError, match="do not carry"):
            decide_embargo_act(dl, case.id_, _reject)

    def test_a_step_that_does_not_apply_is_a_fault(self):
        """The named step is not the one the operation took."""
        case, dl, embargo_id = _proposed("dec-wrong-step")

        def _reject(staged: CasePersistence) -> object:
            return EmbargoLifecycle(
                persistence=staged
            ).reject_embargo_proposal(
                case_id=case.id_,
                embargo_id=embargo_id,
                actor_id=CASE_MANAGER_ACTOR,
            )

        with pytest.raises(VultronBTInternalError, match="do not apply"):
            decide_embargo_act(
                dl,
                case.id_,
                _reject,
                RegisterStep(
                    kind=RegisterStepKind.CANCEL, embargo=f"{embargo_id}-x"
                ),
            )

    def test_a_write_no_entry_can_carry_is_a_fault(self):
        case, dl, _ = _proposed("dec-stray")

        def _stray(staged: CasePersistence) -> object:
            staged.create(
                as_EmbargoEvent(
                    id_=f"{case.id_}/embargo_events/stray",
                    context=case.id_,
                    end_time=days_from_now_utc(10),
                )
            )
            return None

        with pytest.raises(VultronBTInternalError, match="no embargo entry"):
            decide_embargo_act(dl, case.id_, _stray)

    def test_a_row_on_an_unindexed_record_is_dropped_and_logged(
        self, caplog: pytest.LogCaptureFixture
    ):
        """A record the case lists but does not index is outside the case
        file no entry can name; its row is dropped, with a WARNING."""
        case, dl, embargo_id = _proposed("dec-unindexed")
        orphan = CaseParticipant(
            id_=f"{case.id_}/participants/orphan",
            attributed_to="https://example.org/actors/orphan",
            context=case.id_,
        )
        dl.create(orphan)
        stored = cast(VulnerabilityCase, dl.read(case.id_))
        stored.case_participants = [*stored.case_participants, orphan.id_]
        dl.save(stored)

        def _write_orphan(staged: CasePersistence) -> object:
            record = cast(CaseParticipant, staged.read(orphan.id_))
            record.write_uninvited_rows([embargo_id])
            staged.save(record)
            return None

        with caplog.at_level("WARNING"):
            decision = decide_embargo_act(dl, case.id_, _write_orphan)

        assert (decision.act, decision.rows) == (None, ())
        assert any(orphan.id_ in r.getMessage() for r in caplog.records)
