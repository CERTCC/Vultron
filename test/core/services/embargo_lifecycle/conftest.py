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


"""Shared fixtures and builders for the ``EmbargoLifecycle`` service tests.

One test module per submodule of ``vultron/core/services/embargo_lifecycle/``
(CS-18-004); the builders here are what every one of them starts from.
"""

from collections.abc import Generator
from datetime import datetime
from typing import cast

import pytest

from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import (
    CaseParticipant,
    FinderParticipant,
    VendorParticipant,
)
from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

# imported for vocabulary registration side-effect
from vultron.wire.as2.vocab.objects.vulnerability_case import (  # noqa: F401
    as_VulnerabilityCase,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_actor(dl: SqliteDataLayer, name: str) -> as_Service:
    actor = as_Service(name=name)
    dl.create(actor)
    return actor


def _make_case(
    dl: SqliteDataLayer,
    owner_id: str,
    extra_participant_ids: list[str] | None = None,
    em_state: EM = EM.NONE,
) -> tuple[VulnerabilityCase, list[CaseParticipant]]:
    """Create a VulnerabilityCase with an owner participant.

    Returns the case and the list of CaseParticipant objects created.
    """
    case = VulnerabilityCase(
        name="Test embargo case",
        attributed_to=owner_id,
    )
    case.append_case_status(em_state=em_state)

    owner_participant = VendorParticipant(
        attributed_to=owner_id,
        context=case.id_,
        embargo_consent_state=PEC.UNBOUND,
    )
    owner_participant.add_role(CVDRole.CASE_MANAGER)

    participants: list[CaseParticipant] = [owner_participant]
    case.case_participants = [owner_participant.id_]
    case.actor_participant_index = {owner_id: owner_participant.id_}

    for pid in extra_participant_ids or []:
        p = FinderParticipant(
            attributed_to=pid,
            context=case.id_,
            embargo_consent_state=PEC.UNBOUND,
        )
        case.case_participants.append(p.id_)
        case.actor_participant_index[pid] = p.id_
        participants.append(p)

    dl.create(case)
    for participant in participants:
        dl.create(participant)

    return case, participants


def _make_embargo(
    dl: SqliteDataLayer,
    case_id: str,
    *,
    days: int = 45,
    end_time: datetime | None = None,
) -> as_EmbargoEvent:
    """Persist an ``EmbargoEvent`` ending *days* from now (the A-vs-B knob).

    Pass *end_time* to pin the terms exactly — two calls with the same *days*
    are minted at two instants and so end a second apart whenever a second
    boundary falls between them, which is not the "equal terms" a tie test
    means.
    """
    embargo = as_EmbargoEvent(
        context=case_id, end_time=end_time or days_from_now_utc(days)
    )
    dl.create(embargo)
    return embargo


def _force_pec(dl: SqliteDataLayer, participant_id: str, state: PEC) -> None:
    """Seed a PEC state directly — test setup only, never a consent write."""
    participant = cast(CaseParticipant, dl.read(participant_id))
    object.__setattr__(participant, "embargo_consent_state", state)
    dl.save(participant)


def _pec_of(dl: SqliteDataLayer, participant_id: str) -> str:
    return cast(CaseParticipant, dl.read(participant_id)).embargo_consent_state


def _accepted_ids_of(dl: SqliteDataLayer, participant_id: str) -> list[str]:
    return list(
        cast(CaseParticipant, dl.read(participant_id)).accepted_embargo_ids
    )


def _seed_consent(
    dl: SqliteDataLayer,
    participant_id: str,
    state: PEC,
    accepted: list[str],
) -> None:
    """Seed a participant's PEC state and accepted-embargo list together."""
    _force_pec(dl, participant_id, state)
    participant = cast(CaseParticipant, dl.read(participant_id))
    participant.accepted_embargo_ids = list(accepted)
    dl.save(participant)


#: An embargo id no store in these tests ever holds (EMB-18-003).
UNHELD_EMBARGO_ID = "https://example.org/embargoes/never-stored"


def _case_awaiting_activation(
    dl: SqliteDataLayer,
    owner_id: str,
    *,
    replaces: bool,
    activated_id: str,
) -> tuple[VulnerabilityCase, CaseParticipant, str | None]:
    """A case about to activate *activated_id*, which the store may not hold.

    With *replaces* the case is in ``REVISE`` with a readable active embargo
    the owner has signed (a revision); otherwise it is ``PROPOSED`` with no
    active embargo (a first activation).  *activated_id* is recorded as the
    open proposal either way.  Returns the case, the owner's participant and
    the active embargo id (``None`` on a first activation).
    """
    case, participants = _make_case(
        dl, owner_id, em_state=EM.REVISE if replaces else EM.PROPOSED
    )
    owner_p = participants[0]
    active_id = _make_embargo(dl, case.id_).id_ if replaces else None
    case.active_embargo = active_id
    case.proposed_embargoes = [activated_id]
    dl.save(case)
    if active_id is not None:
        _seed_consent(dl, owner_p.id_, PEC.SIGNATORY, [active_id])
    return case, owner_p, active_id


def _assert_activation_wrote_nothing(
    dl: SqliteDataLayer,
    case: VulnerabilityCase,
    owner_p: CaseParticipant,
    *,
    active_id: str | None,
    activated_id: str,
) -> None:
    """EM, ``active_embargo``, the proposals and the owner's consent unchanged."""
    untouched = cast(VulnerabilityCase, dl.read(case.id_))
    assert untouched.current_status.em.state == case.current_status.em.state
    assert untouched.active_embargo_id == active_id
    assert untouched.proposed_embargoes == [activated_id]
    owner = cast(CaseParticipant, dl.read(owner_p.id_))
    expected_pec = PEC.UNBOUND if active_id is None else PEC.SIGNATORY
    assert owner.embargo_consent_state == expected_pec.value
    assert owner.accepted_embargo_ids == (
        [] if active_id is None else [active_id]
    )


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def owner_and_dl() -> Generator[
    tuple[as_Service, SqliteDataLayer], None, None
]:
    owner = as_Service(name="Owner Org")
    reset_datalayer(owner.id_)
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=owner.id_)
    dl.clear_all()
    dl.create(owner)
    try:
        yield owner, dl
    finally:
        dl.close()
        reset_datalayer(owner.id_)


# ---------------------------------------------------------------------------
# P/X/A embargo-eligibility guard inputs (#1454)
# ---------------------------------------------------------------------------

# All non-pxa CS_pxa states trigger the guard.
_PXA_INELIGIBLE_STATES = [
    CS_pxa.Pxa,  # public aware
    CS_pxa.pXa,  # exploit published
    CS_pxa.pxA,  # attacks observed
    CS_pxa.PXa,  # public + exploit
    CS_pxa.PxA,  # public + attacks
    CS_pxa.pXA,  # exploit + attacks
    CS_pxa.PXA,  # all three set
]
