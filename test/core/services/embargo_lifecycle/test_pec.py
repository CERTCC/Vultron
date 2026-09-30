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

"""The PEC side-effect helpers shared by the EM operations (``pec.py``).

The operations' own tests cover these through ``accept_embargo_invite`` and
``activate_embargo`` (the revision-activation cascade, EP-05-001),
``terminate_active_embargo`` (RESET cascade) and accept/reject
(single-actor consent).  These pin the contract of the shared helpers
directly, so a change to the cascade filter or the actor lookup fails here
by name rather than somewhere in a transition test.
"""

import logging

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.services.embargo_lifecycle import EmbargoLifecycle
from vultron.core.states.participant_embargo_consent import PEC
from vultron.errors import VultronValidationError
from vultron.wire.as2.vocab.base.objects.actors import as_Service

from .conftest import (
    _accepted_ids_of,
    _force_pec,
    _make_actor,
    _make_case,
    _make_embargo,
    _pec_of,
    _seed_consent,
)


@pytest.mark.spec("EP-05-001")
@pytest.mark.spec("CM-18-002")
def test_cascade_pec_revise_lapses_only_signatories_lacking_the_revision(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """The REVISE cascade is keyed on the revised embargo, not on state alone.

    Run at *activation* of longer terms (EP-05-001): a SIGNATORY whose
    ``accepted_embargo_ids`` lacks the revised id lapses; a SIGNATORY that
    already accepted it stays; every other state is untouched.
    """
    owner, dl = owner_and_dl
    signer = _make_actor(dl, "Signer")
    accepted = _make_actor(dl, "Accepted")
    invitee = _make_actor(dl, "Invitee")
    case, participants = _make_case(
        dl,
        owner.id_,
        extra_participant_ids=[signer.id_, accepted.id_, invitee.id_],
    )
    owner_p, signer_p, accepted_p, invitee_p = participants
    active = _make_embargo(dl, case.id_)
    revision = _make_embargo(dl, case.id_, days=90)
    _seed_consent(dl, signer_p.id_, PEC.SIGNATORY, [active.id_])
    _seed_consent(
        dl, accepted_p.id_, PEC.SIGNATORY, [active.id_, revision.id_]
    )
    _force_pec(dl, invitee_p.id_, PEC.INVITED)

    lifecycle = EmbargoLifecycle(persistence=dl)
    changes = lifecycle._cascade_pec_revise(
        case, revised_embargo_id=revision.id_
    )

    assert [c.participant_id for c in changes] == [signer_p.id_]
    assert changes[0].pec_before == PEC.SIGNATORY.value
    assert _pec_of(dl, signer_p.id_) == PEC.LAPSED.value
    assert _pec_of(dl, accepted_p.id_) == PEC.SIGNATORY.value
    assert _pec_of(dl, invitee_p.id_) == PEC.INVITED.value
    assert _pec_of(dl, owner_p.id_) == PEC.UNBOUND.value


def test_cascade_pec_reset_skips_unbound_and_resets_the_rest(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """RESET cascade returns every non-UNBOUND participant to UNBOUND."""
    owner, dl = owner_and_dl
    signer = _make_actor(dl, "Signer")
    invitee = _make_actor(dl, "Invitee")
    case, participants = _make_case(
        dl, owner.id_, extra_participant_ids=[signer.id_, invitee.id_]
    )
    owner_p, signer_p, invitee_p = participants
    _force_pec(dl, signer_p.id_, PEC.SIGNATORY)
    _force_pec(dl, invitee_p.id_, PEC.INVITED)

    lifecycle = EmbargoLifecycle(persistence=dl)
    changes = lifecycle._cascade_pec_reset(case)

    assert {c.participant_id for c in changes} == {signer_p.id_, invitee_p.id_}
    for p in participants:
        assert _pec_of(dl, p.id_) == PEC.UNBOUND.value


def test_participant_for_actor_unknown_actor_warns_and_returns_none(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An actor with no participant record yields None and a WARNING naming the purpose."""
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_)
    lifecycle = EmbargoLifecycle(persistence=dl)

    with caplog.at_level(
        logging.WARNING, logger="vultron.core.services.embargo_lifecycle"
    ):
        resolved = lifecycle._participant_for_actor(
            case, "https://example.org/actors/stranger", "acceptance"
        )

    assert resolved is None
    assert any(
        "cannot record embargo acceptance" in r.getMessage()
        for r in caplog.records
    )


def test_record_actor_pec_acceptance_is_idempotent_for_signatory(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """A SIGNATORY re-accepting the same embargo changes nothing and reports nothing."""
    owner, dl = owner_and_dl
    case, (owner_p,) = _make_case(dl, owner.id_)
    lifecycle = EmbargoLifecycle(persistence=dl)
    embargo_id = "https://example.org/embargoes/e1"

    first = lifecycle._record_actor_pec_acceptance(case, owner.id_, embargo_id)
    second = lifecycle._record_actor_pec_acceptance(
        case, owner.id_, embargo_id
    )

    assert [c.pec_after for c in first] == [PEC.SIGNATORY.value]
    assert second == []
    assert _accepted_ids_of(dl, owner_p.id_) == [embargo_id]


@pytest.mark.spec("MSM-07-003")
def test_record_actor_pec_acceptance_without_advance_records_the_id_only(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """``advance=False`` writes the list and leaves the state — and reports nothing.

    A list-only write is not a consent *state* change, so it is persisted
    but does not appear in ``participant_changes``.
    """
    owner, dl = owner_and_dl
    case, (owner_p,) = _make_case(dl, owner.id_)
    _force_pec(dl, owner_p.id_, PEC.INVITED)
    lifecycle = EmbargoLifecycle(persistence=dl)
    embargo_id = "https://example.org/embargoes/proposed"

    changes = lifecycle._record_actor_pec_acceptance(
        case, owner.id_, embargo_id, advance=False
    )

    assert changes == []
    assert _pec_of(dl, owner_p.id_) == PEC.INVITED.value
    assert _accepted_ids_of(dl, owner_p.id_) == [embargo_id]


@pytest.mark.spec("MSM-07-004")
@pytest.mark.spec("CM-18-003")
def test_record_actor_pec_rejection_withdrawal_declines_a_signatory(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Rejecting the active embargo is withdrawal: SIGNATORY → DECLINED, id dropped."""
    owner, dl = owner_and_dl
    case, (owner_p,) = _make_case(dl, owner.id_)
    embargo_id = "https://example.org/embargoes/active"
    _seed_consent(dl, owner_p.id_, PEC.SIGNATORY, [embargo_id])
    lifecycle = EmbargoLifecycle(persistence=dl)

    changes = lifecycle._record_actor_pec_rejection(
        case, owner.id_, embargo_id, withdrawal=True
    )

    assert [(c.pec_before, c.pec_after) for c in changes] == [
        (PEC.SIGNATORY.value, PEC.DECLINED.value)
    ]
    assert _accepted_ids_of(dl, owner_p.id_) == []


@pytest.mark.spec("MSM-07-004")
def test_record_actor_pec_rejection_of_proposed_terms_keeps_a_signatory(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Refusing proposed terms drops the id but leaves a SIGNATORY bound."""
    owner, dl = owner_and_dl
    case, (owner_p,) = _make_case(dl, owner.id_)
    active_id = "https://example.org/embargoes/active"
    proposed_id = "https://example.org/embargoes/proposed"
    _seed_consent(dl, owner_p.id_, PEC.SIGNATORY, [active_id, proposed_id])
    lifecycle = EmbargoLifecycle(persistence=dl)

    changes = lifecycle._record_actor_pec_rejection(
        case, owner.id_, proposed_id, withdrawal=False
    )

    assert changes == []
    assert _pec_of(dl, owner_p.id_) == PEC.SIGNATORY.value
    assert _accepted_ids_of(dl, owner_p.id_) == [active_id]


@pytest.mark.spec("MSM-07-004")
def test_record_actor_pec_rejection_of_proposed_terms_declines_a_non_signatory(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """A participant not yet bound has no consent for the refusal to leave intact."""
    owner, dl = owner_and_dl
    case, (owner_p,) = _make_case(dl, owner.id_)
    _force_pec(dl, owner_p.id_, PEC.INVITED)
    lifecycle = EmbargoLifecycle(persistence=dl)

    changes = lifecycle._record_actor_pec_rejection(
        case, owner.id_, "https://example.org/embargoes/p", withdrawal=False
    )

    assert [c.pec_after for c in changes] == [PEC.DECLINED.value]


def test_assert_rejectable_classifies_active_proposed_and_unknown(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """A Reject names the active embargo, an open proposal, or nothing the case knows."""
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_)
    active = _make_embargo(dl, case.id_)
    proposed = _make_embargo(dl, case.id_, days=60)
    stranger = _make_embargo(dl, case.id_, days=10)
    case.active_embargo = active.id_
    case.proposed_embargoes = [proposed.id_]
    dl.save(case)

    assert EmbargoLifecycle._assert_rejectable(case, active.id_) is True
    assert EmbargoLifecycle._assert_rejectable(case, proposed.id_) is False
    with pytest.raises(VultronValidationError, match="neither the active"):
        EmbargoLifecycle._assert_rejectable(case, stranger.id_)
