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

The operations' own tests cover these through ``propose_embargo`` (REVISE
cascade), ``terminate_active_embargo`` (RESET cascade) and accept/reject
(single-actor consent).  These pin the contract of the shared helpers
directly, so a change to the cascade filter or the actor lookup fails here
by name rather than somewhere in a transition test.
"""

import logging
from typing import cast

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.services.embargo_lifecycle import EmbargoLifecycle
from vultron.core.states.participant_embargo_consent import PEC
from vultron.wire.as2.vocab.base.objects.actors import as_Service

from .conftest import _make_actor, _make_case


def _force_pec(dl: SqliteDataLayer, participant_id: str, state: PEC) -> None:
    participant = cast(CaseParticipant, dl.read(participant_id))
    object.__setattr__(participant, "embargo_consent_state", state)
    dl.save(participant)


def _pec_of(dl: SqliteDataLayer, participant_id: str) -> str:
    return cast(CaseParticipant, dl.read(participant_id)).embargo_consent_state


def test_cascade_pec_revise_moves_only_signatories(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """REVISE cascade lapses SIGNATORY participants and leaves every other state."""
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
    changes = lifecycle._cascade_pec_revise(case)

    assert [c.participant_id for c in changes] == [signer_p.id_]
    assert changes[0].pec_before == PEC.SIGNATORY.value
    assert _pec_of(dl, signer_p.id_) == PEC.LAPSED.value
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
    participant = cast(CaseParticipant, dl.read(owner_p.id_))
    assert participant.accepted_embargo_ids == [embargo_id]
