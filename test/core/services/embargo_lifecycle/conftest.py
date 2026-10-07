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

from test.support.embargo_register import activate, propose
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
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.protocols import PersistableModel
from vultron.core.states.cs import CS_pxa
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
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
) -> tuple[VulnerabilityCase, list[CaseParticipant]]:
    """Create a VulnerabilityCase with an owner participant.

    The case starts with an empty embargo register (EM ``NONE``); a test that
    needs another EM state builds the register with
    :mod:`test.support.embargo_register` once its embargoes exist, because EM
    is derived from the register (ADR-0122).

    Returns the case and the list of CaseParticipant objects created.
    """
    case = VulnerabilityCase(
        name="Test embargo case",
        attributed_to=owner_id,
    )

    owner_participant = VendorParticipant(
        attributed_to=owner_id,
        context=case.id_,
    )
    owner_participant.add_role(CVDRole.CASE_MANAGER)

    participants: list[CaseParticipant] = [owner_participant]
    case.case_participants = [owner_participant.id_]
    case.actor_participant_index = {owner_id: owner_participant.id_}

    for pid in extra_participant_ids or []:
        p = FinderParticipant(
            attributed_to=pid,
            context=case.id_,
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


def _record_save_many(
    dl: SqliteDataLayer, monkeypatch: pytest.MonkeyPatch
) -> list[list[PersistableModel]]:
    """Record every ``save_many`` batch *dl* is handed, then pass it on."""
    calls: list[list[PersistableModel]] = []
    save_many = dl.save_many

    def recording_save_many(objs: list[PersistableModel]) -> None:
        calls.append(list(objs))
        save_many(objs)

    monkeypatch.setattr(dl, "save_many", recording_save_many)
    return calls


def _consent_of(
    dl: SqliteDataLayer, participant_id: str, embargo_id: str
) -> str | None:
    """The stored consent row state for *embargo_id* (``None``: never asked)."""
    state = cast(CaseParticipant, dl.read(participant_id)).consent_for(
        embargo_id
    )
    return state.value if state is not None else None


def _consents_of(dl: SqliteDataLayer, participant_id: str) -> dict[str, str]:
    """Every stored consent row of the participant, ``embargo_id -> state``."""
    participant = cast(CaseParticipant, dl.read(participant_id))
    return {r.embargo_id: r.state.value for r in participant.embargo_consents}


def _seed_consent(
    dl: SqliteDataLayer,
    participant_id: str,
    embargo_id: str,
    state: EmbargoConsentState,
) -> None:
    """Seed one consent row directly — test setup only, never a consent write."""
    participant = cast(CaseParticipant, dl.read(participant_id))
    rows = [
        r for r in participant.embargo_consents if r.embargo_id != embargo_id
    ]
    participant.embargo_consents = [
        *rows,
        EmbargoConsent(embargo_id=embargo_id, state=state),
    ]
    dl.save(participant)


def _is_signatory(
    dl: SqliteDataLayer, case_id: str, participant_id: str
) -> bool:
    """Derived: the participant accepted the case's active embargo."""
    case = cast(VulnerabilityCase, dl.read(case_id))
    participant = cast(CaseParticipant, dl.read(participant_id))
    return participant.is_signatory(case.active_embargo_id)


def _has_lapsed(
    dl: SqliteDataLayer, case_id: str, participant_id: str
) -> bool:
    """Derived: the participant accepted an older embargo, not the active one."""
    case = cast(VulnerabilityCase, dl.read(case_id))
    participant = cast(CaseParticipant, dl.read(participant_id))
    return participant.has_lapsed(case.active_embargo_id)


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
    case, participants = _make_case(dl, owner_id)
    owner_p = participants[0]
    active_id = _make_embargo(dl, case.id_).id_ if replaces else None
    if active_id is not None:
        activate(case, active_id)
    propose(case, activated_id)
    dl.save(case)
    if active_id is not None:
        _seed_consent(dl, owner_p.id_, active_id, EmbargoConsentState.ACCEPTED)
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
    assert untouched.em_state == case.em_state
    assert untouched.active_embargo_id == active_id
    assert untouched.proposed_embargo_ids == [activated_id]
    owner = cast(CaseParticipant, dl.read(owner_p.id_))
    assert {r.embargo_id: r.state.value for r in owner.embargo_consents} == (
        {} if active_id is None else {active_id: "ACCEPTED"}
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
