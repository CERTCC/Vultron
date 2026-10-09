#!/usr/bin/env python

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

"""Shared fixtures for test/core/behaviors/embargo/nodes tests."""

import py_trees
import pytest

from test.support.embargo_register import (
    activate,
    propose,
    terminate,
    write_consent_rows,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import (  # noqa: F401
    as_VulnerabilityCase,
)

CASE_MANAGER_ACTOR = "https://example.org/actors/case-manager"
#: A non-manager participant. The teardown announce is addressed to the case's
#: other participants, so a case needs one for the emission to be observable.
OTHER_PARTICIPANT_ACTOR = "https://example.org/actors/vendor"


def make_case_and_embargo(
    case_suffix: str,
    em_state: EM = EM.ACTIVE,
    attributed_to: str = CASE_MANAGER_ACTOR,
) -> tuple[VulnerabilityCase, as_EmbargoEvent]:
    """Create an in-memory VulnerabilityCase + as_EmbargoEvent pair.

    ``attributed_to`` is required for any tree that commits to the canonical
    ledger: the per-case genesis hash is derived from it (CLP-08-001/002), and
    without one ``ReconstructChainTailNode`` cannot anchor an empty chain and the
    commit fails with "per-case genesis hash is unavailable".
    """
    case = VulnerabilityCase(
        id_=f"https://example.org/cases/case_{case_suffix}",
        name=f"Test Case {case_suffix}",
        attributed_to=attributed_to,
    )
    embargo = as_EmbargoEvent(
        id_=f"https://example.org/cases/case_{case_suffix}/embargo_events/e1",
        context=case.id_,
        end_time=days_from_now_utc(45),
    )
    _drive_register_to(case, embargo, em_state)
    return case, embargo


def _drive_register_to(
    case: VulnerabilityCase, embargo: as_EmbargoEvent, em_state: EM
) -> None:
    """Drive *case*'s embargo register so its derived EM is *em_state*.

    EM is derived from the register (ADR-0122), so each state is reached by
    the register steps that produce it: ``PROPOSED`` holds *embargo* as an
    open proposal; ``ACTIVE`` has it in force; ``REVISE`` adds a second open
    proposal (``.../embargo_events/e2``) beside it; ``EXITED`` terminates it;
    ``NONE`` leaves the register empty.
    """
    if em_state == EM.NONE:
        return
    if em_state == EM.PROPOSED:
        propose(case, embargo)
        return
    activate(case, embargo)
    if em_state == EM.REVISE:
        propose(case, f"{case.id_}/embargo_events/e2")
    elif em_state == EM.EXITED:
        terminate(case)


def make_case_with_manager(
    suffix: str,
    em_state: EM = EM.ACTIVE,
    case_manager_actor: str = CASE_MANAGER_ACTOR,
    other_participants: tuple[str, ...] = (OTHER_PARTICIPANT_ACTOR,),
    other_consent: EmbargoConsentState | None = EmbargoConsentState.AGREED,
    store_actor_id: str | None = None,
) -> tuple[VulnerabilityCase, as_CaseParticipant, SqliteDataLayer]:
    """Return a DataLayer with a case, a CASE_MANAGER, and other participants.

    The case gets at least one participant besides the manager by default,
    because the teardown announce is addressed to the case's *other*
    participants.  A case whose only participant is the manager has nobody to
    announce to, so the announce is skipped — correct behaviour, but it makes a
    fixture built that way unable to observe the emission at all.

    Every participant holds an *other_consent* row for the case's embargo —
    ``AGREED`` by default (``None``: only the ``UNINVITED`` row every register
    entry gets), so it is a signatory, active
    while the embargo is (CM-10-004) and a case-content send reaches
    it.

    *store_actor_id* names the actor whose store holds the case; ``None`` is
    the CASE_MANAGER's.  Pass a participant's id for that participant's own
    replica of the same case (TB-06-007).
    """
    # The store belongs to the CASE_MANAGER named here by default: the teardown
    # trees commit to the canonical ledger, which that role holder owns (CLP-09,
    # ADR-0073).
    dl = SqliteDataLayer(
        "sqlite:///:memory:", actor_id=store_actor_id or case_manager_actor
    )
    case, embargo = make_case_and_embargo(suffix, em_state=em_state)
    consents = (
        []
        if other_consent is None
        else [EmbargoConsent(embargo_id=embargo.id_, state=other_consent)]
    )
    cm_participant = as_CaseParticipant(
        id_=f"{case.id_}/participants/cm",
        attributed_to=case_manager_actor,
        case_roles=[CVDRole.CASE_MANAGER],
        embargo_consents=list(consents),
    )
    case.case_participants.append(cm_participant.id_)
    case.actor_participant_index[case_manager_actor] = cm_participant.id_
    dl.create(cm_participant)

    for i, actor in enumerate(other_participants):
        participant = as_CaseParticipant(
            id_=f"{case.id_}/participants/p{i}",
            attributed_to=actor,
            context=case.id_,
            embargo_consents=list(consents),
        )
        case.case_participants.append(participant.id_)
        case.actor_participant_index[actor] = participant.id_
        dl.create(participant)

    dl.create(case)
    # Every other register entry (the REVISE proposal) gets its UNINVITED row,
    # as a proposal writes it (ADR-0122).
    write_consent_rows(dl, case)
    return case, cm_participant, dl


def setup_blackboard(
    dl: SqliteDataLayer,
    actor_id: str = "https://example.org/users/vendor",
) -> None:
    """Populate the py_trees blackboard with the DataLayer and actor_id."""
    py_trees.blackboard.Blackboard.enable_activity_stream()
    blackboard = py_trees.blackboard.Client(name="test-setup")
    blackboard.register_key(
        key="datalayer", access=py_trees.common.Access.WRITE
    )
    blackboard.register_key(
        key="actor_id", access=py_trees.common.Access.WRITE
    )
    blackboard.datalayer = dl
    blackboard.actor_id = actor_id


@pytest.fixture
def dl() -> SqliteDataLayer:
    """Return a fresh in-memory SQLite DataLayer."""
    return SqliteDataLayer(
        "sqlite:///:memory:",
        actor_id="https://test.example/api/v2/actors/test-actor",
    )
