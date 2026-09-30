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
from typing import cast

import pytest

# noqa: F401 — imported for vocabulary registration side-effect
from vultron.wire.as2.vocab.objects.vulnerability_case import (  # noqa: F401
    as_VulnerabilityCase,
)

from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
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
from vultron.core.models._helpers import days_from_now_utc

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
    dl: SqliteDataLayer, case_id: str, *, days: int = 45
) -> as_EmbargoEvent:
    """Persist an ``EmbargoEvent`` ending *days* from now (the A-vs-B knob)."""
    embargo = as_EmbargoEvent(
        context=case_id, end_time=days_from_now_utc(days)
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
    participant = cast(CaseParticipant, dl.read(participant_id))
    object.__setattr__(participant, "embargo_consent_state", state)
    participant.accepted_embargo_ids = list(accepted)
    dl.save(participant)


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def owner_and_dl() -> (
    Generator[tuple[as_Service, SqliteDataLayer], None, None]
):
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
