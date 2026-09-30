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


"""record_participant_consent — PEC-only operations that leave EM state alone
(consent.py)."""

from typing import cast

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.services.embargo_lifecycle import (
    EmbargoLifecycle,
)
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC, PEC_Trigger
from vultron.errors import VultronInvalidStateTransitionError
from vultron.wire.as2.vocab.base.objects.actors import as_Service

from .conftest import (
    _make_actor,
    _make_case,
    _make_embargo,
)


def test_record_participant_consent_accept_trigger(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """ACCEPT trigger moves INVITED participant to SIGNATORY."""
    owner, dl = owner_and_dl
    case, participants = _make_case(dl, owner.id_, em_state=EM.PROPOSED)
    owner_participant_id = participants[0].id_
    embargo = _make_embargo(dl, case.id_)

    # Set owner participant to INVITED so ACCEPT is valid
    owner_p = cast(CaseParticipant, dl.read(owner_participant_id))
    object.__setattr__(owner_p, "embargo_consent_state", PEC.INVITED)
    dl.save(owner_p)

    lifecycle = EmbargoLifecycle(persistence=dl)
    result = lifecycle.record_participant_consent(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=owner.id_,
        pec_trigger=PEC_Trigger.ACCEPT,
    )

    assert result.case_changed is False
    assert result.case_embargo_changed is False

    refreshed = cast(CaseParticipant, dl.read(owner_participant_id))
    assert refreshed.embargo_consent_state == PEC.SIGNATORY.value
    assert embargo.id_ in refreshed.accepted_embargo_ids


def test_record_participant_consent_decline_trigger(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """DECLINE trigger moves LAPSED participant to DECLINED and removes embargo ID."""
    owner, dl = owner_and_dl
    case, participants = _make_case(dl, owner.id_, em_state=EM.PROPOSED)
    owner_participant_id = participants[0].id_
    embargo = _make_embargo(dl, case.id_)

    # Seed as LAPSED (SIGNATORY → LAPSED after revise) with accepted embargo
    owner_p = cast(CaseParticipant, dl.read(owner_participant_id))
    object.__setattr__(owner_p, "embargo_consent_state", PEC.LAPSED)
    owner_p.accepted_embargo_ids = [embargo.id_]
    dl.save(owner_p)

    lifecycle = EmbargoLifecycle(persistence=dl)
    lifecycle.record_participant_consent(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=owner.id_,
        pec_trigger=PEC_Trigger.DECLINE,
    )

    refreshed = cast(CaseParticipant, dl.read(owner_participant_id))
    assert refreshed.embargo_consent_state == PEC.DECLINED.value
    assert embargo.id_ not in refreshed.accepted_embargo_ids


def test_record_participant_consent_actor_not_in_case(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Actor without a CaseParticipant: result has no pec changes, no crash."""
    owner, dl = owner_and_dl
    outsider = _make_actor(dl, "Outsider Org")
    case, _ = _make_case(dl, owner.id_, em_state=EM.PROPOSED)
    embargo = _make_embargo(dl, case.id_)

    lifecycle = EmbargoLifecycle(persistence=dl)
    result = lifecycle.record_participant_consent(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=outsider.id_,  # not in case
        pec_trigger=PEC_Trigger.ACCEPT,
    )

    assert result.participant_changes == []
    assert result.case_changed is False


def test_record_participant_consent_illegal_trigger_raises(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """AC-5: illegal trigger raises VultronInvalidStateTransitionError.

    ACCEPT from SIGNATORY is not a valid PEC transition.
    apply_pec_transition() is fail-closed and raises; this test pins that
    behavior and confirms record_participant_consent propagates it.
    """
    owner, dl = owner_and_dl
    case, participants = _make_case(dl, owner.id_, em_state=EM.PROPOSED)
    owner_participant_id = participants[0].id_
    embargo = _make_embargo(dl, case.id_)

    owner_p = cast(CaseParticipant, dl.read(owner_participant_id))
    object.__setattr__(owner_p, "embargo_consent_state", PEC.SIGNATORY)
    dl.save(owner_p)

    lifecycle = EmbargoLifecycle(persistence=dl)
    with pytest.raises(VultronInvalidStateTransitionError):
        lifecycle.record_participant_consent(
            case_id=case.id_,
            embargo_id=embargo.id_,
            actor_id=owner.id_,
            pec_trigger=PEC_Trigger.ACCEPT,  # illegal from SIGNATORY
        )
