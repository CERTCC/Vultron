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

"""initialize_creation_embargo (creation.py): propose + activate, one commit.

At case creation the PROPOSE and ACCEPT triggers are applied together and
only ``EM.ACTIVE`` is persisted (EP-04-002).  The consent records, the owner's
SIGNATORY seed and a contested creation's revision commit with it, so any
refusal or fault leaves the case at ``EM.NONE`` for a redelivered proposal to
finish (EP-04-012, #4123, #4142).
"""

from typing import cast

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.pending_creation_time_revision_relay import (
    PendingCreationTimeRevisionRelay,
)
from vultron.core.models.protocols import PersistableModel
from vultron.core.services.embargo_lifecycle import EmbargoLifecycle
from vultron.core.services.embargo_lifecycle.creation import (
    CreationRevision,
)
from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC
from vultron.errors import (
    VultronError,
    VultronInvalidStateTransitionError,
    VultronNotFoundError,
    VultronValidationError,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

from .conftest import (
    _accepted_ids_of,
    _force_pec,
    _make_actor,
    _make_case,
    _make_embargo,
    _pec_of,
    _record_save_many,
)

pytestmark = [pytest.mark.spec("EP-04-002"), pytest.mark.spec("EP-04-012")]


def _stored_case(dl: SqliteDataLayer, case_id: str) -> VulnerabilityCase:
    return cast(VulnerabilityCase, dl.read(case_id))


def _assert_untouched(dl: SqliteDataLayer, case_id: str) -> None:
    case = _stored_case(dl, case_id)
    assert case.current_status.em.state == EM.NONE
    assert case.active_embargo_id is None
    assert case.proposed_embargoes == []


def _unstored_embargo(context: str, days: int = 45) -> as_EmbargoEvent:
    """An ``EmbargoEvent`` the store does not hold yet."""
    return as_EmbargoEvent(context=context, end_time=days_from_now_utc(days))


def test_none_to_active_in_one_commit(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, dl = owner_and_dl
    case, (owner_p,) = _make_case(dl, owner.id_)
    embargo = _make_embargo(dl, case.id_)
    saved_states: list[EM] = []
    commits: list[list[str]] = []
    save, save_many = dl.save, dl.save_many

    def recording_save(obj: PersistableModel) -> None:
        commits.append([obj.id_])
        save(obj)

    def recording_save_many(objs: list[PersistableModel]) -> None:
        commits.append([obj.id_ for obj in objs])
        saved_states.extend(
            obj.current_status.em.state
            for obj in objs
            if isinstance(obj, VulnerabilityCase)
        )
        save_many(objs)

    monkeypatch.setattr(dl, "save", recording_save)
    monkeypatch.setattr(dl, "save_many", recording_save_many)

    result = EmbargoLifecycle(persistence=dl).initialize_creation_embargo(
        case_id=case.id_, embargo=embargo, actor_id=owner.id_
    )

    # EM.PROPOSED is never handed to the store (EP-04-002), and the owner's
    # consent goes in the same commit as the case (#4142).
    assert saved_states == [EM.ACTIVE]
    assert commits == [[case.id_, owner_p.id_]]
    assert (result.em_before, result.em_after) == (EM.NONE, EM.ACTIVE)
    stored = _stored_case(dl, case.id_)
    assert stored.current_status.em.state == EM.ACTIVE
    assert stored.active_embargo_id == embargo.id_
    # Activation decides the proposal at once, so none is left open.
    assert stored.proposed_embargoes == []


def test_consent_matches_propose_then_activate(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """The proposer records its consent; every holder becomes SIGNATORY.

    Same effects as ``propose_embargo`` followed by ``activate_embargo``
    (ADR-0093, EP-05-001): a participant that did not propose is untouched.
    """
    owner, dl = owner_and_dl
    other = _make_actor(dl, "Finder")
    case, (owner_p, other_p) = _make_case(
        dl, owner.id_, extra_participant_ids=[other.id_]
    )
    embargo = _make_embargo(dl, case.id_)

    EmbargoLifecycle(persistence=dl).initialize_creation_embargo(
        case_id=case.id_, embargo=embargo, actor_id=owner.id_
    )

    assert _accepted_ids_of(dl, owner_p.id_) == [embargo.id_]
    assert _pec_of(dl, owner_p.id_) == PEC.SIGNATORY.value
    assert _accepted_ids_of(dl, other_p.id_) == []
    assert _pec_of(dl, other_p.id_) == PEC.UNBOUND.value


@pytest.mark.spec("CM-14-003")
def test_a_non_participant_proposer_still_has_the_owner_seeded(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """The CASE_MANAGER on the creation path need not be a participant.

    It records no consent of its own; the owner is read from the case
    (``attributed_to``) and seeded SIGNATORY of the terms it set.
    """
    owner, dl = owner_and_dl
    case, (owner_p,) = _make_case(dl, owner.id_)
    embargo = _make_embargo(dl, case.id_)

    result = EmbargoLifecycle(persistence=dl).initialize_creation_embargo(
        case_id=case.id_,
        embargo=embargo,
        actor_id="https://example.org/actors/not-a-participant",
    )

    assert _stored_case(dl, case.id_).active_embargo_id == embargo.id_
    owner_record = cast(CaseParticipant, dl.read(owner_p.id_))
    assert owner_record.accepted_embargo_ids == [embargo.id_]
    assert owner_record.embargo_consent_state == PEC.SIGNATORY.value
    assert [c.participant_id for c in result.participant_changes] == [
        owner_p.id_
    ]


@pytest.mark.spec("CM-14-003")
@pytest.mark.spec("CM-13-005")
def test_an_owner_already_signatory_stays_signatory(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Seeding is idempotent: no ``ACCEPT`` from SIGNATORY, no raise."""
    owner, dl = owner_and_dl
    case, (owner_p,) = _make_case(dl, owner.id_)
    _force_pec(dl, owner_p.id_, PEC.SIGNATORY)
    embargo = _make_embargo(dl, case.id_)

    EmbargoLifecycle(persistence=dl).initialize_creation_embargo(
        case_id=case.id_, embargo=embargo, actor_id=owner.id_
    )

    assert _pec_of(dl, owner_p.id_) == PEC.SIGNATORY.value
    assert _accepted_ids_of(dl, owner_p.id_) == [embargo.id_]


@pytest.mark.spec("CM-14-003")
@pytest.mark.spec("CM-18-003")
def test_a_declined_owner_records_nothing_until_re_invited(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """``ACCEPT`` is not legal from DECLINED, so the owner seed records
    nothing: the case still activates, and the owner keeps its decline and an
    empty accepted list until it is re-invited (CM-18-003)."""
    owner, dl = owner_and_dl
    case, (owner_p,) = _make_case(dl, owner.id_)
    _force_pec(dl, owner_p.id_, PEC.DECLINED)
    embargo = _make_embargo(dl, case.id_)

    result = EmbargoLifecycle(persistence=dl).initialize_creation_embargo(
        case_id=case.id_,
        embargo=embargo,
        actor_id="https://example.org/actors/not-a-participant",
    )

    assert _stored_case(dl, case.id_).active_embargo_id == embargo.id_
    assert _pec_of(dl, owner_p.id_) == PEC.DECLINED.value
    assert _accepted_ids_of(dl, owner_p.id_) == []
    assert owner_p.id_ not in [
        c.participant_id for c in result.participant_changes
    ]


@pytest.mark.spec("CM-14-002")
@pytest.mark.parametrize("unseedable", ["no_owner", "no_record"])
def test_an_owner_without_a_participant_record_is_refused_unchanged(
    owner_and_dl: tuple[as_Service, SqliteDataLayer], unseedable: str
) -> None:
    """No owner to seed is a broken precondition, refused before any write."""
    owner, dl = owner_and_dl
    case, (owner_p,) = _make_case(dl, owner.id_)
    if unseedable == "no_owner":
        case.attributed_to = None
    else:
        case.actor_participant_index = {}
    dl.save(case)
    embargo = _make_embargo(dl, case.id_)

    with pytest.raises(VultronNotFoundError, match="for owner"):
        EmbargoLifecycle(persistence=dl).initialize_creation_embargo(
            case_id=case.id_, embargo=embargo, actor_id=owner.id_
        )

    _assert_untouched(dl, case.id_)
    assert _accepted_ids_of(dl, owner_p.id_) == []


@pytest.mark.parametrize(
    "em_state", [state for state in EM if state != EM.NONE]
)
def test_a_case_that_has_left_none_is_refused_unchanged(
    owner_and_dl: tuple[as_Service, SqliteDataLayer], em_state: EM
) -> None:
    """Creation runs only from NONE — PROPOSE then ACCEPT is also legal from
    ACTIVE (via REVISE), so the machine alone would not refuse it."""
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_, em_state=em_state)
    embargo = _make_embargo(dl, case.id_)

    with pytest.raises(VultronInvalidStateTransitionError, match="not NONE"):
        EmbargoLifecycle(persistence=dl).initialize_creation_embargo(
            case_id=case.id_, embargo=embargo, actor_id=owner.id_
        )

    stored = _stored_case(dl, case.id_)
    assert stored.current_status.em.state == em_state
    assert stored.active_embargo_id is None


def test_a_none_case_with_an_attached_embargo_is_refused_unchanged(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Creation never replaces an attached embargo, even at NONE (CSB-16)."""
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_)
    attached = _make_embargo(dl, case.id_)
    case.set_embargo(attached.id_)
    dl.save(case)
    embargo = _make_embargo(dl, case.id_)

    with pytest.raises(
        VultronInvalidStateTransitionError, match="already attached"
    ):
        EmbargoLifecycle(persistence=dl).initialize_creation_embargo(
            case_id=case.id_, embargo=embargo, actor_id=owner.id_
        )

    stored = _stored_case(dl, case.id_)
    assert stored.current_status.em.state == EM.NONE
    assert stored.active_embargo_id == attached.id_


def test_a_stale_proposed_listing_is_discarded_in_the_same_write(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Activation decides the proposal that carried the id (EP-08-003)."""
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_)
    embargo = _make_embargo(dl, case.id_)
    case.proposed_embargoes = [*case.proposed_embargoes, embargo.id_]
    dl.save(case)

    EmbargoLifecycle(persistence=dl).initialize_creation_embargo(
        case_id=case.id_, embargo=embargo, actor_id=owner.id_
    )

    stored = _stored_case(dl, case.id_)
    assert stored.active_embargo_id == embargo.id_
    assert stored.proposed_embargoes == []


@pytest.mark.spec("EMB-01-002")
def test_pxa_set_is_refused_before_any_write(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_)
    case.append_case_status(pxa_state=CS_pxa.Pxa)
    dl.save(case)
    embargo = _make_embargo(dl, case.id_)

    with pytest.raises(VultronInvalidStateTransitionError):
        EmbargoLifecycle(persistence=dl).initialize_creation_embargo(
            case_id=case.id_, embargo=embargo, actor_id=owner.id_
        )

    _assert_untouched(dl, case.id_)


@pytest.mark.spec("EMB-18-003")
def test_an_unstored_embargo_is_stored_in_the_activating_commit(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The event is written by the commit that activates it, with the case
    (#4182): the record being activated is held when the case names it."""
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_)
    embargo = _unstored_embargo(case.id_)
    batches = _record_save_many(dl, monkeypatch)

    EmbargoLifecycle(persistence=dl).initialize_creation_embargo(
        case_id=case.id_, embargo=embargo, actor_id=owner.id_
    )

    (batch,) = batches
    assert embargo.id_ in [obj.id_ for obj in batch]
    assert case.id_ in [obj.id_ for obj in batch]
    assert dl.read(embargo.id_) is not None
    assert _stored_case(dl, case.id_).active_embargo_id == embargo.id_


def test_a_failed_commit_leaves_no_embargo_event_behind(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nothing is stored before the commit, so a run that stops first leaves
    no event for a redelivery that resolves otherwise to orphan (#4182)."""
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_)
    embargo = _unstored_embargo(case.id_)

    with monkeypatch.context() as patch:
        _fail_save_many(dl, patch)
        with pytest.raises(VultronError, match="forced store fault"):
            EmbargoLifecycle(persistence=dl).initialize_creation_embargo(
                case_id=case.id_, embargo=embargo, actor_id=owner.id_
            )

    _assert_untouched(dl, case.id_)
    assert dl.read(embargo.id_) is None


def test_an_embargo_about_another_subject_is_refused_before_any_write(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_)
    embargo = _unstored_embargo("https://example.org/reports/not-the-case")

    with pytest.raises(VultronValidationError):
        EmbargoLifecycle(persistence=dl).initialize_creation_embargo(
            case_id=case.id_, embargo=embargo, actor_id=owner.id_
        )

    _assert_untouched(dl, case.id_)
    assert dl.read(embargo.id_) is None


def test_a_different_object_at_the_embargo_id_is_refused_before_any_write(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    owner, dl = owner_and_dl
    case, (owner_p,) = _make_case(dl, owner.id_)
    held = _make_embargo(dl, "https://example.org/cases/some-other-case")
    clash = as_EmbargoEvent(
        id_=held.id_, context=case.id_, end_time=held.end_time
    )

    with pytest.raises(VultronError, match="already held"):
        EmbargoLifecycle(persistence=dl).initialize_creation_embargo(
            case_id=case.id_, embargo=clash, actor_id=owner.id_
        )

    _assert_untouched(dl, case.id_)
    assert _accepted_ids_of(dl, owner_p.id_) == []


# -- the post-activation effects commit with the activation (#4142) ----------


def _fail_save_many(
    dl: SqliteDataLayer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The one transaction fails, as ``save_many`` does: nothing is written."""

    def failing_save_many(objs: list[PersistableModel]) -> None:
        raise VultronError("forced store fault")

    monkeypatch.setattr(dl, "save_many", failing_save_many)


def test_a_failed_commit_writes_nothing_and_a_rerun_completes(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, dl = owner_and_dl
    case, (owner_p,) = _make_case(dl, owner.id_)
    embargo = _make_embargo(dl, case.id_)

    with monkeypatch.context() as patch:
        _fail_save_many(dl, patch)
        with pytest.raises(VultronError, match="forced store fault"):
            EmbargoLifecycle(persistence=dl).initialize_creation_embargo(
                case_id=case.id_, embargo=embargo, actor_id=owner.id_
            )

    _assert_untouched(dl, case.id_)
    assert _accepted_ids_of(dl, owner_p.id_) == []

    EmbargoLifecycle(persistence=dl).initialize_creation_embargo(
        case_id=case.id_, embargo=embargo, actor_id=owner.id_
    )

    assert _stored_case(dl, case.id_).active_embargo_id == embargo.id_
    assert _pec_of(dl, owner_p.id_) == PEC.SIGNATORY.value


def _revision(case_id: str, days: int = 90) -> as_EmbargoEvent:
    """A losing creation-time proposal, not yet stored."""
    return _unstored_embargo(case_id, days)


def _creation_revision(
    case_id: str, revision: as_EmbargoEvent, proposer_id: str
) -> CreationRevision:
    """*revision*, proposed by *proposer_id*, with the relay it owes."""
    return CreationRevision(
        embargo=revision,
        proposer_id=proposer_id,
        relay=PendingCreationTimeRevisionRelay(
            case_id=case_id,
            embargo_id=revision.id_,
            proposal_id="urn:uuid:00000000-0000-4000-8000-000000004156",
            losing_source="actor_default",
            report_id="https://example.org/reports/r-1",
            case_actor_id="https://example.org/actors/case-manager",
        ),
    )


@pytest.mark.spec("EP-04-003")
def test_a_revision_is_stored_and_proposed_in_the_same_commit(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, dl = owner_and_dl
    case, (owner_p,) = _make_case(dl, owner.id_)
    embargo = _make_embargo(dl, case.id_)
    revision = _revision(case.id_)
    batches = _record_save_many(dl, monkeypatch)

    result = EmbargoLifecycle(persistence=dl).initialize_creation_embargo(
        case_id=case.id_,
        embargo=embargo,
        actor_id=owner.id_,
        revision=_creation_revision(case.id_, revision, owner.id_),
    )

    assert [{obj.id_ for obj in batch} for batch in batches] == [
        {
            case.id_,
            owner_p.id_,
            revision.id_,
            PendingCreationTimeRevisionRelay.build_id(case.id_),
        }
    ]
    assert (result.em_before, result.em_after) == (EM.NONE, EM.REVISE)
    stored = _stored_case(dl, case.id_)
    assert stored.current_status.em.state == EM.REVISE
    assert stored.active_embargo_id == embargo.id_
    assert stored.proposed_embargoes == [revision.id_]
    assert isinstance(dl.read(revision.id_), as_EmbargoEvent)
    # The owner both proposed the revision and is seeded on the active
    # terms: one record carries both through the commit (MSM-07-005).
    assert _pec_of(dl, owner_p.id_) == PEC.SIGNATORY.value
    assert _accepted_ids_of(dl, owner_p.id_) == [embargo.id_, revision.id_]


@pytest.mark.spec("MSM-07-005")
def test_the_revision_is_consented_to_by_its_proposer_not_the_executor(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """The reporter's lost terms land on the reporter's record (#4152).

    The CASE_MANAGER path runs the initialization as someone other than
    either party, so the executing actor is not who proposed the revision.
    """
    owner, dl = owner_and_dl
    reporter_id = "https://example.org/actors/reporter"
    executor_id = "https://example.org/actors/case-manager"
    case, (owner_p, reporter_p) = _make_case(
        dl, owner.id_, extra_participant_ids=[reporter_id]
    )
    embargo = _make_embargo(dl, case.id_)
    revision = _revision(case.id_)

    EmbargoLifecycle(persistence=dl).initialize_creation_embargo(
        case_id=case.id_,
        embargo=embargo,
        actor_id=executor_id,
        revision=_creation_revision(case.id_, revision, reporter_id),
    )

    assert _accepted_ids_of(dl, reporter_p.id_) == [revision.id_]
    # Proposing changes no consent state (EP-05-002).
    assert _pec_of(dl, reporter_p.id_) == PEC.UNBOUND.value
    assert _accepted_ids_of(dl, owner_p.id_) == [embargo.id_]


@pytest.mark.spec("EP-04-003")
def test_a_failed_revision_commit_leaves_the_revision_unstored(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_)
    embargo = _make_embargo(dl, case.id_)
    revision = _revision(case.id_)

    with monkeypatch.context() as patch:
        _fail_save_many(dl, patch)
        with pytest.raises(VultronError, match="forced store fault"):
            EmbargoLifecycle(persistence=dl).initialize_creation_embargo(
                case_id=case.id_,
                embargo=embargo,
                actor_id=owner.id_,
                revision=_creation_revision(case.id_, revision, owner.id_),
            )

    _assert_untouched(dl, case.id_)
    assert dl.read(revision.id_) is None
    # EP-04-011: the relay is owed only with the revision it relays (#4156).
    assert dl.read(PendingCreationTimeRevisionRelay.build_id(case.id_)) is None


@pytest.mark.spec("EP-04-004")
def test_a_revision_id_held_by_other_terms_is_refused_unchanged(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """A stored twin that is not this revision is refused, not overwritten."""
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_)
    embargo = _make_embargo(dl, case.id_)
    held = _make_embargo(dl, case.id_, days=10)
    revision = as_EmbargoEvent(
        id_=held.id_, context=case.id_, end_time=days_from_now_utc(90)
    )

    with pytest.raises(VultronError, match="already held"):
        EmbargoLifecycle(persistence=dl).initialize_creation_embargo(
            case_id=case.id_,
            embargo=embargo,
            actor_id=owner.id_,
            revision=_creation_revision(case.id_, revision, owner.id_),
        )

    _assert_untouched(dl, case.id_)
    stored_held = dl.read(held.id_)
    assert isinstance(stored_held, as_EmbargoEvent)
    assert stored_held.end_time == held.end_time
